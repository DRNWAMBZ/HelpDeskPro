"""Copy HelpDesk Pro data from SQLite into an empty PostgreSQL database.

Required environment variables:
    DATABASE_URL         PostgreSQL destination URL
    SQLITE_DATABASE_URL  SQLite source URL

The destination must be empty. This script keeps record IDs so all existing
relationships continue to work after the move.
"""

import os
import sys
from pathlib import Path

from sqlalchemy import MetaData, create_engine, func, select, text

PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app import app, db, ensure_database_schema


TABLE_ORDER = (
    "user",
    "ticket",
    "ticket_reply",
    "chat_conversation",
    "chat_message",
    "chat_satisfaction_rating",
    "notification",
    "knowledge_article",
    "knowledge_article_image",
    "password_reset_token",
)


def main():

    source_url = os.environ.get("SQLITE_DATABASE_URL")
    destination_url = app.config["SQLALCHEMY_DATABASE_URI"]

    if not source_url:
        sys.exit("Set SQLITE_DATABASE_URL to the SQLite database you want to copy.")

    if not destination_url.startswith("postgresql"):
        sys.exit("DATABASE_URL must point to PostgreSQL before running this migration.")

    if source_url == destination_url:
        sys.exit("Source and destination databases must be different.")

    source_engine = create_engine(source_url)
    source_metadata = MetaData()

    try:
        source_metadata.reflect(bind=source_engine)

        with app.app_context():
            ensure_database_schema()

            destination_engine = db.engine
            destination_tables = db.metadata.tables

            with destination_engine.connect() as connection:
                for table_name in TABLE_ORDER:
                    if table_name not in destination_tables:
                        continue

                    existing_rows = connection.execute(
                        select(func.count()).select_from(
                            destination_tables[table_name]
                        )
                    ).scalar_one()

                    if existing_rows:
                        sys.exit(
                            "Destination database is not empty; "
                            "migration stopped before copying data."
                        )

            with source_engine.connect() as source_connection:
                with destination_engine.begin() as destination_connection:
                    for table_name in TABLE_ORDER:
                        if (
                            table_name not in source_metadata.tables
                            or table_name not in destination_tables
                        ):
                            continue

                        source_table = source_metadata.tables[table_name]
                        destination_table = destination_tables[table_name]
                        destination_columns = {
                            column.name
                            for column in destination_table.columns
                        }
                        rows = source_connection.execute(
                            select(source_table)
                        ).mappings()
                        records = [
                            {
                                key: value
                                for key, value in row.items()
                                if key in destination_columns
                            }
                            for row in rows
                        ]

                        if records:
                            destination_connection.execute(
                                destination_table.insert(),
                                records,
                            )

                        print(f"Copied {len(records)} rows from {table_name}.")

                    for table_name in TABLE_ORDER:
                        if table_name not in destination_tables:
                            continue

                        destination_connection.execute(
                            text(
                                "SELECT setval("
                                "pg_get_serial_sequence(:table_name, 'id'), "
                                "COALESCE((SELECT MAX(id) FROM "
                                f'"{table_name}"), 1), true)'
                            ),
                            {"table_name": f'"{table_name}"'},
                        )

        print("SQLite data migration completed successfully.")
    finally:
        source_engine.dispose()


if __name__ == "__main__":
    main()
