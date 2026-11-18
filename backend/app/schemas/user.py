from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, EmailStr, Field, PlainSerializer, field_validator

from app.models.user import UserRole
from app.schemas.resource import CamelModel

# doar adresele institutionale au voie sa-si faca cont
ALLOWED_DOMAINS = ("student.usv.ro", "usm.ro")

# in baza de date rolurile sunt Student / Professor / Administrator,
# in API (Swagger) sunt student / profesor / administrator
API_ROLES = {
    UserRole.STUDENT: "student",
    UserRole.PROFESSOR: "profesor",
    UserRole.ADMINISTRATOR: "administrator",
}
ROLES_FROM_API = {value: role for role, value in API_ROLES.items()}

ApiRole = Annotated[UserRole, PlainSerializer(lambda role: API_ROLES[role], return_type=str)]


def is_usv_email(email: str) -> bool:
    return email.rsplit("@", 1)[-1].lower() in ALLOWED_DOMAINS


class UserRegister(CamelModel):
    email: EmailStr = Field(examples=["ion.popescu@student.usv.ro"])
    password: str = Field(min_length=8, max_length=128)
    first_name: str = Field(min_length=1, max_length=100, examples=["Ion"])
    last_name: str = Field(min_length=1, max_length=100, examples=["Popescu"])

    @field_validator("email")
    @classmethod
    def lowercase(cls, email: str) -> str:
        # domeniul se verifica in ruta, ca sa putem raspunde cu 400 cum cere Swagger-ul
        return email.lower()


class UserRead(CamelModel):
    id: int
    email: str
    first_name: str
    last_name: str
    role: ApiRole
    no_show_count: int
    blocked: bool
    blocked_until: datetime | None
    reservations_this_month: int


class Token(BaseModel):
    # snake_case cum cere OAuth2 (si butonul Authorize din Swagger UI)
    access_token: str
    token_type: str = "bearer"
