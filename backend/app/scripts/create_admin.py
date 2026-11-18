"""Creeaza (sau promoveaza) un cont de administrator.

Adminii nu se pot inregistra din API, asa ca primul cont se face din linia de comanda:

    python -m app.scripts.create_admin admin@usm.ro "parola-lunga" Ion Popescu
"""

import sys

from sqlalchemy import select

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models.user import User, UserRole


def main(args: list[str]) -> None:
    if len(args) != 4:
        print(__doc__)
        raise SystemExit(1)
    email, password, first_name, last_name = args
    email = email.lower()
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == email))
        if user is None:
            user = User(email=email, first_name=first_name, last_name=last_name)
            db.add(user)
        user.password_hash = hash_password(password)
        user.role = UserRole.ADMINISTRATOR
        db.commit()
        print(f"admin gata: {email}")


if __name__ == "__main__":
    main(sys.argv[1:])
