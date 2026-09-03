# HelpDesk Pro — ChatGPT Handover

## What this project is

HelpDesk Pro is DRN TECH's internal IT-support portal. It is a Flask project hosted on EC2 behind Gunicorn and Nginx, with PostgreSQL used in production and SQLite available locally.

## Main user journeys

### Staff

1. Register or log in.
2. Create a ticket with category, priority, description, and optional attachment.
3. Track replies, progress, due date, status, and notifications.
4. Search knowledge-base articles or start live chat.
5. Submit a five-star rating when live chat is resolved.

### Administrators

1. Manage users and roles.
2. View, filter, sort, claim, and update tickets.
3. Assign due dates, add tags, internal notes, replies, and progress updates.
4. Claim one live chat at a time, resolve it, request feedback, then close/delete it.
5. Manage knowledge-base articles and export CSV reports.

## Important implementation decisions

- Live chat uses claim ownership so two administrators cannot reply to the same conversation.
- CSRF is enforced globally for POST requests.
- User uploads are private ticket attachments; downloads are access-controlled.
- Ticket and notification emails are SMTP-configured through `.env`.
- Database changes are versioned in `migrations/`.
- Mobile navigation uses a fixed bottom bar; More opens the complete navigation sheet.

## Key files

| File or folder | Purpose |
| --- | --- |
| `app.py` | Flask routes, models, validation, security controls, and business logic. |
| `templates/` | User, administrator, authentication, ticket, chat, and knowledge-base pages. |
| `static/` | CSS, JavaScript, DRN TECH brand assets, and knowledge-base images. |
| `migrations/` | Versioned database schema changes. |
| `tests/` | Functional regression and security checks. |
| `docs/` | Migration, roadmap, handover, and security-review documentation. |

## Current status

Core functionality and the mobile/desktop interface are complete for the project scope. Deferred post-launch work is a custom domain with HTTPS, web-push notifications, and refinements based on real user feedback.

## Useful commands

```powershell
python -m unittest tests.test_regression
python -m unittest tests.test_security
git status
```

On EC2:

```bash
cd /home/ubuntu/helpdeskpro
git pull origin main
sudo systemctl restart helpdeskpro
sudo systemctl start helpdeskpro-backup.service
```
