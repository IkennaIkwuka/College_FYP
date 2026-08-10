from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend


class MatricNumberOrUsernameBackend(ModelBackend):
    """Lets students log in with their matric number, and everyone else with their username."""

    def authenticate(self, request, username=None, password=None, **kwargs):
        if username is None or password is None:
            return None

        # The login form only has one "username" box. Try it as a real username first
        # (covers Admin/Lecturer accounts), and only fall back to matric-number lookup
        # if that fails - this keeps normal username login working unchanged.
        User = get_user_model()
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            # Import here, not at the top of the file: students imports accounts.models,
            # so importing students.models up top would risk a circular import.
            from students.models import StudentProfile

            try:
                profile = StudentProfile.objects.select_related("user").get(
                    matric_number=username.strip().upper()
                )
            except StudentProfile.DoesNotExist:
                return None
            user = profile.user

        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None
