"""Explicit provisioning; never executed by server startup."""
import argparse
import getpass


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--username", required=True)
    args = parser.parse_args()
    password = getpass.getpass("New administrator password (at least 16 characters): ")
    if len(password) < 16 or password != getpass.getpass("Confirm password: "):
        parser.error("Password too short or confirmation differs")
    from SHARED.database import session_scope, init_db
    from SHARED.models import AppUser
    from SHARED.auth_service import AuthService
    init_db()
    with session_scope() as db:
        if db.query(AppUser).filter(AppUser.username == args.username.strip()).first():
            parser.error("Account already exists; use the authorized password reset workflow")
        db.add(AppUser(username=args.username.strip(), full_name=args.username.strip(),
                       password_hash=AuthService.hash_password(password), auth_type="local",
                       role="superadmin", is_active=True))
        db.commit()
    print("Administrator created")


if __name__ == "__main__":
    main()
