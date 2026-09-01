# PostgreSQL migration

HelpDesk Pro keeps using SQLite locally until `DATABASE_URL` is set. For EC2,
create an empty PostgreSQL database and configure the deployed app with:

```text
APP_ENV=production
SECRET_KEY=<a long random value>
DATABASE_URL=postgresql+psycopg://<username>:<password>@<host>:5432/<database>
```

Install the PostgreSQL driver with the project dependencies, then initialise the
empty database:

```powershell
pip install -r requirements.txt -r requirements-postgresql.txt
python -m flask --app app init-db
```

## Copy existing SQLite data

1. Back up `instance/helpdesk.db` before making any changes.
2. Point `DATABASE_URL` to the empty PostgreSQL database.
3. Set `SQLITE_DATABASE_URL` to the SQLite backup, for example:

```powershell
$env:SQLITE_DATABASE_URL = 'sqlite:///C:/Users/Ebuka/HelpDeskPro/instance/helpdesk.db'
python scripts/migrate_sqlite_to_postgres.py
```

The script stops if the destination database contains data. It copies users,
tickets, conversations, notifications, Knowledge Base content, and reset-token
records while preserving their IDs.
