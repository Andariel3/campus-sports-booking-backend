from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.core.security import create_access_token
from app.db.session import get_db
from app.schemas.user import Token, UserRead, UserRegister, is_usv_email
from app.services import auth_service, user_service
from app.services.auth_service import EmailAlreadyUsedError

router = APIRouter(prefix="/auth", tags=["auth"])

DbSession = Annotated[Session, Depends(get_db)]


@router.post(
    "/register",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
    summary="Creare cont cu email institutional",
)
def register(data: UserRegister, db: DbSession):
    if not is_usv_email(data.email):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "Se accepta doar adrese @student.usv.ro sau @usm.ro"
        )
    try:
        user = auth_service.register_user(db, data)
    except EmailAlreadyUsedError:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Exista deja un cont cu acest email"
        ) from None
    return user_service.user_view(db, user)


@router.post("/login", response_model=Token, summary="Login, intoarce tokenul JWT")
def login(form: Annotated[OAuth2PasswordRequestForm, Depends()], db: DbSession):
    # OAuth2 password flow: campul username este adresa de email
    user = auth_service.authenticate(db, form.username, form.password)
    if user is None:
        # acelasi mesaj si pentru email inexistent, ca sa nu se poata afla ce conturi exista
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Email sau parola gresita")
    if user_service.is_blocked(user):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "Contul este blocat din cauza neprezentarilor"
        )
    return Token(access_token=create_access_token(user.id))
