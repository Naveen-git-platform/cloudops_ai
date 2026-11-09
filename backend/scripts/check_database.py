"""Production-safe database and Alembic preflight.

Run from backend/: python -m scripts.check_database
The command never prints the connection URL or raw driver exception text.
"""

from pathlib import Path
import sys

from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, text

from app.config import Settings


def main() -> int:
    engine = None
    try:
        settings = Settings()  # DATABASE_URL is read from the environment/.env
        engine = create_engine(settings.database_url, pool_pre_ping=True, connect_args={"connect_timeout": 5})
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
            current = MigrationContext.configure(connection).get_current_revision()

        backend = Path(__file__).resolve().parents[1]
        config = Config(str(backend / "alembic.ini"))
        expected_heads = set(ScriptDirectory.from_config(config).get_heads())
        current_revisions = {current} if current else set()

        if current_revisions != expected_heads:
            expected = ", ".join(sorted(expected_heads)) or "none"
            actual = ", ".join(sorted(current_revisions)) or "none"
            print(f"Database reachable, but migrations are not current (expected: {expected}; found: {actual}).")
            print("Run: alembic upgrade head")
            return 1

        print(f"Database connection OK; Alembic revision: {current}.")
        return 0
    except Exception as error:
        # Do not print exception text: database drivers can include connection details.
        print(f"Database preflight failed ({type(error).__name__}). Check DATABASE_URL, network access, and SSL settings.")
        return 1
    finally:
        if engine is not None:
            engine.dispose()


if __name__ == "__main__":
    sys.exit(main())
