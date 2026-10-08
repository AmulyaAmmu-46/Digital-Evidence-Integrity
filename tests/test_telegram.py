import json

from app import create_app
from app.extensions import db
from app.models.audit import AuditLog
from app.models.user import User
from app.services.audit_service import log_audit_event


class TelegramTestConfig:
    SECRET_KEY = 'test-secret'
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    UPLOAD_FOLDER = 'uploads'
    WTF_CSRF_ENABLED = False
    TELEGRAM_BOT_TOKEN = 'test-token'
    TELEGRAM_CHAT_ID = '12345'


class FakeResponse:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def read(self):
        return b'{"ok": true}'


def test_login_audit_sends_minimal_telegram_alert(monkeypatch):
    captured = {}
    requests = []

    def fake_urlopen(request, timeout):
        captured['request'] = request
        captured['timeout'] = timeout
        requests.append(request)
        return FakeResponse()

    monkeypatch.setattr('app.services.telegram_service.urlopen', fake_urlopen)
    app = create_app(TelegramTestConfig)
    with app.app_context():
        db.create_all()
        user = User(
            email='admin@example.test',
            full_name='Admin User',
            role='ADMIN',
            password_hash='unused',
        )
        db.session.add(user)
        db.session.commit()

        with app.test_request_context('/', environ_base={'REMOTE_ADDR': '192.0.2.1'}):
            audit_log = log_audit_event(
                user.id,
                user.role,
                'LOGIN_SUCCESS',
                'User',
                user.id,
                'SUCCESS',
                'This description must not be sent',
            )
            log_audit_event(
                user.id,
                user.role,
                'EVIDENCE_VIEWED',
                'Evidence',
                'evidence-id',
                'SUCCESS',
            )

        message = json.loads(captured['request'].data)['text']
        assert len(requests) == 1
        assert captured['timeout'] == 3
        assert 'LOGIN_SUCCESS' in message
        assert 'Admin User (admin@example.test)' in message
        assert '192.0.2.1' in message
        assert 'This description must not be sent' not in message
        assert AuditLog.query.filter_by(id=audit_log.id).one()
        db.drop_all()


def test_telegram_failure_does_not_prevent_audit_commit(monkeypatch):
    def failing_urlopen(request, timeout):
        raise TimeoutError('Telegram timed out')

    monkeypatch.setattr('app.services.telegram_service.urlopen', failing_urlopen)
    app = create_app(TelegramTestConfig)
    with app.app_context():
        db.create_all()
        user = User(
            email='admin@example.test',
            full_name='Admin User',
            role='ADMIN',
            password_hash='unused',
        )
        db.session.add(user)
        db.session.commit()

        with app.test_request_context('/'):
            audit_log = log_audit_event(
                user.id,
                user.role,
                'LOGIN_SUCCESS',
                'User',
                user.id,
                'SUCCESS',
            )

        assert AuditLog.query.filter_by(id=audit_log.id).one()
        db.drop_all()