import hashlib
from io import BytesIO
import os
import tempfile

import pytest
from flask import g
from sqlalchemy.exc import IntegrityError

from app import create_app
from app.extensions import bcrypt, db
from app.models.case import Case
from app.models.audit import AuditLog
from app.models.custody import CustodyEvent
from app.models.evidence import Evidence
from app.models.user import User


class TestConfig:
    SECRET_KEY = 'test-secret'
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    UPLOAD_FOLDER = 'uploads'
    WTF_CSRF_ENABLED = False


@pytest.fixture
def isolated_case_app(tmp_path):
    class Config(TestConfig):
        UPLOAD_FOLDER = str(tmp_path)

    app = create_app(Config)
    app.config['TESTING'] = True
    with app.app_context():
        db.create_all()
        investigator_a = User(
            email='a@example.test',
            full_name='Investigator A',
            role='INVESTIGATOR',
            password_hash='unused',
        )
        investigator_b = User(
            email='b@example.test',
            full_name='Investigator B',
            role='INVESTIGATOR',
            password_hash='unused',
        )
        admin = User(email='admin@example.test', full_name='Admin', role='ADMIN', password_hash='unused')
        auditor = User(email='auditor@example.test', full_name='Auditor', role='AUDITOR', password_hash='unused')
        viewer = User(email='viewer@example.test', full_name='Viewer', role='VIEWER', password_hash='unused')
        db.session.add_all([investigator_a, investigator_b, admin, auditor, viewer])
        db.session.flush()
        case = Case(
            case_id='CASE-2026-0001',
            title='Private investigation',
            category='Cyber Incident',
            created_by=investigator_b.id,
            assigned_to=investigator_b.id,
        )
        db.session.add(case)
        db.session.commit()
        content = b'original evidence bytes'
        stored_path = tmp_path / 'evidence.txt'
        stored_path.write_bytes(content)
        evidence = Evidence(
            evidence_id='EVD-2026-0001',
            case_db_id=case.id,
            name='Network log',
            original_filename='network.txt',
            evidence_type='Log',
            file_size=len(content),
            collected_by=investigator_b.id,
            sha256_hash=hashlib.sha256(content).hexdigest(),
            storage_path=str(stored_path),
        )
        db.session.add(evidence)
        db.session.flush()
        db.session.add(CustodyEvent(
            evidence_db_id=evidence.id,
            case_db_id=case.id,
            action='EVIDENCE_UPLOADED',
            performed_by=investigator_b.id,
            new_custodian=investigator_b.id,
            reason='Initial collection',
        ))
        db.session.commit()
        yield app, {
            'admin': admin,
            'investigator_a': investigator_a,
            'investigator_b': investigator_b,
            'auditor': auditor,
            'viewer': viewer,
        }, case, evidence
        db.drop_all()


def sign_in(client, user):
    with client.session_transaction() as session:
        session['_user_id'] = user.id
        session['_fresh'] = True
    g.pop('_login_user', None)


def test_investigator_cannot_open_unrelated_case(isolated_case_app):
    app, users, case, _ = isolated_case_app
    client = app.test_client()
    sign_in(client, users['investigator_a'])

    response = client.get(f'/cases/{case.id}')

    assert response.status_code in (403, 404)
    assert b'Private investigation' not in response.data


def test_investigator_case_list_excludes_unrelated_cases(isolated_case_app):
    app, users, case, _ = isolated_case_app
    client = app.test_client()
    sign_in(client, users['investigator_a'])

    response = client.get('/cases/')

    assert response.status_code == 200
    assert case.case_id.encode() not in response.data


def test_investigator_can_view_created_and_assigned_cases(isolated_case_app):
    app, users, unrelated_case, _ = isolated_case_app
    assigned_case = Case(
        case_id='CASE-2026-0002',
        title='Assigned investigation',
        category='Cyber Incident',
        created_by=users['investigator_b'].id,
        assigned_to=users['investigator_a'].id,
    )
    created_case = Case(
        case_id='CASE-2026-0003',
        title='Investigator-created case',
        category='Cyber Incident',
        created_by=users['investigator_a'].id,
    )
    db.session.add_all([assigned_case, created_case])
    db.session.commit()
    client = app.test_client()
    sign_in(client, users['investigator_a'])

    listing = client.get('/cases/')

    assert assigned_case.case_id.encode() in listing.data
    assert created_case.case_id.encode() in listing.data
    assert unrelated_case.case_id.encode() not in listing.data
    assert client.get(f'/cases/{assigned_case.id}').status_code == 200


