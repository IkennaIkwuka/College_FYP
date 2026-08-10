import re

from django.core.exceptions import ValidationError


class ComplexityValidator:
    """Requires a mix of character types, not just length.

    Django's built-in validators only check length, similarity to the user's own
    details, and whether it's a known common/all-numeric password - a long password
    made of only lowercase letters would sail through those. This adds the
    uppercase/lowercase/digit/symbol requirement on top, matching the "stricter
    criteria" and "medium strength or better" requirement for student passwords.
    """

    def validate(self, password, user=None):
        if not re.search(r"[A-Z]", password):
            raise ValidationError("Password must include at least one uppercase letter.", code="password_no_upper")
        if not re.search(r"[a-z]", password):
            raise ValidationError("Password must include at least one lowercase letter.", code="password_no_lower")
        if not re.search(r"\d", password):
            raise ValidationError("Password must include at least one digit.", code="password_no_digit")
        if not re.search(r"[^A-Za-z0-9]", password):
            raise ValidationError(
                "Password must include at least one special character.", code="password_no_special"
            )

    def get_help_text(self):
        return "Must include an uppercase letter, a lowercase letter, a digit, and a special character."
