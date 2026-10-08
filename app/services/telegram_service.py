import json
import logging
from urllib.request import Request, urlopen

from flask import current_app
from app.extensions import db


logger = logging.getLogger(__name__)

ALERT_ACTIONS = {
    'LOGIN_SUCCESS',
    'LOGIN_FAILED',
}


def send_telegram_message(message):
    token = current_app.config.get('TELEGRAM_BOT_TOKEN')
    chat_id = current_app.config.get('TELEGRAM_CHAT_ID')
    if not token or not chat_id:
        return False

    payload = json.dumps({'chat_id': chat_id, 'text': message}).encode('utf-8')
    request = Request(
        f'https://api.telegram.org/bot{token}/sendMessage',
        data=payload,
        headers={'Content-Type': 'application/json'},
        method='POST',
    )
    try:
        with urlopen(request, timeout=3) as response:
            result = json.loads(response.read().decode('utf-8'))
        if result.get('ok') is True:
            return True
    except Exception:
        logger.warning('Telegram notification delivery failed.')
        return False

    logger.warning('Telegram notification was rejected.')
    return False


def notify_audit_event(audit_log):
    if audit_log.action not in ALERT_ACTIONS:
        return

    from app.models.user import User

    actor = db.session.get(User, audit_log.user_id) if audit_log.user_id else None
    actor_label = f'{actor.full_name} ({actor.email})' if actor else 'Unknown account'
    timestamp = audit_log.timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')
    resource = audit_log.resource_type or 'System'
    if audit_log.resource_id:
        resource = f'{resource} {audit_log.resource_id}'

    message = '\n'.join((
        f'Security alert: {audit_log.action}',
        f'Actor: {actor_label}',
        f'Role: {audit_log.role or "Unknown"}',
        f'Result: {audit_log.result}',
        f'Resource: {resource}',
        f'IP: {audit_log.ip_address or "Unavailable"}',
        f'Time: {timestamp}',
    ))
    send_telegram_message(message)