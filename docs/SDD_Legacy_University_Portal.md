# System Design Document (SDD)

## Design and Implementation of a Secure University Information Management Portal with Role-Based Access Control Using Python

**Institution:** Legacy University, Okija, Anambra State, Nigeria
**Faculty:** Natural and Applied Sciences
**Department:** Computer Science
**Document Version:** 2.0 — reconciled to the as-built system
**Date:** 2026

---

## Table of Contents

1. [Introduction](#1-introduction)
2. [System Architecture](#2-system-architecture)
3. [Project Structure](#3-project-structure)
4. [Database Design](#4-database-design)
5. [RBAC Design](#5-rbac-design)
6. [Module Design](#6-module-design)
7. [Interface Design](#7-interface-design)
8. [Security Design](#8-security-design)
9. [Technology Stack](#9-technology-stack)
10. [Scope Evolution from the Original Design](#10-scope-evolution-from-the-original-design)

---

## 1. Introduction

### 1.1 Purpose

This document describes the system architecture, database schema, module breakdown, and design decisions for the Legacy University Information Management Portal. It serves as the technical blueprint for the implementation, translating the requirements in the SRS into a concrete Django design.

### 1.2 Scope

The SDD covers:
- Overall system architecture (MVT pattern)
- Django app/module structure
- Database entity-relationship design
- RBAC enforcement mechanism
- Security implementation design
- UI layout per role

### 1.3 Design Goals

- Enforce least-privilege access at every layer
- Keep RBAC checks close to the view they guard, so each route's access rule is easy to audit by reading the view
- Maintain clean separation between apps
- Keep the schema simple enough for a single developer to maintain within the project timeline

---

## 2. System Architecture

The system follows Django's **Model-View-Template (MVT)** architecture:

- **Model layer** — defines the 8-table schema (Section 4) and encapsulates all data-access logic through the Django ORM.
- **View layer** — handles requests, applies a role-specific decorator (e.g. `@student_required`, `@admin_required`) before any business logic executes, and returns rendered templates or redirects.
- **Template layer** — role-specific dashboards built on a shared Bootstrap 5 base template, so navigation and styling stay consistent while content varies by role.

**Request flow:**

1. Request arrives at Django's URL dispatcher.
2. Django's authentication middleware confirms the session is valid; unauthenticated requests are redirected to login (FR-AUTH-07).
3. The view's `@<role>_required` decorator (from `accounts/decorators.py`) checks one boolean property on `request.user` (e.g. `is_student`) and raises `PermissionDenied` if it's false.
4. If authorized, the view executes and renders the appropriate template.

Each decorator wraps Django's own `login_required`, so the login check and the role check both happen before any view logic runs. There is no separate permission-lookup step against a database table — the check is a single attribute read on the user object.

---

## 3. Project Structure

The portal is organized into **four Django apps**, plus the project configuration package:

| App | Responsibility |
|---|---|
| `accounts` | Custom `User` model, authentication, role decorators, dashboards, staff/account management, self-service flows |
| `students` | Faculty, Department, and StudentProfile models; student registration, profile editing, lookup |
| `courses` | Course and CourseRegistration models; course management and semester registration |
| `results` | Result model and grading/GPA-CGPA services |
| `lu_sims` | Project settings, root URL configuration, shared ID-format helpers |

There is no separate `core`, `rbac`, `registrar`, `finance`, `department`, `faculty`, or `itadmin` app. Registrar-facing features live in `accounts`/`students`; HOD/Dean/Bursar dashboards live in `accounts`; the role decorators live in `accounts/decorators.py` rather than a standalone `rbac` app.

---

## 4. Database Design

**8-table schema:**

| # | Table | Purpose |
|---|---|---|
| 1 | `accounts_user` | Core user account: username, hashed password, staff_id, preferred_username, must_change_password, phone/gender, email (unique) |
| 2 | `accounts_staffidcounter` | Per-role-per-year sequence driving generated staff IDs (e.g. `LU-RG-26-0001`) |
| 3 | `students_faculty` | Faculty name and its Dean (one-to-one with `accounts_user`, limited to the Dean group) |
| 4 | `students_department` | Department name, programme duration in years, Faculty FK, HOD (one-to-one with `accounts_user`, limited to the HOD group) |
| 5 | `students_studentprofile` | Matriculation number, Department FK, entry level/session, admission type, PIN hash and lockout fields for passwordless first login |
| 6 | `courses_course` | Course code, title, unit load, Department FK, level, semester, Lecturer FK, active flag (soft-disable) |
| 7 | `courses_courseregistration` | Student FK, Course FK, session, semester (unique together, so a student can't double-register the same course in a term) |
| 8 | `results_result` | One-to-one with a registration; score, grade, grade_point (auto-derived on the NUC 5-point scale), entered-by FK, timestamps |

**Key relationships:**

- `accounts_user` 1—1 `students_studentprofile` (a student account extends the base user record)
- `accounts_user` 1—1 `students_faculty` (Dean) and 1—1 `students_department` (HOD)
- `students_department` 1—M `courses_course`; `students_studentprofile` M—M `courses_course` through `courses_courseregistration`
- `courses_courseregistration` 1—1 `results_result`

There is no generic `roles`/`permissions`/`role_permissions` schema and no `audit_logs` table — see Section 10.

---

## 5. RBAC Design

Roles are Django Groups: Student, Lecturer, HOD, Registrar, Bursar, Dean, IT Admin. `User` exposes a boolean property per role (`is_student`, `is_lecturer`, `is_hod`, `is_registrar`, `is_bursar`, `is_dean`, `is_admin`), each backed by `has_role(group_name)` — a membership check against the user's groups. `is_admin` additionally returns true for `is_superuser`, so there is no separate Super Admin role or group.

**Enforcement:** `accounts/decorators.py` defines one decorator per role (`admin_required`, `student_required`, `hod_required`, `lecturer_required`, `registrar_required`, `bursar_required`, `dean_required`). Each wraps `login_required`, then checks the matching `is_<role>` property and raises `PermissionDenied` (HTTP 403) if it's false. A view needing to accept more than one role stacks the relevant check inline rather than via a shared decorator, since the roster of multi-role views is small.

This is a fixed, code-defined mapping rather than a database-driven permission catalog — see Section 10 for why.

---

## 6. Module Design

Each app follows the same internal layout: `models.py`, `views.py`, `urls.py`, `templates/<app_name>/`, and `forms.py` where relevant. `accounts` additionally holds `decorators.py` (the role decorators, imported by every other app's views) and the auth backend/middleware for session timeout and login lockout.

---

## 7. Interface Design

Each role lands on a dashboard template extending a shared base template, so the navigation bar and layout stay consistent while the main content panel is populated per role:

- **Student dashboard** — profile summary, course registration, results/GPA-CGPA
- **Registrar dashboard** — student registration/bulk import, student search with live typeahead
- **HOD dashboard** — departmental course management
- **Lecturer dashboard** — assigned courses, result entry
- **Dean dashboard** — read-only view of courses across departments in their faculty
- **IT Admin dashboard** — staff account management, faculty/department management
- **Bursar dashboard** — currently a stub template with no data behind it; the fee module was never built (Section 10)

---

## 8. Security Design

- Passwords hashed with Django's default PBKDF2 hasher — never stored in plaintext.
- CSRF tokens on every form via Django's built-in CSRF middleware.
- Session idle timeout after 15 minutes of inactivity (FR-AUTH-06).
- Account lockout after 5 failed login attempts, 15-minute cooldown (FR-AUTH-05); the same attempt-limit/cooldown pattern is applied independently to student PIN entry and email-change verification codes.
- All permission checks enforced server-side in the view layer via the role decorators, never trusted from the client.
- SECRET_KEY and DEBUG are environment-driven with dev-safe defaults; HTTPS redirect and secure-cookie flags are gated behind `not DEBUG` so local HTTP development still works.
- No audit logging exists — see Section 10.

---

## 9. Technology Stack

| Layer | Choice |
|---|---|
| Backend framework | Python 3.14, Django 6.0.6 |
| Database | SQLite (only target — no PostgreSQL configuration) |
| Frontend | HTML5, CSS3, Bootstrap 5.3 |
| Authentication | Django's built-in session framework, extended with the custom role decorators |
| Password hashing | Django's default PBKDF2 |

---

## 10. Scope Evolution from the Original Design

The design that guided early planning specified a 9-app architecture, a database-driven 21-permission matrix across 7 role modules, and a full audit-logging subsystem. During implementation, this was simplified:

- **RBAC**: the planned `roles`/`permissions`/`role_permissions` schema and generic `@permission_required(codename)` decorator were replaced with the fixed per-role decorators described in Section 5. For a small, stable set of 7 roles this was simpler to build and verify than a data-driven matrix, at the cost of needing a code change (not a database row) to add a new permission.
- **Audit logging** was dropped for time/scope reasons. Nothing in the current build writes to any activity log; it remains a natural future extension.
- **Fee/Finance and Transcript-request modules** were never started. The Bursar role exists at the login/RBAC layer only, with a stub dashboard.
- **Attendance**, originally one of the four in-scope modules per the HOD project brief, was replaced with a **Results/Grading** module (NUC 5-point-scale GPA/CGPA), judged to demonstrate the RBAC model more centrally across the Student, Lecturer, and HOD roles.
- A **Lecturer** role/group was added, which was not part of the original 7-role list, to separate result entry from HOD course management.
- The app count dropped from 9 planned apps (`config`, `core`, `accounts`, `students`, `registrar`, `finance`, `hod`, `dean`, `itadmin`, `superadmin`) to the 4 actually built (`accounts`, `students`, `courses`, `results`) — several of the originally-separate apps turned out thin enough to fold into `accounts` or `students` without losing separation of concerns.
- The technology stack itself changed in places: Django 6.0.6 instead of 4.2 LTS, PBKDF2 instead of bcrypt, and SQLite-only instead of a Postgres-ready configuration.

---

*Document prepared as part of Final Year Project — Legacy University, Okija, Anambra State, Nigeria. 2026.*
