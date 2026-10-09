from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.db import Database
from app.services.registry import Registry


def get_session(request: Request) -> Iterator[Session]:
    """A database session scoped to one request."""
    database: Database = request.app.state.database
    yield from database.session()


def get_registry(session: Annotated[Session, Depends(get_session)]) -> Registry:
    return Registry(session)


RegistryDep = Annotated[Registry, Depends(get_registry)]
