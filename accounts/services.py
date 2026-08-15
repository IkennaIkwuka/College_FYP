from django.conf import settings


def assign_staff_identity(user):
    """Mutates an unsaved User in place: username, and initial password/flag.

    Assumes the caller has already set user.staff_id from validated form data (portal
    or Django admin), normalized and checked unique there - this just derives the
    username from it. Kept separate from admin.py so it's testable directly without
    driving the admin add_view. Caller is still responsible for user.save().
    """
    # Django's username field rejects "/", which staff IDs may contain (e.g.
    # 2026/CSC/010, mirroring matric number convention) - same fix as
    # students.services.create_student_account uses for the same reason.
    user.username = user.staff_id.lower().replace("/", "")
    user.set_password(settings.DEFAULT_PASSWORD)
    user.must_change_password = True
    return user
