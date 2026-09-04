# HelpDesk Pro

HelpDesk Pro is a secure internal IT-support web application for DRN TECH. Staff can raise and track support requests, find self-help articles, use live chat, and request guest Wi-Fi access. Administrators manage users, support queues, knowledge-base content, reports, and ticket progress.

## Features

- Role-based staff and administrator workspaces.
- Tickets with replies, priorities, due dates, tags, attachments, and status history.
- Single-owner live chat with ratings and automatic cleanup.
- Searchable knowledge base with administrator-managed images.
- Password reset, in-app/email notifications, reports, pagination, and CSV export.
- PostgreSQL migrations, scheduled backups, and responsive desktop/mobile layouts.

## Technology

Python, Flask, Flask-Login, Flask-SQLAlchemy, Flask-Migrate, SQLite for local development, PostgreSQL for production, Gunicorn, Nginx, HTML/CSS/JavaScript, and Pillow.

## Local setup

```powershell
cd C:\Users\Ebuka\HelpDeskPro
py -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
python app.py
```

Open `http://127.0.0.1:5000`.

For PostgreSQL, also install `requirements-postgresql.txt` and follow [docs/postgresql-migration.md](docs/postgresql-migration.md).

## Testing

```powershell
python -m unittest tests.test_regression
python -m unittest tests.test_security
```

## Production notes

- Set `APP_ENV=production`, a long random `SECRET_KEY`, and `SESSION_COOKIE_SECURE=true`.
- Serve through Gunicorn and Nginx.
- Use HTTPS with a real domain before enabling secure production cookies and web push.
- Run migrations before releases and verify backups regularly.

## Repository hygiene

The repository includes application source, templates, static assets, migrations, tests, documentation, and scripts. It deliberately excludes `.env`, databases, uploads, virtual environments, IDE settings, and generated cache files.

## Documentation

- [Project roadmap](docs/project-roadmap.md)
- [PostgreSQL migration guide](docs/postgresql-migration.md)
- [Security review](docs/security-review-2026-09-03.md)
