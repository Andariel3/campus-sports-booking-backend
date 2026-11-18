from datetime import time
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.resource import POOL_SPORTS, Resource, ResourceSchedule, ResourceType, SportType
from app.schemas.resource import ResourceCreate, ResourceUpdate, check_open_before_close


class ResourceNotFoundError(Exception):
    pass


class DuplicateResourceNameError(Exception):
    pass


def list_resources(
    db: Session,
    sport: str | None = None,
    resource_type: ResourceType | None = None,
    include_inactive: bool = False,
) -> list[Resource]:
    query = select(Resource).outerjoin(Resource.sport_type).order_by(Resource.name)
    if not include_inactive:
        query = query.where(Resource.is_active.is_(True))
    if sport:
        query = query.where(func.lower(SportType.label) == sport.strip().lower())
    if resource_type is ResourceType.BAZIN:
        query = query.where(func.lower(SportType.label).in_(POOL_SPORTS))
    elif resource_type is ResourceType.TEREN:
        query = query.where(func.lower(SportType.label).not_in(POOL_SPORTS))
    return list(db.scalars(query).unique())


def get_resource(db: Session, resource_id: int) -> Resource:
    resource = db.get(Resource, resource_id)
    if resource is None:
        raise ResourceNotFoundError(resource_id)
    return resource


def create_resource(db: Session, data: ResourceCreate) -> Resource:
    _check_name_is_free(db, data.name)
    resource = Resource(
        name=data.name,
        sport_type=_sport_type(db, data.sport),
        description=data.description,
        price_per_hour=Decimal(str(data.price_per_hour)),
    )
    _set_hours(resource, data.open_hour, data.close_hour)
    db.add(resource)
    db.commit()
    db.refresh(resource)
    return resource


def update_resource(db: Session, resource_id: int, data: ResourceUpdate) -> Resource:
    resource = get_resource(db, resource_id)
    changes = data.model_dump(exclude_unset=True)

    if "name" in changes and changes["name"] != resource.name:
        _check_name_is_free(db, changes["name"])
        resource.name = changes["name"]
    if "sport" in changes:
        resource.sport_type = _sport_type(db, changes["sport"])
    if "description" in changes:
        resource.description = changes["description"]
    if changes.get("price_per_hour") is not None:
        resource.price_per_hour = Decimal(str(changes["price_per_hour"]))
    if changes.get("is_active") is not None:
        resource.is_active = changes["is_active"]
    if "open_hour" in changes or "close_hour" in changes:
        # orele noi se verifica si fata de cele deja salvate
        open_hour = changes.get("open_hour") or _text(resource.open_hour)
        close_hour = changes.get("close_hour") or _text(resource.close_hour)
        check_open_before_close(open_hour, close_hour)
        _set_hours(resource, open_hour, close_hour)

    db.commit()
    db.refresh(resource)
    return resource


def deactivate_resource(db: Session, resource_id: int) -> None:
    """Resursa nu se sterge (ar disparea si istoricul rezervarilor), doar devine inactiva."""
    resource = get_resource(db, resource_id)
    resource.is_active = False
    db.commit()


def _sport_type(db: Session, label: str) -> SportType:
    """Sportul din sport_types; daca nu exista inca, il adaugam."""
    label = label.strip().lower()
    sport_type = db.scalar(select(SportType).where(func.lower(SportType.label) == label))
    if sport_type is None:
        sport_type = SportType(label=label)
        db.add(sport_type)
    return sport_type


def _set_hours(resource: Resource, open_hour: str | None, close_hour: str | None) -> None:
    """Acelasi program in toate cele 7 zile (resource_schedules)."""
    if not open_hour or not close_hour:
        return
    opens, closes = time.fromisoformat(open_hour), time.fromisoformat(close_hour)
    by_day = {s.day_of_week: s for s in resource.schedules}
    for day in range(7):
        schedule = by_day.get(day)
        if schedule is None:
            resource.schedules.append(
                ResourceSchedule(day_of_week=day, open_time=opens, close_time=closes)
            )
        else:
            schedule.open_time, schedule.close_time = opens, closes


def _check_name_is_free(db: Session, name: str) -> None:
    exists = db.scalar(select(Resource.id).where(func.lower(Resource.name) == name.lower()))
    if exists is not None:
        raise DuplicateResourceNameError


def _text(value: time | None) -> str | None:
    return value.strftime("%H:%M") if value else None
