from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import CurrentUser
from app.db.session import get_db
from app.schemas.user import UserRead
from app.services import user_service

router = APIRouter(prefix="/users", tags=["users"])

DbSession = Annotated[Session, Depends(get_db)]


@router.get("/me", response_model=UserRead, summary="Datele utilizatorului logat")
def me(user: CurrentUser, db: DbSession):
    return user_service.user_view(db, user)
