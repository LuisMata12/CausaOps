import argparse
import getpass
import sys

from sqlalchemy import select

from app.database import SessionLocal
from app.models import User
from app.security import hash_password

MINIMUM_PASSWORD_LENGTH = 12


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a CausaOps user who can approve actions")
    parser.add_argument("--email", required=True)
    parser.add_argument("--name", required=True, help="Display name shown on approvals")
    parser.add_argument(
        "--password",
        help="Read from a prompt when omitted, so it never reaches the shell history",
    )
    args = parser.parse_args()

    password = args.password or getpass.getpass("Password: ")
    if len(password) < MINIMUM_PASSWORD_LENGTH:
        sys.exit(f"The password must be at least {MINIMUM_PASSWORD_LENGTH} characters long.")

    email = args.email.strip().lower()
    with SessionLocal() as db:
        if db.scalar(select(User).where(User.email == email)) is not None:
            sys.exit(f"A user with the email {email} already exists.")
        user = User(email=email, display_name=args.name, password_hash=hash_password(password))
        db.add(user)
        db.commit()
        print(f"Created {user.email} ({user.id}).")


if __name__ == "__main__":
    main()
