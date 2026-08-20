import re

from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend
from django.db.models import Q


class LenientUsernameBackend(ModelBackend):
    """Matches the typed username after stripping punctuation and ignoring case.

    Usernames are derived from a matric number or staff ID with slashes stripped
    (see students/services.py, accounts/services.py) - this lets someone log in
    typing the ID in its natural shape (e.g. "2025/CSC/010" or "hod-csc-001")
    instead of needing to know the exact stripped/cased form it was stored as.

    Also matches User.preferred_username, a self-chosen second login credential -
    that one is compared as typed (just trimmed, not stripped of punctuation), since
    its punctuation is meaningful and chosen by the person, unlike the derived username.
    """

    def authenticate(self, request, username=None, password=None, **kwargs):
        if username is None or password is None:
            return None
        UserModel = get_user_model()
        cleaned = re.sub(r"[^A-Za-z0-9]", "", username)
        raw = username.strip()
        try:
            user = UserModel._default_manager.get(Q(username__iexact=cleaned) | Q(preferred_username__iexact=raw))
        except UserModel.DoesNotExist:
            # Same timing-attack mitigation ModelBackend uses: still hash the
            # password even when there's no matching user, so response time
            # doesn't leak whether a username exists.
            UserModel().set_password(password)
            return None
        except UserModel.MultipleObjectsReturned:
            return None
        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None
