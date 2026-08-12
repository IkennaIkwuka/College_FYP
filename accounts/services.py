from django.conf import settings
from django.db import transaction

from .models import StaffIDCounter

STAFF_ID_PREFIX = "STF"
STAFF_ID_DIGITS = 4


def generate_next_staff_id():
    """Atomically reserve and return the next sequential staff ID, e.g. 'STF0007'.

    select_for_update() is a no-op on SQLite (it has no row-locking support), but SQLite's
    own single-writer transaction lock already serializes this correctly today - and this
    becomes correct on Postgres/MySQL too, with no code change, if the project ever moves
    off SQLite.
    """
    with transaction.atomic():
        counter = StaffIDCounter.objects.select_for_update().get(pk=1)
        counter.last_number += 1
        counter.save(update_fields=["last_number"])
        return f"{STAFF_ID_PREFIX}{counter.last_number:0{STAFF_ID_DIGITS}d}"


def assign_staff_identity(user):
    """Mutates an unsaved User in place: staff_id, username, and initial password/flag.

    Kept separate from admin.py so it's testable directly without driving the admin
    add_view. Caller is still responsible for user.save().
    """
    staff_id = generate_next_staff_id()
    user.staff_id = staff_id
    user.username = staff_id.lower()
    user.set_password(settings.DEFAULT_PASSWORD)
    user.must_change_password = True
    return user
