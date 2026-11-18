from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from sqlalchemy.orm import Session

from app.core.deps import AdminUser
from app.db.session import get_db
from app.models.resource import ResourceType
from app.schemas.availability import Availability
from app.schemas.resource import ResourceCreate, ResourceRead, ResourceUpdate
from app.services import availability_service, resource_service
from app.services.resource_service import DuplicateResourceNameError, ResourceNotFoundError

router = APIRouter(prefix="/resources", tags=["resources"])

# the contract names the path parameter resourceId
ResourceId = Annotated[int, Path(alias="resourceId")]
DbSession = Annotated[Session, Depends(get_db)]


@router.get("", response_model=list[ResourceRead], summary="Lista resurselor sportive")
def list_resources(
    db: DbSession,
    sport: Annotated[str | None, Query(description="Filtrare dupa sport")] = None,
    resource_type: Annotated[ResourceType | None, Query(alias="type")] = None,
):
    return resource_service.list_resources(db, sport, resource_type)


@router.post(
    "",
    response_model=ResourceRead,
    status_code=status.HTTP_201_CREATED,
    summary="Adaugare resursa (admin)",
)
def create_resource(data: ResourceCreate, _: AdminUser, db: DbSession):
    try:
        return resource_service.create_resource(db, data)
    except DuplicateResourceNameError:
        raise _duplicate_name() from None


@router.get("/{resourceId}", response_model=ResourceRead, summary="Detalii resursa")
def get_resource(resource_id: ResourceId, db: DbSession):
    try:
        return resource_service.get_resource(db, resource_id)
    except ResourceNotFoundError:
        raise _not_found(resource_id) from None


@router.get(
    "/{resourceId}/availability",
    response_model=Availability,
    summary="Orarul unei resurse pe o zi",
    description="Intervale de cate o ora din programul zilei: liber / ocupat / mentenanta.",
)
def get_availability(
    resource_id: ResourceId, db: DbSession, day: Annotated[date, Query(alias="date")]
):
    try:
        resource = resource_service.get_resource(db, resource_id)
    except ResourceNotFoundError:
        raise _not_found(resource_id) from None
    return {
        "resource_id": resource.id,
        "date": day,
        "slots": availability_service.day_slots(db, resource, day),
    }


@router.patch("/{resourceId}", response_model=ResourceRead, summary="Modificare resursa (admin)")
def update_resource(resource_id: ResourceId, data: ResourceUpdate, _: AdminUser, db: DbSession):
    try:
        return resource_service.update_resource(db, resource_id, data)
    except ResourceNotFoundError:
        raise _not_found(resource_id) from None
    except DuplicateResourceNameError:
        raise _duplicate_name() from None
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from None


@router.delete(
    "/{resourceId}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Stergere resursa (admin)",
    description="Resursa devine inactiva si nu mai apare in lista; istoricul rezervarilor ramane.",
)
def delete_resource(resource_id: ResourceId, _: AdminUser, db: DbSession) -> None:
    try:
        resource_service.deactivate_resource(db, resource_id)
    except ResourceNotFoundError:
        raise _not_found(resource_id) from None


def _not_found(resource_id: int) -> HTTPException:
    return HTTPException(status.HTTP_404_NOT_FOUND, f"Resursa {resource_id} nu exista")


def _duplicate_name() -> HTTPException:
    return HTTPException(status.HTTP_409_CONFLICT, "Exista deja o resursa cu acest nume")
