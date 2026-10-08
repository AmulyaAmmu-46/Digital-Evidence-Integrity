import pytest

from app import create_app
from app.extensions import bcrypt, db
from app.models.audit import AuditLog
from app.models.case import Case
from app.models.case_viewer_grant import CaseViewerGrant
from app.models.user import User


class TestConfig:
    SECRET_KEY = 'test-secret'
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    UPLOAD_FOLDER = 'uploads'
    WTF_CSRF_ENABLED = False


@pytest.fixture
def app():
    app = create_app(TestConfig)
    app.config['TESTING'] = True
    with app.app_context():
        db.create_all()
        admin = User(
            email='admin@example.test',
            full_name='Test Admin',
            role='ADMIN',
            password_hash=bcrypt.generate_password_hash('admin-password').decode('utf-8'),
        )
        investigator = User(
            email='investigator@example.test',
            full_name='Test Investigator',
            role='INVESTIGATOR',
            password_hash=bcrypt.generate_password_hash('investigator-password').decode('utf-8'),
        )
        db.session.add_all([admin, investigator])
        db.session.commit()
        yield app, admin, investigator
        db.drop_all()


def sign_in(client, user):
    with client.session_transaction() as session:
        session['_user_id'] = user.id
        session['_fresh'] = True


def test_admin_can_create_role_account_with_hashed_password(app):
    flask_app, admin, _ = app
    client = flask_app.test_client()
    sign_in(client, admin)

    response = client.post('/users/', data={
        'full_name': 'New Auditor',
        'email': 'AUDITOR@example.test',
        'role': 'AUDITOR',
        'password': 'a-unique-password',
        'password_confirmation': 'a-unique-password',
    }, follow_redirects=True)

    assert response.status_code == 200
    assert b'account created' in response.data.lower()
    user = User.query.filter_by(email='auditor@example.test').one()
    assert user.role == 'AUDITOR'
    assert bcrypt.check_password_hash(user.password_hash, 'a-unique-password')


def test_non_admin_cannot_create_accounts(app):
    flask_app, _, investigator = app
    client = flask_app.test_client()
    sign_in(client, investigator)

    response = client.post('/users/', data={
        'full_name': 'Unauthorized User',
        'email': 'unauthorized@example.test',
        'role': 'VIEWER',
        'password': 'a-unique-password',
        'password_confirmation': 'a-unique-password',
    })

    assert response.status_code == 403
    assert User.query.filter_by(email='unauthorized@example.test').first() is None


def test_admin_can_change_role_and_disable_then_reenable_user(app):
    flask_app, admin, investigator = app
    client = flask_app.test_client()
    sign_in(client, admin)

    response = client.post(f'/users/{investigator.id}/update', data={
        'role': 'AUDITOR',
        'is_active': 'false',
    })

    assert response.status_code == 302
    assert investigator.role == 'AUDITOR'
    assert investigator.is_active is False
    assert AuditLog.query.filter_by(resource_id=investigator.id, action='USER_ROLE_CHANGED').one()
    assert AuditLog.query.filter_by(resource_id=investigator.id, action='USER_ACCOUNT_STATUS_CHANGED').one()

    sign_in(client, admin)
    response = client.post(f'/users/{investigator.id}/update', data={
        'role': 'AUDITOR',
        'is_active': ['false', 'true'],
    })

    assert response.status_code == 302
    assert investigator.is_active is True


def test_admin_cannot_disable_or_demote_self(app):
    flask_app, admin, _ = app
    client = flask_app.test_client()
    sign_in(client, admin)

    response = client.post(f'/users/{admin.id}/update', data={
        'role': 'INVESTIGATOR',
        'is_active': 'false',
    }, follow_redirects=True)

    assert response.status_code == 200
    assert admin.role == 'ADMIN'
    assert admin.is_active is True


def test_investigator_cannot_change_user_roles(app):
    flask_app, admin, investigator = app
    client = flask_app.test_client()
    sign_in(client, investigator)

    response = client.post(f'/users/{admin.id}/update', data={
        'role': 'VIEWER',
        'is_active': 'true',
    })

    assert response.status_code == 403
    assert admin.role == 'ADMIN'


def test_role_change_revokes_viewer_case_grants(app):
    flask_app, admin, investigator = app
    investigator.role = 'VIEWER'
    case = Case(
        case_id='CASE-2026-9000',
        title='Granted case',
        category='Cyber Incident',
        created_by=admin.id,
    )
    db.session.add(case)
    db.session.flush()
    grant = CaseViewerGrant(case_id=case.id, viewer_id=investigator.id, granted_by=admin.id)
    db.session.add(grant)
    db.session.commit()

    client = flask_app.test_client()
    sign_in(client, admin)
    response = client.post(f'/users/{investigator.id}/update', data={
        'role': 'AUDITOR',
        'is_active': 'true',
    })

    assert response.status_code == 302
    assert CaseViewerGrant.query.filter_by(viewer_id=investigator.id).count() == 0
    assert AuditLog.query.filter_by(resource_id=case.id, action='CASE_VIEWER_ACCESS_REVOKED').one()


def test_disabling_viewer_revokes_case_grants(app):
    flask_app, admin, investigator = app
    investigator.role = 'VIEWER'
    case = Case(
        case_id='CASE-2026-9001',
        title='Viewer grant to revoke',
        category='Cyber Incident',
        created_by=admin.id,
    )
    db.session.add(case)
    db.session.flush()
    db.session.add(CaseViewerGrant(case_id=case.id, viewer_id=investigator.id, granted_by=admin.id))
    db.session.commit()

    client = flask_app.test_client()
    sign_in(client, admin)
    response = client.post(f'/users/{investigator.id}/update', data={
        'role': 'VIEWER',
        'is_active': 'false',
    })

    assert response.status_code == 302
    assert CaseViewerGrant.query.filter_by(viewer_id=investigator.id).count() == 0
    assert AuditLog.query.filter_by(resource_id=case.id, action='CASE_VIEWER_ACCESS_REVOKED').one()