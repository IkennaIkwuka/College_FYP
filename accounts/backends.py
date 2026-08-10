from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend


class MatricNumberOrUsernameBackend(ModelBackend):
    """Lets students log in with their matric number, and everyone else with their username."""

    def authenticate(self, request, username=None, password=None, **kwargs):
        if username is None or password is None:
            return None

        User = get_user_model()
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
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
