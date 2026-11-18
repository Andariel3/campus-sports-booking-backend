from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from sqlalchemy.orm import Session

from app.core.deps import AdminUser, CurrentUser
from app.db.session import get_db
from app.schemas.user import ROLES_FROM_API, ApiRoleName, UserRead
from app.services import user_service
from app.services.user_service import UserNotFoundError

router = APIRouter(prefix="/users", tags=["users"])

DbSession = Annotated[Session, Depends(get_db)]


@router.get("/me", response_model=UserRead, summary="Datele utilizatorului logat")
def me(user: CurrentUser, db: DbSession):
    return user_service.user_view(db, user)


@router.get("", response_model=list[UserRead], summary="Lista utilizatorilor (admin)")
def list_users(
    _: AdminUser,
    db: DbSession,
    role: Annotated[ApiRoleName | None, Query()] = None,
    blocked: Annotated[bool | None, Query()] = None,
):
    users = user_service.list_users(db, ROLES_FROM_API[role] if role else None, blocked)
    return [user_service.user_view(db, user) for user in users]


@router.post(
    "/{userId}/unblock",
    response_model=UserRead,
    summary="Deblocare cont (admin)",
    description="Contul se blocheaza automat dupa 2 neprezentari. Adminul il poate debloca manual.",
)
def unblock(user_id: Annotated[int, Path(alias="userId")], _: AdminUser, db: DbSession):
    try:
        user = user_service.unblock(db, user_id)
    except UserNotFoundError:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, f"Utilizatorul {user_id} nu exista"
        ) from None
    return user_service.user_view(db, user)
