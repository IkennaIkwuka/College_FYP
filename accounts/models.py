from datetime import timedelta

from django.conf import settings
from django.contrib.auth.hashers import check_password
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone

ADMIN_GROUP = "IT Admin"
LECTURER_GROUP = "Lecturer"
STUDENT_GROUP = "Student"
HOD_GROUP = "HOD"
REGISTRAR_GROUP = "Registrar"
BURSAR_GROUP = "Bursar"
DEAN_GROUP = "Dean"

# 2-letter code embedded in generated staff IDs (e.g. "LU-RG-26-0001").
STAFF_ROLE_CODES = {
    ADMIN_GROUP: "AD",
    HOD_GROUP: "HD",
    LECTURER_GROUP: "LC",
    REGISTRAR_GROUP: "RG",
    BURSAR_GROUP: "BS",
    DEAN_GROUP: "DN",
}

# Local copy, not shared with students.models.GENDER_CHOICES - students already
# depends on accounts one-directionally, so importing the other way isn't an
# option, and the two fields aren't otherwise unified (see accounts/models.py's
# User.gender docstring below).
GENDER_CHOICES = [
    ("M", "Male"),
    ("F", "Female"),
]


class User(AbstractUser):
    """Custom user model so role/permission logic isn't locked to Django's default auth.User."""

    email = models.EmailField(unique=True)
    must_change_password = models.BooleanField(default=False)
    # Only set for staff (Lecturer/HOD/IT Admin) - students are identified by
    # StudentProfile.matric_number instead. null=True (not just blank) so every
    # student's staff_id being empty doesn't collide under the unique constraint -
    # SQL treats multiple NULLs as non-conflicting, unlike multiple empty strings.
    staff_id = models.CharField(max_length=20, unique=True, null=True, blank=True)
    # Optional second login credential, self-chosen - the derived `username` above
    # never stops working, this is purely an additional way in. null=True (not just
    # blank) for the same reason as staff_id - multiple unset accounts shouldn't
    # collide under the unique constraint.
    preferred_username = models.CharField(max_length=150, unique=True, null=True, blank=True)
    # When last changed, not an absolute unlock timestamp - so PREFERRED_USERNAME_COOLDOWN_DAYS
    # can be tuned later without leaving already-set cooldowns stuck on the old duration.
    preferred_username_changed_at = models.DateTimeField(null=True, blank=True)
    # Self-service personal info, staff-only in practice - students already have
    # equivalent fields on StudentProfile (phone_number/date_of_birth/gender/address),
    # wired into bulk-import CSV columns, the registrar edit form, and lookup.html.
    # Moving those onto User instead would mean a data migration for every existing
    # student plus updating all of that, for no real benefit - kept separate instead.
    phone_number = models.CharField(max_length=20, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    gender = models.CharField(max_length=1, choices=GENDER_CHOICES, blank=True)
    # Self-service email change, verified with a code sent to the new address (not the
    # old one - the point is confirming the new address is real and reachable) before it
    # takes effect. Same hashing/lockout shape as StudentProfile's first-login PIN
    # (students/models.py) - independently defined rather than imported, same reason as
    # GENDER_CHOICES above: accounts can't depend on students.
    pending_email = models.EmailField(blank=True, default="")
    email_change_code_hash = models.CharField(max_length=128, blank=True, default="")
    email_change_attempts = models.PositiveSmallIntegerField(default=0)
    email_change_locked_until = models.DateTimeField(null=True, blank=True)
    # When the email last actually changed - cooldown timestamp, same role as
    # preferred_username_changed_at above.
    email_changed_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        # AbstractUser's default falls back to username, which is a stripped-down
        # ID (e.g. "hodcsc001") - not something anyone should see displayed as a
        # person's identity in a template, list, or dropdown.
        return self.get_full_name() or self.username

    def has_role(self, group_name):
        return self.groups.filter(name=group_name).exists()

    @property
    def is_admin(self):
        return self.is_superuser or self.has_role(ADMIN_GROUP)

    @property
    def is_lecturer(self):
        return self.has_role(LECTURER_GROUP)

    @property
    def is_student(self):
        return self.has_role(STUDENT_GROUP)

    @property
    def is_hod(self):
        return self.has_role(HOD_GROUP)

    @property
    def is_registrar(self):
        return self.has_role(REGISTRAR_GROUP)

    @property
    def is_bursar(self):
        return self.has_role(BURSAR_GROUP)

    @property
    def is_dean(self):
        return self.has_role(DEAN_GROUP)

    @property
    def preferred_username_locked_until(self):
        if not self.preferred_username_changed_at:
            return None
        unlock = self.preferred_username_changed_at + timedelta(days=settings.PREFERRED_USERNAME_COOLDOWN_DAYS)
        return unlock if unlock > timezone.now() else None

    @property
    def email_locked_until(self):
        if not self.email_changed_at:
            return None
        unlock = self.email_changed_at + timedelta(days=settings.EMAIL_CHANGE_COOLDOWN_DAYS)
        return unlock if unlock > timezone.now() else None

    def check_email_change_code(self, raw_code):
        return check_password(raw_code, self.email_change_code_hash)

    @property
    def is_email_change_locked(self):
        return self.email_change_locked_until is not None and self.email_change_locked_until > timezone.now()

    def register_failed_email_change_attempt(self):
        self.email_change_attempts += 1
        if self.email_change_attempts >= settings.EMAIL_CHANGE_CODE_MAX_ATTEMPTS:
            self.email_change_locked_until = timezone.now() + timedelta(minutes=settings.EMAIL_CHANGE_CODE_LOCKOUT_MINUTES)
        self.save(update_fields=["email_change_attempts", "email_change_locked_until"])

    def reset_email_change_attempts(self):
        self.email_change_attempts = 0
        self.email_change_locked_until = None
        self.save(update_fields=["email_change_attempts", "email_change_locked_until"])


class StaffIDSequence(models.Model):
    """Per-role-per-year counter driving staff IDs like "LU-RG-26-0001".

    A dedicated counter (rather than scanning User.staff_id for the current max) stays
    correct even after a staff account is deleted, and is what generate_staff_id() in
    accounts.services locks via select_for_update() to keep concurrent staff creation
    from handing out the same ID twice. select_for_update() is a no-op on SQLite (it has
    no row-locking support), but SQLite's own single-writer transaction lock already
    serializes this correctly today - and this becomes correct on Postgres/MySQL too,
    with no code change, if the project ever moves off SQLite.
    """

    role_code = models.CharField(max_length=2)
    year = models.PositiveSmallIntegerField()
    last_number = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = ("role_code", "year")
