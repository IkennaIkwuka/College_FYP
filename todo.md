- [x] Add a filter in [Manage students] to filter by level,dept,

- [ ] Bursar / Fees module - role and dashboard exist, no functional fee features built
- [ ] Course registration approval workflow - currently pure self-service, no Advisor/HOD/Faculty Board approval step, no unit-load exception path, Dean has no approval capability
- [ ] Results / grades / CGPA system - foundational gap, needed for correct current_level, probation, carryover tracking; must use NUC's real 5-point scale (A=5..F=0), not a 4.0 GPA
- [ ] Carryover-student handling (depends on Results system above) - no tracking of failed/repeated courses, no NUC max-duration (~1.5x programme length) withdrawal enforcement
- [ ] Staff qualification tracking - no field records highest qualification, so HOD/Dean appointments can't be checked against NUC's practical PhD expectation
- [ ] Superuser vs IT Admin identity/dashboard separation - deferred mid-discussion, never decided between a label-only fix and a fully separate dashboard
- [ ] Auxiliary/informal staff designations (Exams Officer, Course/Level Adviser, SIWES Coordinator, etc.) - 2026-08-22 discussion: don't give these full RBAC treatment (new Group/decorator/dashboard/nav/ID-code) like the 7 core roles, since they're informal "hats" a Lecturer holds on top of their main role, not standardized structural offices, and there's no feature yet to gate by them. Model as a lightweight descriptive designation field on User first; only wire a real permission check once an actual feature (e.g. an Exams module) needs restricting to whoever holds it

From the 2026-08-21 project audit (SECRET_KEY/DEBUG/ALLOWED_HOSTS already fixed):
- [ ] SQLite -> real DB before deployment - needs an actual DB instance to point at, deliberately not picked yet
- [ ] LEVEL_CHOICES caps at 500, blocks 600L for 6-year departments (Medicine/Law/Engineering) - internal bug, not just NUC gap
- [ ] accounts/views.py imports from students (PIN flow) - breaks the one-directional app-dependency rule
- [ ] Test coverage: 6 JSON typeahead endpoints untested, resend_email_change_code untested, Faculty CRUD untested
- [ ] courses app has no services.py - registration logic inlined in views.py, will get worse once approval workflow lands
- [ ] DEFAULT_PASSWORD is one shared password for every new account - consider per-account random initial passwords instead
- [ ] Email-existence enumeration oracle in RequestEmailChangeForm/StaffAccountForm/StudentAccountForm clean_email
- [ ] Minor cleanup: unnecessary |safe on password help_text (3 templates), CSV bulk_import has no size/encoding guard, unused test vars in students/tests.py:248 and courses/tests.py:243
- [ ] Course-code semester-parity rule (odd/even = 1st/2nd sem) has no confirmed NUC source - unverified project convention, not urgent

Brainstormed features (2026-08-21), not yet scoped/prioritized:

Core academic - fits FYP scope, builds on Results system once it lands:
- [ ] Transcript generation (PDF) - once Results/CGPA exists
- [ ] Course prerequisite enforcement at registration time
- [ ] Add/drop deadline enforcement (registration window dates, not just CURRENT_SEMESTER flag)
- [ ] Graduation-eligibility checker - units completed + CGPA + no outstanding carryover
- [ ] Auto probation/warning flag from CGPA threshold - ties into Results

Bursar/Fees - expands the already-planned module:
- [ ] Fee schedule per department/level/session
- [ ] Record payments + generate receipts (internal ledger, not a payment gateway)
- [ ] Fee-clearance gate blocking registration on outstanding balance

Admin/records:
- [ ] Audit log - who changed what, on sensitive records (Registrar edits, staff force-reset, etc.)
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
