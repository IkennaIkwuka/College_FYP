document.addEventListener("DOMContentLoaded", function () {
    // Mirrors PreferredUsernameForm.clean_preferred_username's regex - a UX hint only,
    // the server-side check (accounts/forms.py) is what actually enforces this.
    var PATTERN = /^[A-Za-z][A-Za-z0-9._-]{3,149}$/;

    document.querySelectorAll("[data-username-hint]").forEach(function (input) {
        var hint = document.getElementById(input.dataset.usernameHint);
        if (!hint) return;
        var defaultText = hint.textContent;

        input.addEventListener("input", function () {
            var value = input.value.trim();
            if (!value) {
                hint.textContent = defaultText;
                hint.className = "form-text text-muted";
                return;
            }
            var valid = PATTERN.test(value);
            hint.textContent = valid ? "Looks good." : defaultText;
            hint.className = "form-text " + (valid ? "text-success" : "text-danger");
        });
    });
});
