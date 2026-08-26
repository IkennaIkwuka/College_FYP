# System Design Document (SDD)

## Design and Implementation of a Secure University Information Management Portal with Role-Based Access Control Using Python

**Institution:** Legacy University, Okija, Anambra State, Nigeria
**Faculty:** Natural and Applied Sciences
**Department:** Computer Science
**Document Version:** 1.0
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

---

## 1. Introduction

### 1.1 Purpose

This document describes the system architecture, database schema, module breakdown, and design decisions for the Legacy University Information Management Portal. It serves as the technical blueprint guiding implementation, translating the requirements in the SRS into a concrete Django design.

### 1.2 Scope

The SDD covers:
- Overall system architecture (MVT pattern)
- Django app/module structure
- Database entity-relationship design
- RBAC permission matrix
- Security implementation design
- UI layout per role

### 1.3 Design Goals

- Enforce least-privilege access at every layer
- Keep RBAC logic centralized and reusable (decorators/middleware)
- Maintain clean separation between apps (student, registrar, finance, etc.)
- Make the schema extensible without breaking existing role assignments

---

## 2. System Architecture

The system follows Django's **Model-View-Template (MVT)** architecture:

- **Model layer** — defines the 12-table schema (Section 4) and encapsulates all data-access logic through the Django ORM.
- **View layer** — handles requests, applies the `@permission_required` decorator before any business logic executes, and returns rendered templates or redirects.
- **Template layer** — role-specific dashboards built on a shared Bootstrap 5 base template, so navigation and styling stay consistent while content varies by role.

**Request flow:**

1. Request arrives at Django's URL dispatcher.
2. Django's authentication middleware confirms the session is valid; unauthenticated requests are redirected to login.
3. The view's `@permission_required` decorator checks the user's role against the permission required for that route.
4. If authorized, the view executes and renders the appropriate template. If not, the request is denied and logged (FR-LOG-03).

This keeps permission enforcement in one place — the decorator — rather than scattered through templates or views, so every route's access rule is auditable in a single pass over the codebase.

---

## 3. Project Structure

The portal is organized into **nine Django apps**, each owning one bounded area of functionality:

| App | Responsibility |
|---|---|
| `accounts` | Authentication, user model, login/logout, session handling |
| `rbac` | Role and permission definitions, the `@permission_required` decorator, audit logging hooks |
| `students` | Student profile, course registration, results viewing, transcript requests |
| `registrar` | Academic record management, transcript approval and generation |
| `finance` | Fee records, payment status, Bursar operations |
| `department` | HOD course management and result approval |
| `faculty` | Dean-level read-only reporting across departments |
| `itadmin` | User account management, audit log review |
| `core` | Shared base templates, navigation, dashboard routing by role |

This mirrors the seven role modules from the SRS, with `rbac` and `core` as cross-cutting apps that every role-specific app depends on.

---

## 4. Database Design

**12-table schema:**

| # | Table | Purpose |
|---|---|---|
| 1 | `users` | Core user account: username, hashed password, role FK, status |
| 2 | `roles` | The seven defined roles (Student, Registrar, Bursar, HOD, Dean, IT Admin, Super Admin) |
| 3 | `permissions` | The 21-permission catalog (Section 5) |
| 4 | `role_permissions` | Many-to-many join between `roles` and `permissions` |
| 5 | `departments` | Department name, code, assigned HOD |
| 6 | `students` | Student profile: matriculation number, department FK, level, user FK |
| 7 | `courses` | Course code, title, unit load, department FK |
| 8 | `course_registrations` | Student FK, course FK, semester, session |
| 9 | `results` | Student FK, course FK, score, grade, approval status |
| 10 | `fee_records` | Student FK, session, amount due, amount paid, status |
| 11 | `transcript_requests` | Student FK, request date, status, processed-by FK |
| 12 | `audit_logs` | User FK, action, target table/record, timestamp, outcome (allowed/denied) |

**Key relationships:**

- `users` 1—1 `students` (a student account extends the base user record)
- `roles` M—M `permissions` through `role_permissions`
- `departments` 1—M `courses`, `courses` M—M `students` through `course_registrations`
- `students` 1—M `results`, `fee_records`, `transcript_requests`
- Every write to a sensitive table is mirrored into `audit_logs`

---

## 5. RBAC Design

**21-permission matrix across seven role modules.** Permissions follow the pattern `<module>.<action>` (e.g., `student.register_course`, `registrar.approve_transcript`).

| Role | Representative permissions | Count |
|---|---|---|
| Student | `student.view_profile`, `student.register_course`, `student.view_results`, `student.request_transcript` | 4 |
| Registrar | `registrar.view_records`, `registrar.edit_records`, `registrar.approve_transcript`, `registrar.generate_transcript` | 4 |
| Bursar | `finance.view_fees`, `finance.update_fee_status`, `finance.record_payment` | 3 |
| HOD | `department.manage_courses`, `department.approve_results`, `department.view_enrollment` | 3 |
| Dean | `faculty.view_reports`, `faculty.view_registration_stats` | 2 |
| IT Admin | `itadmin.manage_accounts`, `itadmin.view_audit_logs` | 2 |
| Super Admin | `superadmin.manage_roles`, `superadmin.manage_permissions`, `superadmin.view_all` | 3 |

(7 + 4 + 4 + 3 + 3 + 2 + 2 = the remaining permissions cover shared/base actions such as `core.login` and `core.view_dashboard`, bringing the total to 21.)

**Enforcement:** the `@permission_required('permission.code')` decorator wraps every view. It checks the current user's role against `role_permissions` on each request — no permission is cached client-side, satisfying FR-RBAC-06.

---

## 6. Module Design

Each app follows the same internal layout: `models.py`, `views.py`, `urls.py`, `templates/<app_name>/`, and where relevant `forms.py`. The `rbac` app additionally exposes `decorators.py` (the `@permission_required` decorator) and `middleware.py` (denied-access logging), which every other app imports rather than reimplementing.

---

## 7. Interface Design

Each role lands on a dashboard template extending a shared `core/base.html`, so the navigation bar, footer, and color scheme stay consistent while the sidebar menu and main content panel are populated per role:

- **Student dashboard** — profile summary, registered courses, results, fee balance, transcript request status
- **Registrar dashboard** — search bar for student records, pending transcript requests queue
- **Bursar dashboard** — fee status table with filter by paid/outstanding
- **HOD dashboard** — department course list, pending result approvals
- **Dean dashboard** — read-only faculty performance charts
- **IT Admin dashboard** — user account table, audit log search
- **Super Admin dashboard** — role and permission matrix editor

---

## 8. Security Design

- Passwords hashed with bcrypt (Django's default PBKDF2 or a configured bcrypt backend) — never stored in plaintext.
- CSRF tokens on every form via Django's built-in CSRF middleware.
- Session expiry after 30 minutes of inactivity (FR-AUTH-06).
- Account lockout after 5 failed login attempts (FR-AUTH-05).
- All permission checks enforced server-side in the view layer, never trusted from the client.
- Every create/update/delete on academic or financial data, and every denied access attempt, is written to `audit_logs` and is immutable once written.

---

## 9. Technology Stack

| Layer | Choice |
|---|---|
| Backend framework | Python 3.10+, Django 4.2 LTS |
| Database (dev) | SQLite |
| Database (production-ready) | PostgreSQL |
| Frontend | HTML5, CSS3, Bootstrap 5 |
| Authentication | Django's built-in session framework, extended with the custom RBAC layer |
| Password hashing | bcrypt |

---

*Document prepared as part of Final Year Project — Legacy University, Okija, Anambra State, Nigeria. 2026.*
