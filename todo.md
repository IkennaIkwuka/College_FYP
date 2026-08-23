# todo.md

Sectioned by severity (Critical/High/Medium/Low), then Decisions (settled,
don't relitigate without new info), then Brainstormed (not yet scoped), then
Done. Severity reflects impact/urgency, not effort. Keep this structure
going forward - new items get filed into the right section, not appended
chronologically at the bottom.

## Critical

- [ ] Transcript request/approval workflow (SRS FR-STU-05, FR-REG-02/03) - student submits a request, Registrar approves/rejects, then generates the document. Not built. The Pilot Proposal already names this as the pilot's headline feature to the HOD, so it's represented as working when it isn't.
- [ ] Audit logging (SRS FR-LOG-01-05) - log every login attempt, every create/update/delete on academic/financial records, every denied access attempt; immutable; viewable only by IT Admin/Super Admin. Not built. The Pilot Proposal already states to the HOD that "every action taken on the system is logged."
- [ ] Attendance Management module - one of the HOD Project Brief's own four committed modules (Auth/RBAC, Student Info, Course Registration, Attendance). Zero code anywhere. Undelivered against the project's own submitted scope.

## High

- [ ] SQLite -> real DB before deployment - needs an actual DB instance to point at, deliberately not picked yet. Real blocker before the pilot proposal's own "core system already built, need 4-6 weeks internal testing" timeline can hold.
- [ ] FR-AUTH-06: session expiry after 30 minutes of inactivity - not implemented, no SESSION_COOKIE_AGE or idle-expiry configured. Distinct from the "Session timeout / auto-logout" brainstorm item below (that one's a cybercafe-UX nicety; this is a specific SRS requirement already promised in the document set).
- [ ] LEVEL_CHOICES caps at 500, blocks 600L for 6-year departments (Medicine/Law/Engineering) - internal bug, not just a NUC gap.
- [ ] docs/SDD_Legacy_University_Portal.md Section 5 (RBAC Design) describes a generic roles/permissions/role_permissions schema + single @permission_required decorator + Super Admin permission-matrix editor; actual code is 7 hardcoded per-role decorators in accounts/decorators.py checking Group membership. Functionally equivalent, but the document doesn't match the code. Needs a decision on which one to update - not done, not started.
- [ ] `feedback_flag_new_django_app_boundaries.md` (project memory) still says the `StudentAccountForm`/`register`-view accounts->students coupling is "not fixed yet" - it was fixed 2026-08-20 (commit `aa6832f`, confirmed live in the current codebase). The memory file needs correcting; it's a documentation error actively misinforming future sessions, not a code issue.
- [ ] DEFAULT_PASSWORD is one shared password for every new account - consider per-account random initial passwords instead.

## Medium

- [ ] Bursar / Fees module - role and dashboard exist, no functional fee features built.
- [ ] Course registration approval workflow - currently pure self-service, no Advisor/HOD/Faculty Board approval step, no unit-load exception path, Dean has no approval capability.
- [ ] Carryover-student handling (unblocked now that Results system exists) - no tracking of failed/repeated courses, no NUC max-duration (~1.5x programme length) withdrawal enforcement.
- [ ] Staff qualification tracking - no field records highest qualification, so HOD/Dean appointments can't be checked against NUC's practical PhD expectation.
- [ ] Superuser vs IT Admin identity/dashboard separation - deferred mid-discussion, never decided between a label-only fix and a fully separate dashboard.
- [ ] Auxiliary/informal staff designations (Exams Officer, Course/Level Adviser, SIWES Coordinator, etc.) - 2026-08-22 decision: don't give these full RBAC treatment (new Group/decorator/dashboard/nav/ID-code) like the 7 core roles, since they're informal "hats" a Lecturer holds on top of their main role, not standardized structural offices, and there's no feature yet to gate by them. Model as a lightweight descriptive designation field on User first; only wire a real permission check once an actual feature (e.g. an Exams module) needs restricting to whoever holds it.
- [ ] Test coverage: 6 JSON typeahead endpoints untested, resend_email_change_code untested, Faculty CRUD untested.
- [ ] courses app has no services.py - registration logic inlined in views.py, will get worse once approval workflow lands.
- [ ] Memory hygiene: the `project_fyp_current_state_*` chain is now 7 files deep (15/17/18/20/21/22/23, the largest ~24KB) - consider consolidating the older ones (15/17/18/20/21) into one condensed historical file now that a full audit has to read all of them, and now that the chain has already produced one real contradiction between what an older snapshot said and what later ones said (see Done section - accounts/students PIN import).
- [ ] Dev-workflow: no CI configured (no GitHub Actions or equivalent) - `python manage.py test` only runs when someone remembers to run it locally.
- [ ] Dev-workflow: no linter/formatter configured (no flake8/ruff/black) - style is currently whatever each session happened to write.
- [ ] Dev-workflow: no type checker configured or ever run against project code (no mypy/pyright) - `pyrightconfig.json` added 2026-08-23 scopes Pylance to project code instead of `venv/site-packages`, but nobody's actually run a type-checking pass yet to see what it surfaces.

## Low

- [ ] Minor cleanup: unnecessary |safe on password help_text (3 templates), CSV bulk_import has no size/encoding guard, unused test vars in students/tests.py:248 and courses/tests.py:243.
- [ ] Course-code semester-parity rule (odd/even = 1st/2nd sem) has no confirmed NUC source - unverified project convention, not urgent.

## Decisions (settled, don't relitigate without new information)

- **"One app per role" restructure** - considered and rejected 2026-08-23: Django apps should own a data domain, not a role; most SRS roles (Student/Registrar/HOD/Dean/IT Admin) all touch the same models (StudentProfile, Course, Result), so per-role apps would force either model duplication or cross-app imports worse than any coupling already in the codebase. Only split a new app off when a role needs data nobody else owns yet - e.g. Bursar/Fees, Audit log.

## Brainstormed / not yet scoped

Core academic - fits FYP scope, builds on Results system now that it exists:
- [ ] Transcript generation (PDF) - once the Critical transcript-workflow item above exists to attach it to.
- [ ] Course prerequisite enforcement at registration time
- [ ] Add/drop deadline enforcement (registration window dates, not just CURRENT_SEMESTER flag)
- [ ] Graduation-eligibility checker - units completed + CGPA + no outstanding carryover
- [ ] Auto probation/warning flag from CGPA threshold - ties into Results

Bursar/Fees - expands the already-planned module:
- [ ] Fee schedule per department/level/session
- [ ] Record payments + generate receipts (internal ledger, not a payment gateway)
- [ ] Fee-clearance gate blocking registration on outstanding balance

Admin/records:
- [ ] Document upload per student (admission letter, credentials)
- [ ] Announcements/notices board - referenced below as a dashboard widget dependency, not yet its own tracked feature

Per-role dashboard content (2026-08-22 brainstorm) - every dashboard is currently
just a "Welcome, X" placeholder, no summary content:
- [ ] IT Admin: staff/student headcount by role/department, recently created accounts, accounts still on default password / never logged in
- [ ] Dean: departments under faculty + their HODs, faculty-wide student headcount, pending Dean approvals (once registration approval workflow exists)
- [ ] HOD: department student headcount by level, lecturers + what they teach, pending department approvals (once registration approval workflow exists)
- [ ] Registrar: recent admissions, students still pending first-login PIN verification, department/level breakdown counts
- [ ] Bursar: outstanding-balance summary, recent payments, students blocked from registration on unpaid fees (blocked on Fees module above)
- [ ] Lecturer: courses currently teaching + enrolled-student counts, recent registrations into their courses
- [ ] Student: registered courses + unit count against MIN/MAX_SEMESTER_UNITS, CGPA/level summary (once Results exists), surface incomplete PIN/profile steps here
- [ ] Cross-role: shared announcements/notices widget once a notice-board feature exists, same widget on every dashboard, content scoped per audience

Stretch / likely out of FYP scope, noted for awareness:
- [ ] Payment gateway integration (Paystack/Flutterwave)
- [ ] SMS alerts alongside email (PIN/reset codes) - relevant since not everyone checks email
- [ ] ID card generation with photo/QR
- [ ] Timetable/class-schedule management
- [ ] Session timeout / auto-logout for shared/cybercafe use

## Done

- [x] Add a filter in Manage Students to filter by level, dept
- [x] Results / grades / CGPA system - done 2026-08-22, new `results` app (see project memory for design). Lecturer/HOD upload-only, no in-portal draft/publish cycle. GPA/CGPA computed on demand.
- [x] accounts/views.py imports from students (PIN flow) - fixed 2026-08-23: send_pin_code moved to lu_sims/views.py (the existing accounts+students composition layer, same pattern as profile/profile_edit), accounts/urls.py imports it from there. URL name/path unchanged, 218 tests still green.
- [x] Contradiction across memory on the accounts/students PIN-flow import - resolved 2026-08-23, see the entry above and `project_fyp_current_state_2026_08_23.md`. Fixed in code, not just documented.
- [x] Dependency/migration drift check (`/deep-audit`, 2026-08-23) - clean. `requirements.txt` matches actual imports (no unused/undeclared deps), `manage.py makemigrations --check --dry-run` reports no changes detected.
- [x] Email-existence enumeration oracle - fixed 2026-08-23, scoped to `RequestEmailChangeForm` only (the one self-service form reachable by any logged-in user). `StaffAccountForm`/`StaffEditForm`/`StudentAccountForm`/`StudentEditForm` deliberately left as-is - they're already `registrar_required`/`admin_required`-gated, so "email already taken" there is legitimate admin UX (prevents duplicate accounts), not an oracle exposed to a low-trust actor. Fix: `clean_new_email` no longer checks whether the email is taken; the view always shows the same "Code sent" message and redirect regardless, only actually generating/sending a real code when the address is genuinely free. Also closed a residual leak in `EmailChangeCodeForm.clean_code` (a missing code-hash used to say "No code has been sent yet" - distinguishable from "Incorrect code" - now both cases behave identically, same lockout bookkeeping). 6 new tests in `accounts/tests.py:EmailChangeTests`, full suite 224 passing.
- [x] FR-AUTH-05: account lockout after 5 failed login attempts - fixed 2026-08-23. `User` gained `failed_login_attempts`/`login_locked_until` (same shape as the existing PIN/email-change lockouts, `LOGIN_MAX_ATTEMPTS=5`/`LOGIN_LOCKOUT_MINUTES=15`), checked/incremented in `accounts.auth_backends.LenientUsernameBackend.authenticate()`. A correct password on an inactive account doesn't count as a failed attempt. Found and fixed a real bypass along the way: `AUTHENTICATION_BACKENDS` had a second `django.contrib.auth.backends.ModelBackend` entry that Django silently falls through to whenever the first backend returns `None` - since that backend has no lockout awareness, a locked-out exact-username login was succeeding through the fallback anyway. Removing that entry initially broke logins for any username containing punctuation (e.g. a manually-created `/admin/` staff account like "j.smith") - `LenientUsernameBackend`'s regex strips punctuation from what's *typed* before matching, but a stored username can legitimately still contain it, so the stripped form never matched. Real fix: the backend's lookup now also matches the exact-as-typed username, not just the stripped form, making it a genuine superset instead of relying on the second backend to catch what it missed. 6 new tests in `accounts/tests.py:LoginLockoutTests` plus a regression test for the punctuation case, full suite 230 passing.