def test_database_rejects_orphan_case_owner(isolated_case_app):
    _, users, _, _ = isolated_case_app
    orphan = Case(
        case_id='CASE-2026-9999',
        title='Orphan case',
        category='Cyber Incident',
        created_by='missing-user-id',
    )
    db.session.add(orphan)

    with pytest.raises(IntegrityError):
        db.session.commit()
    db.session.rollback()
    assert Case.query.filter_by(case_id='CASE-2026-9999').first() is None


def test_investigator_dashboard_and_relevant_audit_page_render(isolated_case_app):
    app, users, _, _ = isolated_case_app
    client = app.test_client()
    sign_in(client, users['investigator_a'])

    assert client.get('/dashboard').status_code == 200
    assert client.get('/audit/').status_code == 200


def test_login_rejects_external_redirect_and_normalizes_email(isolated_case_app):
    app, users, _, _ = isolated_case_app
    users['admin'].password_hash = bcrypt.generate_password_hash('strong-test-password').decode('utf-8')
    db.session.commit()
    client = app.test_client()

    response = client.post('/login?next=https://attacker.example/', data={
        'email': ' ADMIN@EXAMPLE.TEST ',
        'password': 'strong-test-password',
    })

    assert response.status_code == 302
    assert response.location.endswith('/dashboard')
    assert AuditLog.query.filter_by(user_id=users['admin'].id, action='LOGIN_SUCCESS').one()


def test_inactive_user_session_is_invalidated(isolated_case_app):
    app, users, _, _ = isolated_case_app
    users['investigator_a'].is_active = False
    db.session.commit()
    client = app.test_client()
    sign_in(client, users['investigator_a'])

    response = client.get('/cases/')

    assert response.status_code == 302
    assert '/login' in response.location


def test_csrf_rejection_returns_400_error_page(isolated_case_app):
    app, _, _, _ = isolated_case_app
    app.config['WTF_CSRF_ENABLED'] = True
    client = app.test_client()

    response = client.post('/login', data={'email': 'admin@example.test', 'password': 'wrong'})

    assert response.status_code == 400
    assert b'400' in response.data


def test_login_page_includes_csrf_token(isolated_case_app):
    app, _, _, _ = isolated_case_app
    client = app.test_client()

    response = client.get('/login')

    assert response.status_code == 200
    assert b'name="csrf_token"' in response.data


@pytest.mark.parametrize('role_key', ['admin', 'investigator_a'])
def test_admin_and_investigator_can_create_cases(isolated_case_app, role_key):
    app, users, _, _ = isolated_case_app
    client = app.test_client()
    sign_in(client, users[role_key])

    response = client.post('/cases/create', data={
        'title': 'Cyber Incident Investigation',
        'category': 'Cyber Incident',
        'priority': 'HIGH',
    })

    assert response.status_code == 302
    created_case = Case.query.filter_by(title='Cyber Incident Investigation').one()
    assert created_case.created_by == users[role_key].id


def test_case_metadata_is_html_escaped(isolated_case_app):
    app, users, _, _ = isolated_case_app
    client = app.test_client()
    sign_in(client, users['admin'])
    payload = '<script>alert(1)</script>'

    response = client.post('/cases/create', data={
        'title': payload,
        'category': 'Cyber Incident',
        'priority': 'HIGH',
    }, follow_redirects=True)

    assert response.status_code == 200
    assert payload.encode() not in response.data
    assert b'&lt;script&gt;alert(1)&lt;/script&gt;' in response.data


def test_audit_history_paginates_past_one_hundred_records(isolated_case_app):
    app, users, _, _ = isolated_case_app
    db.session.add(AuditLog(
        user_id=users['admin'].id,
        role='ADMIN',
        action='PAGINATION_TEST',
        result='SUCCESS',
        description='oldest pagination row',
    ))
    db.session.commit()
    db.session.add_all([
        AuditLog(
            user_id=users['admin'].id,
            role='ADMIN',
            action='PAGINATION_TEST',
            result='SUCCESS',
            description=f'pagination row {index}',
        )
        for index in range(100)
    ])
    db.session.commit()
    client = app.test_client()
    sign_in(client, users['admin'])

    response = client.get('/audit/?page=2')

    assert response.status_code == 200
    assert b'Page 2 of 2' in response.data
    assert b'oldest pagination row' in response.data


@pytest.mark.parametrize('role_key', ['auditor', 'viewer'])
def test_auditor_and_viewer_cannot_create_cases(isolated_case_app, role_key):
    app, users, _, _ = isolated_case_app
    client = app.test_client()
    sign_in(client, users[role_key])

    response = client.post('/cases/create', data={
        'title': 'Unauthorized case',
        'category': 'Cyber Incident',
        'priority': 'HIGH',
    })

    assert response.status_code == 403
    assert Case.query.filter_by(title='Unauthorized case').first() is None


