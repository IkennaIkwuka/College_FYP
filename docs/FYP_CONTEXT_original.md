# FYP Project Context — University Information Management Portal

## Project Identity

- **Title:** Design and Implementation of a Secure University Information Management Portal with Role-Based Access Control Using Python
- **Institution:** Legacy University, Okija, Anambra State, Nigeria — Faculty of Natural and Applied Sciences, Department of Computer Science. Established 2016, located on the Onitsha-Owerri Expressway. The university currently has no functional student/admin portal (all processes are manual), which is the problem the project addresses.

## Tech Stack (final, confirmed — do not swap without discussion)

- Python 3.10+
- Django 4.2 LTS (MVT pattern)
- Django ORM and Django Templates
- Password hashing: PBKDF2 / django-bcrypt
- Frontend: HTML5, CSS3, Bootstrap 5.3
- Database: SQLite for dev, PostgreSQL 15 for prod-ready deployment
- Git for version control
- requirements.txt includes: django-bcrypt, python-dotenv, psycopg2-binary, whitenoise, gunicorn

Flask and PHP/Laravel were both considered and rejected in favor of Django, mainly for its built-in auth/permissions framework.

## Architecture

Nine Django apps: `config`, `core`, `accounts`, `students`, `registrar`, `finance`, `hod`, `dean`, `itadmin`, `superadmin`.

### Database schema (14 tables)
`auth_user`, `accounts_userprofile`, `core_role`, `core_permission`, `core_rolepermission`, `core_department`, `core_faculty`, `students_student`, `students_courseregistration`, `academics_course`, `academics_result`, `finance_feerecord`, `registrar_transcriptrequest`, `core_auditlog`

### RBAC
- 21-permission matrix
- Enforced via a custom `@permission_required(codename)` decorator in `core/decorators.py`
- Session timeout: 30 minutes, via `SessionTimeoutMiddleware` in `core/middleware.py`
- Audit logging via `core.audit.log_action()`, writing to an append-only `core_auditlog` table

### Roles (7 total)
Student, Registrar, Bursar/Finance Officer, Head of Department (HOD), Dean, IT Administrator, Super Administrator

### Scope
40+ functional requirements across the 9 modules, 14 documented use cases.

## Documents Already Completed

- **SRS** (Software Requirements Specification)
- **SDD** (Software Design Document)
- **Project Proposal** — partial; student name, matric number, and supervisor left as placeholders
- **Seminar report** — Word doc, ~18 pages, APA 7th edition, 6 verified references. Six chapters: Introduction, Literature Review, Methodology, Findings, Discussion, Conclusion, plus cover page, certification, acknowledgement, table of contents, and abstract. Methodology is literature-based only — no survey or primary data collected.
- **PowerPoint** — 12 slides, navy/gold/ice-blue color scheme
- **HOD project brief** — scoped to 4 in-scope modules
- **Journal article** — full version plus a condensed ~900-word, 3-page booklet version

As of the latest upload, the actual seminar report `.docx`, presentation `.pptx`, and HOD brief `.docx` files were recovered intact from a zip archive (`files__1_.zip`) — despite an earlier note in the project records claiming these files were permanently lost.

### Case studies
Restricted to Nigerian universities only: University of Nigeria Nsukka (UNN) and Covenant University, Ota.

### The 6 verified references (used throughout all written documents)
1. Ferraiolo & Kuhn (1992)
2. Sandhu et al. (1996)
3. Onashoga et al. (2014)
4. Saltzer & Schroeder (1975)
5. Laudon & Laudon (2020)
6. Stallings & Brown (2018)

## Writing Rules (apply to any prose deliverable — seminar report, HOD brief, journal article, etc.)

- Never use the word "demo" anywhere — frame it as "focused deliverable" instead
- No em dashes in any writing
- Seminar report, HOD brief, and journal article must read as human-authored, not AI-generated: vary sentence rhythm and paragraph length, avoid uniform "rule of three" lists, avoid repeated bullet formatting, avoid tidy aphoristic wrap-up sentences, avoid uniformly polished depth throughout, use occasional contractions, no meta-references to how the document was produced

## Implementation Status

As of the last handoff: environment setup and Django app creation were instructed but not yet confirmed executed. `settings.py`, `.env`, models, the RBAC engine, and all role-specific modules have not yet been started.

## Environment

- Development machine: Kubuntu (native dual-boot on a Lenovo LOQ 15AHP10)
- Editor: VS Code
