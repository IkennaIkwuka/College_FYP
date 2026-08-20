document.addEventListener("DOMContentLoaded", function () {
    var EYE = '<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" ' +
        'fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">' +
        '<path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8Z"/><circle cx="12" cy="12" r="3"/></svg>';
    var EYE_SLASH = '<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" ' +
        'fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">' +
        '<path d="M17.94 17.94A10.94 10.94 0 0 1 12 20c-7 0-11-8-11-8a20.3 20.3 0 0 1 5.06-5.94"/>' +
        '<path d="M9.9 4.24A10.4 10.4 0 0 1 12 4c7 0 11 8 11 8a20.3 20.3 0 0 1-3.22 4.36"/>' +
        '<path d="M14.12 14.12a3 3 0 1 1-4.24-4.24"/><line x1="1" y1="1" x2="23" y2="23"/></svg>';

    document.querySelectorAll(".password-toggle").forEach(function (btn) {
        var input = document.getElementById(btn.dataset.target);
        if (!input) return;
        btn.innerHTML = EYE;
        btn.setAttribute("aria-label", "Show password");
        btn.addEventListener("click", function () {
            var showing = input.type === "text";
            input.type = showing ? "password" : "text";
            btn.innerHTML = showing ? EYE : EYE_SLASH;
            btn.setAttribute("aria-label", showing ? "Show password" : "Hide password");
        });
    });
});