def test_only_admin_can_assign_and_change_case_status(isolated_case_app):
    app, users, case, _ = isolated_case_app
    investigator_client = app.test_client()
    sign_in(investigator_client, users['investigator_b'])
    denied = investigator_client.post(f'/cases/{case.id}/assign', data={'assigned_to': users['investigator_a'].id})
    assert denied.status_code == 403
    investigator_client.post(f'/cases/{case.id}/edit', data={
        'title': case.title,
        'category': case.category,
        'priority': case.priority,
        'status': 'CLOSED',
    })
    assert Case.query.get(case.id).status == 'OPEN'

    admin_client = app.test_client()
    sign_in(admin_client, users['admin'])
    updated = admin_client.post(f'/cases/{case.id}/edit', data={
        'title': case.title,
        'category': case.category,
        'priority': case.priority,
        'status': 'CLOSED',
    })
    assert updated.status_code == 302
    assert Case.query.get(case.id).status == 'CLOSED'
    assert AuditLog.query.filter_by(resource_id=case.id, action='STATUS_CHANGED').one().result == 'SUCCESS'


def test_evidence_upload_hashes_file_and_records_custody_and_audit(isolated_case_app):
    app, users, case, _ = isolated_case_app
    client = app.test_client()
    sign_in(client, users['investigator_b'])
    contents = b'collected log evidence'

    response = client.post(f'/evidence/upload/{case.id}', data={
        'name': 'Collected log',
        'evidence_type': 'Log',
        'file': (BytesIO(contents), '../collected.txt'),
    })

    assert response.status_code == 302
    evidence = Evidence.query.filter_by(name='Collected log').one()
    assert evidence.sha256_hash == hashlib.sha256(contents).hexdigest()
    assert os.path.dirname(evidence.storage_path) == app.config['UPLOAD_FOLDER']
    assert os.path.basename(evidence.storage_path) != '../collected.txt'
    assert CustodyEvent.query.filter_by(evidence_db_id=evidence.id, action='EVIDENCE_UPLOADED').one()
    assert AuditLog.query.filter_by(resource_id=evidence.id, action='EVIDENCE_UPLOADED').one()


def test_upload_rejects_binary_content_disguised_as_text(isolated_case_app):
    app, users, case, _ = isolated_case_app
    client = app.test_client()
    sign_in(client, users['investigator_b'])

    response = client.post(f'/evidence/upload/{case.id}', data={
        'name': 'Spoofed file',
        'evidence_type': 'Log',
        'file': (BytesIO(b'\x00\x01\xff'), 'spoofed.txt'),
    }, follow_redirects=True)

    assert response.status_code == 200
    assert b'Invalid file type' in response.data
    assert Evidence.query.filter_by(name='Spoofed file').first() is None


def test_investigator_transfers_evidence_between_authorized_case_users(isolated_case_app):
    app, users, case, evidence = isolated_case_app
    admin_client = app.test_client()
    sign_in(admin_client, users['admin'])
    assert admin_client.post(f'/cases/{case.id}/assign', data={'assigned_to': users['investigator_a'].id}).status_code == 302

    investigator_client = app.test_client()
    sign_in(investigator_client, users['investigator_b'])
    assert investigator_client.get(f'/evidence/{evidence.id}').status_code == 200
    response = investigator_client.post(f'/evidence/{evidence.id}/transfer', data={
        'new_custodian': users['investigator_a'].id,
        'reason': 'Authorized handoff for analysis',
    })

    assert response.status_code == 302
    event = CustodyEvent.query.filter_by(evidence_db_id=evidence.id, action='EVIDENCE_TRANSFERRED').one()
    assert event.previous_custodian == users['investigator_b'].id
    assert event.new_custodian == users['investigator_a'].id
    assert AuditLog.query.filter_by(resource_id=evidence.id, action='EVIDENCE_TRANSFERRED').one()


def test_download_rejects_storage_path_outside_upload_root(isolated_case_app):
    app, users, _, evidence = isolated_case_app
    client = app.test_client()
    sign_in(client, users['investigator_b'])
    with tempfile.TemporaryDirectory() as outside_root:
        outside_file = os.path.join(outside_root, 'outside.txt')
        with open(outside_file, 'wb') as stored_file:
            stored_file.write(b'outside')
        evidence.storage_path = outside_file
        assert client.get(f'/evidence/{evidence.id}/download').status_code == 404


