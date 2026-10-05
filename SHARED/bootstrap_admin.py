"""Administrator provisioning; Compose initializes an empty database exactly once."""
import argparse
import getpass
import sys

from SHARED.passwords import MIN_PASSWORD_LENGTH, MAX_PASSWORD_LENGTH


def _read_password(args, parser):
    if args.password_stdin:
        password = sys.stdin.readline().rstrip("\r\n")
        if not password:
            parser.error("Password was not provided on stdin")
        return password

    password = getpass.getpass(
        f"New administrator password ({MIN_PASSWORD_LENGTH}-{MAX_PASSWORD_LENGTH} characters): "
    )
    confirmation = getpass.getpass("Confirm password: ")
    if password != confirmation:
        parser.error("Password confirmation differs")
    return password


def main():
    parser = argparse.ArgumentParser(
        description="Create or explicitly reset a local superadmin account."
    )
    parser.add_argument("--username", default="admin")
    parser.add_argument("--initialize-default", action="store_true",
                        help="Initialize an empty database with admin and a mandatory password change.")
    parser.add_argument(
        "--reset-existing",
        action="store_true",
        help="Reset an existing account to active local superadmin and replace its password.",
    )
    parser.add_argument(
        "--password-stdin",
        action="store_true",
        help="Read the password from stdin instead of prompting. Useful for controlled deployment commands.",
    )
    args = parser.parse_args()

    if args.initialize_default and (args.reset_existing or args.password_stdin or args.username != 'admin'):
        parser.error('Default initialization cannot be combined with account reset options')
    password = 'admin123' if args.initialize_default else _read_password(args, parser)
    if not MIN_PASSWORD_LENGTH <= len(password) <= MAX_PASSWORD_LENGTH:
        parser.error(
            f"Password length must be between {MIN_PASSWORD_LENGTH} and {MAX_PASSWORD_LENGTH} characters"
        )

    from SHARED.database import session_scope, init_db
    from SHARED.models import AppUser
    from SHARED.auth_service import AuthService

    init_db()
    username = args.username.strip()
    if not username:
        parser.error("Username must not be empty")

    with session_scope() as db:
        if args.initialize_default and db.query(AppUser).first() is not None:
            print('Existing accounts preserved; initial administrator not created')
            return
        user = db.query(AppUser).filter(AppUser.username == username).first()
        if user is not None:
            if not args.reset_existing:
                parser.error(
                    "Account already exists; pass --reset-existing for an explicit administrator reset"
                )
            user.full_name = user.full_name or username
            user.password_hash = AuthService.hash_password(password)
            user.must_change_password = False
            user.auth_type = "local"
            user.role = "superadmin"
            user.is_active = True
            user.branch_id = None
            action = "reset"
        else:
            user = AppUser(
                username=username,
                full_name=username,
                password_hash=AuthService.hash_password(password),
                must_change_password=args.initialize_default,
                auth_type="local",
                role="superadmin",
                is_active=True,
                branch_id=None,
            )
            db.add(user)
            action = "created"
        db.commit()

    print(f"Administrator {username!r} {action}")


if __name__ == "__main__":
    main()
