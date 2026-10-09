from fastapi import APIRouter, status

from app.dependencies import RegistryDep
from app.models import Service
from app.schemas import ServiceCreate

router = APIRouter(prefix="/services", tags=["services"])


@router.get("", response_model=list[Service])
def list_services(registry: RegistryDep) -> list[Service]:
    return registry.list_services()


@router.get("/{service_id}", response_model=Service)
def get_service(service_id: str, registry: RegistryDep) -> Service:
    return registry.get_service(service_id)


@router.post("", response_model=Service, status_code=status.HTTP_201_CREATED)
def create_service(payload: ServiceCreate, registry: RegistryDep) -> Service:
    return registry.create_service(payload)
