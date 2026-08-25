# College_FYP — LU-SIMS

Final year project for my Computer Science degree at Legacy University, Okija, Anambra State — a Role-Based Access Control (RBAC) information management portal built with Django.

This repo used to just hold a placeholder; the project lived inside the LegacyUniversityOkija coursework repo instead. Moved it here so it has its own home, separate from general coursework.

## Status

In active development. Four apps are built and working: authentication/staff accounts, student records, course management/registration, and results/GPA-CGPA. See `todo.md` for what's still open, including gaps against the project's own SRS/SDD/HOD-brief documentation.

## Apps

- `accounts` — authentication, the custom `User` model, role groups (Student/Lecturer/HOD/Registrar/Bursar/Dean/Admin), staff account management, profile self-service
- `students` — student profiles, faculties/departments, registrar-facing student CRUD, bulk CSV import
- `courses` — course catalog, HOD-managed course CRUD, student course registration
- `results` — lecturer/HOD result upload, GPA/CGPA computed on demand

## Tech stack

- Python 3
- Django 6.0.6
- SQLite (development database)
- Bootstrap 5 (frontend)

## Setup

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

## Project layout

```
.
├── manage.py          # Django's command-line entry point
├── lu_sims/           # Project-level config
│   ├── settings.py    # App list, database, middleware, etc.
│   ├── urls.py         # Top-level URL routing
│   ├── wsgi.py         # Sync production entry point
│   └── asgi.py         # Async production entry point
├── accounts/          # Auth, User model, roles, staff accounts
├── students/          # Student profiles, faculties, departments
├── courses/           # Course catalog and registration
├── results/           # Results, GPA/CGPA
├── docs/              # SRS, SDD, HOD brief, pilot proposal, seminar report/presentation
├── todo.md            # Open work and known gaps
└── requirements.txt   # Pinned dependencies
```
