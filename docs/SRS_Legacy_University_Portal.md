# Software Requirements Specification (SRS)

## Design and Implementation of a Secure University Information Management Portal with Role-Based Access Control Using Python

**Institution:** Legacy University, Okija, Anambra State, Nigeria
**Faculty:** Natural and Applied Sciences
**Department:** Computer Science
**Document Version:** 2.0 — reconciled to the as-built system
**Date:** 2026

---

## Table of Contents

1. [Introduction](#1-introduction)
2. [Overall Description](#2-overall-description)
3. [Functional Requirements](#3-functional-requirements)
4. [Non-Functional Requirements](#4-non-functional-requirements)
5. [System Constraints and Scope Evolution](#5-system-constraints-and-scope-evolution)
6. [External Interface Requirements](#6-external-interface-requirements)
7. [Use Case Summary](#7-use-case-summary)
8. [Assumptions and Dependencies](#8-assumptions-and-dependencies)

---

## 1. Introduction

### 1.1 Purpose

This document specifies the software requirements for the **Legacy University Information Management Portal** — a web-based system designed to centralize academic and administrative operations at Legacy University, Okija, Anambra State, Nigeria.

### 1.2 Scope

The portal provides role-specific access to academic records, course registration, and results, governed by a Role-Based Access Control (RBAC) layer so each user sees and can act on only what their role permits.

### 1.3 Definitions and Acronyms

| Term | Meaning |
|---|---|
| RBAC | Role-Based Access Control |
| MVT | Model-View-Template (Django's architectural pattern) |
| CRUD | Create, Read, Update, Delete |
| HOD | Head of Department |
| CSRF | Cross-Site Request Forgery |
| FR | Functional Requirement |
| NUC | National Universities Commission (Nigeria) |
| GPA/CGPA | Grade Point Average / Cumulative Grade Point Average |

### 1.4 Intended Audience

This document is intended for the project supervisor, examiners, and any future developer extending the portal beyond its current scope.

---

## 2. Overall Description

### 2.1 Product Perspective

The portal is a new, standalone system. Legacy University currently operates only a public informational website with no functional student or staff portal, so this system introduces the institution's first centralized digital records platform.

### 2.2 User Roles

| Role | Description |
|---|---|
| Student | Views academic profile, registers for courses, checks results/GPA |
| Lecturer | Manages assigned courses, enters and updates results |
| Registrar | Manages student records, registers new students, bulk imports |
| Bursar | Login role reserved for fee management; no fee-record features are implemented yet (see Section 5) |
| Head of Department (HOD) | Manages departmental courses |
| Dean | Views faculty-scoped course information |
| IT Admin | Manages staff accounts, departments, and faculties; superuser access folds into this role rather than a separate Super Admin role |

### 2.3 Operating Environment

- Server-side: Python 3.14, Django 6.0.6
- Database: SQLite (the only database target — no PostgreSQL configuration exists)
- Client-side: any modern desktop web browser (Chrome, Firefox, Edge)
- Frontend: HTML5, CSS3, Bootstrap 5.3

---

## 3. Functional Requirements

### 3.1 Authentication Module

| ID | Requirement |
|---|---|
| FR-AUTH-01 | The system shall allow users to log in using a unique username and password |
| FR-AUTH-02 | The system shall hash all passwords using Django's PBKDF2 hasher before storage |
| FR-AUTH-03 | The system shall issue a session token upon successful login |
| FR-AUTH-04 | The system shall invalidate the session token upon logout |
| FR-AUTH-05 | The system shall lock an account after 5 consecutive failed login attempts, for a 15-minute cooldown |
| FR-AUTH-06 | The system shall enforce session expiry after 15 minutes of inactivity |
| FR-AUTH-07 | The system shall redirect unauthenticated users to the login page |
| FR-AUTH-08 | New students shall complete first login via an emailed PIN rather than a shared initial password; the PIN is subject to the same 5-attempt lockout as FR-AUTH-05 |
| FR-AUTH-09 | New staff accounts shall complete first login via an emailed setup link, then be forced to set their own password |
| FR-AUTH-10 | Users shall be able to self-service a forgotten password, a voluntary password change, and an email address change, each protected by its own attempt-limited verification code |

### 3.2 Role-Based Access Control Module

| ID | Requirement |
|---|---|
| FR-RBAC-01 | Each user shall be assigned to one or more Django Groups representing their role(s) at account creation |
| FR-RBAC-02 | Each protected view shall be wrapped in a decorator that checks the current user's role |
| FR-RBAC-03 | The system shall deny access (403) to any route not permitted for the user's role |
| FR-RBAC-04 | IT Admin shall be the only role able to create and manage staff accounts, departments, and faculties |
| FR-RBAC-05 | The system shall display only the navigation items and actions permitted for the logged-in user's role |
| FR-RBAC-06 | Permission checks shall be enforced server-side, in the decorator; client-side hiding is cosmetic only |

### 3.3 Student Module

| ID | Requirement |
|---|---|
| FR-STU-01 | Students shall be able to view their personal academic profile |
| FR-STU-02 | Students shall be able to register for available courses each semester |
| FR-STU-03 | Students shall be able to view published results and computed GPA/CGPA for registered courses |
| FR-STU-04 | Students shall be able to set a preferred username and update self-service account details |
| FR-STU-05 | Students shall only be able to view and edit their own records, never another student's |

### 3.4 Registrar Module

| ID | Requirement |
|---|---|
| FR-REG-01 | The Registrar shall be able to register new students, individually or via bulk import |
| FR-REG-02 | The Registrar shall be able to view and edit student profile records (name, email, and related fields) |
| FR-REG-03 | The Registrar shall be able to search student records with live/typeahead lookup by name or matriculation number |
| FR-REG-04 | The Registrar shall not be able to modify fee records or user roles |

### 3.5 Bursar Module (descoped)

The Bursar role exists as a real login role with its own dashboard, but no fee-record functionality is implemented behind it — there is no Fee model, and the dashboard currently renders no data. This module was never carried past the login/RBAC layer; see Section 5 for why.

### 3.6 Head of Department (HOD) and Lecturer Modules

| ID | Requirement |
|---|---|
| FR-HOD-01 | The HOD shall be able to add, edit, or deactivate courses within their department |
| FR-HOD-02 | Course level shall be validated against the department's programme duration (e.g. a 4-year department cannot have a 500-level course) |
| FR-LEC-01 | A Lecturer assigned to a course shall be able to enter and update student results for that course |
| FR-LEC-02 | Result scores shall be validated to 0-100 and automatically graded on the NUC 5-point scale (A-F, grade points 5 down to 0) |

### 3.7 Dean Module

| ID | Requirement |
|---|---|
| FR-DEAN-01 | The Dean shall be able to view courses across departments in their faculty |
| FR-DEAN-02 | The Dean's access shall be read-only for course and student data |

### 3.8 IT Admin Module

| ID | Requirement |
|---|---|
| FR-ITA-01 | The IT Admin shall be able to create, edit, and manage staff accounts (Lecturer, HOD, Registrar, Bursar, Dean, IT Admin) |
| FR-ITA-02 | The IT Admin shall be able to assign a role (Django Group) to a staff account |
| FR-ITA-03 | The IT Admin shall be able to create and manage Faculties and Departments |
| FR-ITA-04 | There is no separate role/permission-definition capability beyond assigning an account to one of the fixed Django Groups — this is a deliberate simplification from the original design (see Section 5) |

### 3.9 Audit Logging (descoped)

No audit logging exists in the current build. The original design specified a full audit trail (every login, every create/update/delete, every denied access attempt); this was not implemented. See Section 5.

---

## 4. Non-Functional Requirements

| Category | Requirement |
|---|---|
| Performance | The system shall load any dashboard page within 2 seconds under normal load |
| Security | All passwords shall be stored hashed (PBKDF2); all forms shall be CSRF-protected |
| Usability | The interface shall be navigable without training, using consistent layout across role dashboards |
| Reliability | The system shall handle invalid input gracefully without exposing stack traces to end users |
| Maintainability | The codebase shall follow Django's app-per-module convention to keep concerns separated |
| Portability | The system shall run on any platform supporting Python 3.10+ and a WSGI-compatible server |

---

## 5. System Constraints and Scope Evolution

### 5.1 Constraints

- The system is developed and runs on SQLite only; there is no PostgreSQL configuration and no plan to add one within this project's scope.
- No third-party payment gateway is integrated; a fee module was never started.
- The system is browser-based only; no native mobile application is in scope.
- The project timeline and single-developer scope limited the implementation to four in-scope modules, as originally set out in the accompanying HOD project brief.

### 5.2 Scope evolution from the original design

The original design (developed early in the project, before implementation began) specified a 9-app architecture, a database-driven 21-permission matrix across the 7 role modules, and a full audit-logging subsystem. During implementation this was simplified:

- RBAC enforcement moved from a generic `@permission_required(codename)` decorator reading a `roles`/`permissions`/`role_permissions` matrix to a set of hardcoded per-role decorators (`admin_required`, `student_required`, etc.), each checking one boolean property on the user. This was faster to build and easier to reason about for a fixed, small set of roles, at the cost of not being data-driven — adding a new permission means adding a new decorator rather than a database row.
- Audit logging was dropped entirely for time/scope reasons. It remains a natural extension (see the seminar report / HOD brief's "future potential" framing) but nothing in the current build writes to any kind of activity log.
- The Fee/Finance and Transcript-request modules were never started. The Bursar role exists at the login/RBAC layer only.
- The originally-scoped Attendance module was replaced with a Results/Grading module (NUC 5-point-scale GPA/CGPA) — a more central academic-record feature that better demonstrates the RBAC model across the Student, Lecturer, and HOD roles.
- A Lecturer role was added, which was not part of the original 7-role list, to own result entry separately from HOD course management.
- The app count dropped from the originally-planned 9 (`config`, `core`, `accounts`, `students`, `registrar`, `finance`, `hod`, `dean`, `itadmin`, `superadmin`) to 4 (`accounts`, `students`, `courses`, `results`), since most of the originally-separate apps turned out to be thin enough to fold into `accounts` or `students` without losing separation of concerns.

---

## 6. External Interface Requirements

### 6.1 User Interfaces

Each role has a dedicated dashboard displaying only the navigation items and widgets relevant to that role, built with Bootstrap 5 for consistent, responsive layout.

### 6.2 Hardware Interfaces

No special hardware is required beyond a standard computer capable of running a modern web browser.

### 6.3 Software Interfaces

The system interfaces with the Django ORM for all database operations and relies on Django's built-in session framework for authentication state.

### 6.4 Communication Interfaces

All communication occurs over standard HTTP/HTTPS between the client browser and the Django application server.

---

## 7. Use Case Summary

| Use Case | Actor(s) | Description |
|---|---|---|
| UC-01: Login | All users | Authenticate with username/password, or PIN for a student's first login |
| UC-02: View dashboard | All users | View role-specific landing page |
| UC-03: Register courses | Student | Select and register courses for current semester |
| UC-04: View results | Student | View published results and computed GPA/CGPA |
| UC-05: Self-service account | Student, staff | Set preferred username, change password, change email, recover a forgotten password |
| UC-06: Register/manage students | Registrar | Add students individually or via bulk import, edit profile records |
| UC-07: Search student records | Registrar | Live/typeahead lookup by name or matriculation number |
| UC-08: Manage courses | HOD | Add, edit, or deactivate departmental courses |
| UC-09: Enter results | Lecturer | Enter and update scores for an assigned course; grade computed automatically |
| UC-10: View faculty courses | Dean | Read-only view of courses across departments in their faculty |
| UC-11: Manage staff accounts | IT Admin | Create and manage staff accounts, assign roles |
| UC-12: Manage faculties/departments | IT Admin | Create and manage Faculty and Department records |

---

## 8. Assumptions and Dependencies

### 8.1 Assumptions

- Each user has a unique institutional identifier (matriculation number for students, a generated staff ID for staff) used as their login username, with an optional self-chosen preferred username as a second login credential.
- All users have access to a computer and a modern web browser.
- Student and staff accounts are created by the Registrar or IT Admin respectively — there is no public self-registration flow.

### 8.2 Dependencies

- Python 3.10 or higher installed on the development machine
- Django and the packages listed in requirements.txt, installable via pip
- A running SQLite database file for data persistence
- Bootstrap 5 CDN accessible, or served locally for offline use

---

*Document prepared as part of Final Year Project — Legacy University, Okija, Anambra State, Nigeria. 2026.*
