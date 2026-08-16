from django.conf import settings

from lu_sims.id_format import format_academic_id


def assign_staff_identity(user):
    """Mutates an unsaved User in place: username, and initial password/flag.

    Assumes the caller has already set user.staff_id from validated form data (portal
    or Django admin), checked unique there - this normalizes it and derives the
    username from it. Kept separate from admin.py so it's testable directly without
    driving the admin add_view. Caller is still responsible for user.save().
    """
    user.staff_id = format_academic_id(user.staff_id)
    # Django's username field rejects "/", which staff IDs may contain (e.g.
    # HOD/CSC/001) - LenientUsernameBackend (accounts/auth_backends.py) is what
    # actually lets someone log in typing the staff ID in its natural shape
    # instead of this stripped/lowercased form.
    user.username = user.staff_id.lower().replace("/", "")
    user.set_password(settings.DEFAULT_PASSWORD)
    user.must_change_password = True
    return user


def force_password_reset(user):
    """Resets an existing account back to the same state a freshly-created one
    starts in: shared default password, forced change on next login. Covers both
    "forgot it" and "think it's compromised" - either way the old password stops
    working immediately.
    """
    user.set_password(settings.DEFAULT_PASSWORD)
    user.must_change_password = True
    user.save(update_fields=["password", "must_change_password"])
