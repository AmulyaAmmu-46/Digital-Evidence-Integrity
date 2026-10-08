from getpass import getpass

from app import create_app
from app.extensions import db, bcrypt
from app.models.user import User

app = create_app()

LEGACY_DEMO_EMAILS = (
    'admin@example.com',
    'investigator@example.com',
    'auditor@example.com',
    'viewer@example.com',
)


def create_admin(email, full_name, password):
    email = email.strip().lower()
    full_name = full_name.strip()
    if not email or not full_name or len(password) < 12 or len(password.encode('utf-8')) > 72:
        raise ValueError('Email and full name are required; password must be 12-72 UTF-8 bytes.')

    with app.app_context():
        db.create_all()

        User.query.filter(User.email.in_(LEGACY_DEMO_EMAILS)).update(
            {User.is_active: False}, synchronize_session=False
        )

        admin = User.query.filter_by(email=email).first()
        if admin is None:
            admin = User(email=email, role='ADMIN')
            db.session.add(admin)

        admin.full_name = full_name
        admin.role = 'ADMIN'
        admin.password_hash = bcrypt.generate_password_hash(password).decode('utf-8')
        admin.is_active = True
        db.session.commit()
        print(f'Admin account ready for {email}.')


if __name__ == '__main__':
    admin_email = input('Admin email: ')
    admin_name = input('Admin full name: ')
    admin_password = getpass('Admin password: ')
    password_confirmation = getpass('Confirm admin password: ')

    if admin_password != password_confirmation:
        raise SystemExit('Passwords do not match; no changes were made.')

    try:
        create_admin(admin_email, admin_name, admin_password)
    except ValueError as error:
        raise SystemExit(str(error)) from error
