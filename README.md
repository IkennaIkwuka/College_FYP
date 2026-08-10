# College_FYP — UniPortal

Final year project for my Computer Science degree at Legacy University, Okija, Anambra State — a Role-Based Access Control (RBAC) information management portal built with Django.

This repo used to just hold a placeholder; the project lived inside the LegacyUniversityOkija coursework repo instead. Moved it here so it has its own home, separate from general coursework.

## Status

Currently a bare Django skeleton. Being rebuilt from scratch after an earlier version (student records, course management, course registration, custom auth) was stripped out to restart the build more deliberately.

## Tech stack

- Python 3
- Django 6.0.6
- SQLite (development database)

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
├── manage.py         # Django's command-line entry point
├── lu_sims/          # Project-level config
│   ├── settings.py   # App list, database, middleware, etc.
│   ├── urls.py        # Top-level URL routing
│   ├── wsgi.py        # Sync production entry point
│   └── asgi.py        # Async production entry point
└── requirements.txt   # Pinned dependencies
```
