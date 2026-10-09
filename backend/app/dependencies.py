from typing import Annotated

from fastapi import Depends, Request

from app.services.registry import Registry


def get_registry(request: Request) -> Registry:
    """The registry instance owned by the running app (see create_app)."""
    registry: Registry = request.app.state.registry
    return registry


RegistryDep = Annotated[Registry, Depends(get_registry)]
