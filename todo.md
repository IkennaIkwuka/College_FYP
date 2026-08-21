- [x] Add a filter in [Manage students] to filter by level,dept,

- [ ] Bursar / Fees module - role and dashboard exist, no functional fee features built
- [ ] Course registration approval workflow - currently pure self-service, no Advisor/HOD/Faculty Board approval step, no unit-load exception path, Dean has no approval capability
- [ ] Results / grades / CGPA system - foundational gap, needed for correct current_level, probation, carryover tracking; must use NUC's real 5-point scale (A=5..F=0), not a 4.0 GPA
- [ ] Carryover-student handling (depends on Results system above) - no tracking of failed/repeated courses, no NUC max-duration (~1.5x programme length) withdrawal enforcement
- [ ] Staff qualification tracking - no field records highest qualification, so HOD/Dean appointments can't be checked against NUC's practical PhD expectation
- [ ] Superuser vs IT Admin identity/dashboard separation - deferred mid-discussion, never decided between a label-only fix and a fully separate dashboard

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
