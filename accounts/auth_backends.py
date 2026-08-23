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
            # Match the stripped form (lenient matric-number typing) AND the
            # exact-as-typed form (a manually-created staff username can itself
            # legitimately contain punctuation Django's validator allows -
            # @/./+/-/_ - e.g. one typed straight into /admin/accounts/user/add/,
            # not derived from a slash-stripped matric/staff ID). Without the raw
            # match, an account like "j.smith" could never log in, since the
            # stripped form "jsmith" would never match the stored "j.smith".
            user = UserModel._default_manager.get(
                Q(username__iexact=raw) | Q(username__iexact=cleaned) | Q(preferred_username__iexact=raw)
            )
        except UserModel.DoesNotExist:
            # Same timing-attack mitigation ModelBackend uses: still hash the
            # password even when there's no matching user, so response time
            # doesn't leak whether a username exists.
            UserModel().set_password(password)
            return None
        except UserModel.MultipleObjectsReturned:
            return None

        # A student who hasn't finished first-login setup skips the password check
        # entirely - see User.skips_first_login_password for why this is safe.
        # Whatever was typed (blank or otherwise) is irrelevant for this branch.
        if user.skips_first_login_password:
            return user

        # FR-AUTH-05: lock out after settings.LOGIN_MAX_ATTEMPTS consecutive wrong
        # passwords. Lazily clear an expired lockout first, same pattern as the
        # PIN/email-change lockouts - no cron needed, the next attempt after the
        # cooldown passes just resets the counter here.
        if user.login_locked_until is not None and not user.is_login_locked:
            user.reset_login_attempts()

        if user.is_login_locked:
            return None

        if user.check_password(password):
            if self.user_can_authenticate(user):
                user.reset_login_attempts()
                return user
            # Correct password but inactive account - not a wrong guess, don't
            # count it against the lockout.
            return None

        user.register_failed_login_attempt()
        return None
