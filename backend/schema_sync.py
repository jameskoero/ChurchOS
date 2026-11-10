"""Adds columns that newer code needs to tables that already exist.

db.create_all() creates missing tables but never alters an existing one.
Every statement here is additive and safe to run on every startup.
"""
from sqlalchemy import inspect, text

ADDITIONS = [
    ('users', 'failed_logins', 'INTEGER DEFAULT 0'),
    ('users', 'locked_until', 'TIMESTAMP'),
    ('users', 'token_version', 'INTEGER DEFAULT 0'),
]


def sync_schema(db):
    """Return the list of 'table.column' names that were added."""
    engine = db.engine
    if_not_exists = 'IF NOT EXISTS ' if engine.dialect.name == 'postgresql' else ''
    added = []
    for table, column, ddl in ADDITIONS:
        insp = inspect(engine)
        if table not in insp.get_table_names():
            continue
        if column in {c['name'] for c in insp.get_columns(table)}:
            continue
        try:
            with engine.begin() as conn:
                conn.execute(text(
                    f'ALTER TABLE {table} ADD COLUMN {if_not_exists}{column} {ddl}'))
            added.append(f'{table}.{column}')
        except Exception:
            # Another worker may have added it at the same moment.
            if column not in {c['name'] for c in inspect(engine).get_columns(table)}:
                raise
    return added