def test_upload_rejects_payload_over_configured_limit(isolated_case_app):
    app, users, case, _ = isolated_case_app
    app.config['MAX_CONTENT_LENGTH'] = 128
    client = app.test_client()
    sign_in(client, users['investigator_b'])

    response = client.post(f'/evidence/upload/{case.id}', data={
        'name': 'Large upload',
        'evidence_type': 'Log',
        'file': (BytesIO(b'A' * 1024), 'large.txt'),
    })

    assert response.status_code == 413
    assert b'413' in response.data


def test_investigator_cannot_view_or_download_unrelated_evidence(isolated_case_app):
    app, users, _, evidence = isolated_case_app
    client = app.test_client()
    sign_in(client, users['investigator_a'])

    assert client.get(f'/evidence/{evidence.id}').status_code == 404
    assert client.get(f'/evidence/{evidence.id}/download').status_code == 404


def test_viewer_cannot_download_or_verify_evidence(isolated_case_app):
    app, users, _, evidence = isolated_case_app
    client = app.test_client()
    sign_in(client, users['viewer'])

    assert client.get(f'/evidence/{evidence.id}/download').status_code == 403
    assert client.post(f'/evidence/{evidence.id}/verify').status_code == 403


def test_auditor_can_view_and_verify_but_cannot_edit_or_download(isolated_case_app):
    app, users, case, evidence = isolated_case_app
    client = app.test_client()
    sign_in(client, users['auditor'])

    assert client.get(f'/cases/{case.id}').status_code == 200
    assert client.get(f'/evidence/{evidence.id}').status_code == 200
    assert client.get(f'/evidence/{evidence.id}/download').status_code == 403
    assert client.post(f'/cases/{case.id}/edit', data={}).status_code == 403
    assert client.post(f'/evidence/{evidence.id}/transfer', data={}).status_code == 403

    verified = client.post(f'/evidence/{evidence.id}/verify', follow_redirects=True)

    assert verified.status_code == 200
    assert b'Integrity Verified Successfully' in verified.data
    assert Evidence.query.get(evidence.id).status == 'VERIFIED'
    assert CustodyEvent.query.filter_by(evidence_db_id=evidence.id, action='EVIDENCE_VERIFIED').one()
    assert AuditLog.query.filter_by(resource_id=evidence.id, action='EVIDENCE_VERIFIED').one()


def test_admin_grants_and_revokes_viewer_read_access(isolated_case_app):
    app, users, case, evidence = isolated_case_app
    admin_client = app.test_client()
    sign_in(admin_client, users['admin'])
    grant_response = admin_client.post(
        f'/cases/{case.id}/viewers',
        data={'viewer_ids': users['viewer'].id},
    )
    assert grant_response.status_code == 302

    viewer_client = app.test_client()
    sign_in(viewer_client, users['viewer'])
    dashboard = viewer_client.get('/dashboard')
    assert b'Authorized Cases' in dashboard.data
    assert viewer_client.get(f'/cases/{case.id}').status_code == 200
    assert viewer_client.get(f'/evidence/{evidence.id}').status_code == 200
    assert viewer_client.get(f'/evidence/{evidence.id}/download').status_code == 403
    assert viewer_client.post(f'/evidence/{evidence.id}/verify').status_code == 403

    sign_in(admin_client, users['admin'])
    revoke_response = admin_client.post(f'/cases/{case.id}/viewers', data={})
    assert revoke_response.status_code == 302
    sign_in(viewer_client, users['viewer'])
    assert viewer_client.get(f'/cases/{case.id}').status_code == 404


def test_integrity_mismatch_is_recorded_in_status_custody_and_audit(isolated_case_app):
    app, users, _, evidence = isolated_case_app
    with open(evidence.storage_path, 'wb') as stored_file:
        stored_file.write(b'tampered evidence bytes')

    client = app.test_client()
    sign_in(client, users['investigator_b'])
    response = client.post(f'/evidence/{evidence.id}/verify', follow_redirects=True)

    assert response.status_code == 200
    assert b'Integrity Check FAILED' in response.data
    assert Evidence.query.get(evidence.id).status == 'INTEGRITY_FAILED'
    custody = CustodyEvent.query.filter_by(evidence_db_id=evidence.id, action='INTEGRITY_FAILED').one()
    assert custody.result == 'FAILURE'
    audit = AuditLog.query.filter_by(resource_id=evidence.id, action='INTEGRITY_FAILED').one()
    assert audit.result == 'FAILURE'
    assert evidence.sha256_hash in audit.description
