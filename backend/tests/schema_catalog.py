"""Read a PostgreSQL schema from the system catalog, for exact schema comparisons."""

import re
from typing import Any

from sqlalchemy import Connection, text

TABLES = ("services", "integrations", "telemetry_records")


def catalog(connection: Connection) -> dict[str, Any]:
    """Columns, constraints and indexes of the application's tables, as PostgreSQL reports them."""
    columns = connection.execute(
        text(
            "SELECT table_name, column_name, data_type, character_maximum_length, is_nullable, column_default "
            "FROM information_schema.columns WHERE table_schema = 'public' AND table_name = ANY(:tables) "
            "ORDER BY table_name, ordinal_position"
        ),
        {"tables": list(TABLES)},
    ).all()
    constraints = connection.execute(
        text(
            "SELECT conrelid::regclass::text, conname, contype, pg_get_constraintdef(oid) FROM pg_constraint "
            "WHERE conrelid::regclass::text = ANY(:tables) ORDER BY 1, 2"
        ),
        {"tables": list(TABLES)},
    ).all()
    indexes = connection.execute(
        text(
            "SELECT tablename, indexname, indexdef FROM pg_indexes "
            "WHERE schemaname = 'public' AND tablename = ANY(:tables) ORDER BY 1, 2"
        ),
        {"tables": list(TABLES)},
    ).all()
    return {
        "columns": [tuple(row) for row in columns],
        "constraints": [tuple(row) for row in constraints],
        "indexes": [tuple(row) for row in indexes],
    }


def strip_schema(definition: str) -> str:
    return re.sub(r"\bpublic\.", "", definition)
