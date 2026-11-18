from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.security import read_user_id
from app.db.session import get_db
from app.models.user import User, UserRole

# tokenUrl face ca butonul Authorize din Swagger UI sa mearga direct cu email + parola.
# auto_error=False ca sa intoarcem noi 401 cu mesajul nostru
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)


def get_current_user(
    token: Annotated[str | None, Depends(oauth2_scheme)],
    db: Annotated[Session, Depends(get_db)],
) -> User:
    user_id = read_user_id(token) if token else None
    user = db.get(User, user_id) if user_id is not None else None
    if user is None:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Nu sunteti autentificat",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_admin(user: CurrentUser) -> User:
    if user.role != UserRole.ADMINISTRATOR:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Nu aveti drepturi pentru aceasta operatie")
    return user


AdminUser = Annotated[User, Depends(require_admin)]
