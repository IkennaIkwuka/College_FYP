# Software Requirements Specification (SRS)

## Design and Implementation of a Secure University Information Management Portal with Role-Based Access Control Using Python

**Institution:** Legacy University, Okija, Anambra State, Nigeria
**Faculty:** Natural and Applied Sciences
**Department:** Computer Science
**Document Version:** 1.0
**Date:** 2026

---

## Table of Contents

1. [Introduction](#1-introduction)
2. [Overall Description](#2-overall-description)
3. [Functional Requirements](#3-functional-requirements)
4. [Non-Functional Requirements](#4-non-functional-requirements)
5. [System Constraints](#5-system-constraints)
6. [External Interface Requirements](#6-external-interface-requirements)
7. [Use Case Summary](#7-use-case-summary)
8. [Assumptions and Dependencies](#8-assumptions-and-dependencies)

---

## 1. Introduction

### 1.1 Purpose

This document specifies the software requirements for the **Legacy University Information Management Portal** — a web-based system designed to centralize academic and administrative operations at Legacy University, Okija, Anambra State, Nigeria.

### 1.2 Scope

The portal will provide role-specific access to academic records, course registration, fee records, transcript processing, and departmental administration. Access to every feature is governed by a Role-Based Access Control (RBAC) layer, so that each user sees and can act on only what their role permits.

### 1.3 Definitions and Acronyms

| Term | Meaning |
|---|---|
| RBAC | Role-Based Access Control |
| MVT | Model-View-Template (Django's architectural pattern) |
| CRUD | Create, Read, Update, Delete |
| HOD | Head of Department |
| CSRF | Cross-Site Request Forgery |
| FR | Functional Requirement |

### 1.4 Intended Audience

This document is intended for the project supervisor, examiners, and any future developer extending the portal beyond its current scope.

---

## 2. Overall Description

### 2.1 Product Perspective

The portal is a new, standalone system. Legacy University currently operates only a public informational website with no functional student or staff portal, so this system introduces the institution's first centralized digital records platform.

### 2.2 User Roles

| Role | Description |
|---|---|
| Student | Views academic records, registers courses, checks results and fees |
| Registrar | Manages student academic records and transcript processing |
| Bursar / Finance Officer | Manages fee records and payment status |
| Head of Department (HOD) | Manages departmental courses and approves results |
| Dean | Views faculty-wide academic performance reports |
| IT Administrator | Manages user accounts and reviews audit logs |
| Super Admin | Defines roles and permissions; full system oversight |

### 2.3 Operating Environment

- Server-side: Python 3.10+, Django 4.2 LTS
- Database: SQLite for development, PostgreSQL-ready for production
- Client-side: any modern desktop web browser (Chrome, Firefox, Edge)
- Frontend: HTML5, CSS3, Bootstrap 5

---

## 3. Functional Requirements

### 3.1 Authentication Module

| ID | Requirement |
|---|---|
| FR-AUTH-01 | The system shall allow users to log in using a unique username and password |
| FR-AUTH-02 | The system shall hash all passwords using bcrypt before storage |
| FR-AUTH-03 | The system shall issue a session token upon successful login |
| FR-AUTH-04 | The system shall invalidate the session token upon logout |
| FR-AUTH-05 | The system shall lock an account after 5 consecutive failed login attempts |
| FR-AUTH-06 | The system shall enforce session expiry after 30 minutes of inactivity |
| FR-AUTH-07 | The system shall redirect unauthenticated users to the login page |

### 3.2 Role-Based Access Control Module

| ID | Requirement |
|---|---|
| FR-RBAC-01 | Each user shall be assigned exactly one role at account creation |
| FR-RBAC-02 | Each role shall have a defined set of permissions |
| FR-RBAC-03 | The system shall deny access to any route not permitted by the user's role |
| FR-RBAC-04 | Super Admin shall be the only role able to create, modify, or delete roles and permissions |
| FR-RBAC-05 | The system shall display only the navigation items and actions permitted for the logged-in user's role |
| FR-RBAC-06 | Permission checks shall be enforced server-side; client-side hiding is cosmetic only |

### 3.3 Student Module

| ID | Requirement |
|---|---|
| FR-STU-01 | Students shall be able to view their personal academic profile |
| FR-STU-02 | Students shall be able to register for available courses each semester |
| FR-STU-03 | Students shall be able to view published results for registered courses |
| FR-STU-04 | Students shall be able to view their current fee balance |
| FR-STU-05 | Students shall be able to submit a transcript request to the Registrar |
| FR-STU-06 | Students shall only be able to view and edit their own records, never another student's |

### 3.4 Registrar Module

| ID | Requirement |
|---|---|
| FR-REG-01 | The Registrar shall be able to view and update student academic records |
| FR-REG-02 | The Registrar shall be able to approve or reject transcript requests |
| FR-REG-03 | The Registrar shall be able to generate an official transcript document per approved request |
| FR-REG-04 | The Registrar shall be able to search student records by name or matriculation number |
| FR-REG-05 | The Registrar shall not be able to modify fee records or user roles |

### 3.5 Bursar / Finance Module

| ID | Requirement |
|---|---|
| FR-FIN-01 | The Bursar shall be able to mark a student's fee record as paid or outstanding |
| FR-FIN-02 | The Bursar shall be able to view a summary of fee payment status across all students |
| FR-FIN-03 | The Bursar shall be able to record partial payments against a student's fee balance |
| FR-FIN-04 | The system shall log every fee record change with a timestamp and the acting user's ID |

### 3.6 Head of Department (HOD) Module

| ID | Requirement |
|---|---|
| FR-HOD-01 | The HOD shall be able to add, edit, or deactivate courses within their department |
| FR-HOD-02 | The HOD shall be able to review and approve results submitted for their department before publication |
| FR-HOD-03 | The HOD shall be able to view enrollment statistics for departmental courses |
| FR-HOD-04 | The HOD shall not be able to approve results for courses outside their department |

### 3.7 Dean Module

| ID | Requirement |
|---|---|
| FR-DEAN-01 | The Dean shall be able to view academic performance reports across all departments in their faculty |
| FR-DEAN-02 | The Dean shall be able to view aggregate course registration statistics per department |
| FR-DEAN-03 | The Dean's access shall be read-only; the Dean role shall not be able to edit student or course records |

### 3.8 IT Administrator Module

| ID | Requirement |
|---|---|
| FR-ITA-01 | The IT Administrator shall be able to create, suspend, or reset user accounts |
| FR-ITA-02 | The IT Administrator shall be able to assign a role to a newly created account |
| FR-ITA-03 | The IT Administrator shall be able to search and filter system audit logs |
| FR-ITA-04 | The IT Administrator shall not be able to define new roles or permissions |

### 3.9 Super Admin Module

| ID | Requirement |
|---|---|
| FR-SA-01 | The Super Admin shall be able to define new roles |
| FR-SA-02 | The Super Admin shall be able to assign or revoke permissions for any role |
| FR-SA-03 | The Super Admin shall have unrestricted read access to all system modules |
| FR-SA-04 | The Super Admin shall be able to view a complete history of role and permission changes |

### 3.10 Audit Logging Module

| ID | Requirement |
|---|---|
| FR-LOG-01 | The system shall log every login attempt, successful or failed, with a timestamp |
| FR-LOG-02 | The system shall log every create, update, or delete action on academic or financial records |
| FR-LOG-03 | The system shall log every denied access attempt, including the user, route, and reason |
| FR-LOG-04 | Audit logs shall be viewable only by the IT Administrator and Super Admin roles |
| FR-LOG-05 | Audit logs shall be immutable — no role shall be able to edit or delete a log entry |

---

## 4. Non-Functional Requirements

| Category | Requirement |
|---|---|
| Performance | The system shall load any dashboard page within 2 seconds under normal load |
| Security | All passwords shall be stored hashed; all forms shall be CSRF-protected |
| Usability | The interface shall be navigable without training, using consistent layout across role dashboards |
| Reliability | The system shall handle invalid input gracefully without exposing stack traces to end users |
| Maintainability | The codebase shall follow Django's app-per-module convention to keep concerns separated |
| Scalability | The database layer shall be swappable from SQLite to PostgreSQL without application-code changes |
| Portability | The system shall run on any platform supporting Python 3.10+ and a WSGI-compatible server |

---

## 5. System Constraints

- The system is developed and demonstrated using SQLite; production deployment would require migration to PostgreSQL and institutional server infrastructure.
- The project timeline and single-developer scope limit the implementation to four in-scope modules (see Section 7 and the accompanying project brief) rather than the full 7-role, 9-app specification.
- No third-party payment gateway (e.g., Remita, Paystack) is integrated; fee status is recorded manually by the Bursar role.
- The system is browser-based only; no native mobile application is in scope.

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
| UC-01: Login | All users | Authenticate with username and password |
| UC-02: View dashboard | All users | View role-specific landing page |
| UC-03: Register courses | Student | Select and register courses for current semester |
| UC-04: View results | Student | View published academic results |
| UC-05: Request transcript | Student | Submit a transcript request to the Registrar |
| UC-06: Manage student records | Registrar | CRUD operations on student academic records |
| UC-07: Process transcript | Registrar | Approve or reject a student's transcript request |
| UC-08: Update fee record | Bursar | Mark student fees as paid or outstanding |
| UC-09: Manage courses | HOD | Add, edit, or deactivate departmental courses |
| UC-10: Approve results | HOD | Review and approve results before publication |
| UC-11: View faculty reports | Dean | View academic performance across departments |
| UC-12: Manage user accounts | IT Admin | Create, suspend, or reset user accounts |
| UC-13: View audit logs | IT Admin / Super Admin | Search and filter system activity logs |
| UC-14: Manage roles | Super Admin | Define and assign roles and permissions |

---

## 8. Assumptions and Dependencies

### 8.1 Assumptions

- Each user will have a unique institutional identifier (student number or staff ID) used as their login username.
- All users have access to a computer and a modern web browser.
- The institution will provide a dedicated server environment for production deployment.
- Student and staff data will be seeded into the system manually by the IT Administrator at initial setup.

### 8.2 Dependencies

- Python 3.10 or higher installed on the development and production machine
- Django and all listed dependencies installable via pip
- A running SQLite (development) or PostgreSQL (production-ready) instance for data persistence
- Bootstrap 5 CDN accessible, or served locally for offline use

---

*Document prepared as part of Final Year Project — Legacy University, Okija, Anambra State, Nigeria. 2026.*
