from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import func

from app.extensions import bcrypt, db
from app.models.user import User
from app.models.case_viewer_grant import CaseViewerGrant
from app.services.audit_service import log_audit_event
from app.utils.decorators import role_required

users_bp = Blueprint('users', __name__)
ACCOUNT_ROLES = ('INVESTIGATOR', 'AUDITOR', 'VIEWER')
ALL_ROLES = ('ADMIN',) + ACCOUNT_ROLES


@users_bp.route('/', methods=['GET', 'POST'])
@login_required
@role_required('ADMIN')
def index():
    if request.method == 'POST':
        full_name = request.form.get('full_name', '').strip()
        email = request.form.get('email', '').strip().lower()
        role = request.form.get('role', '')
        password = request.form.get('password', '')
        password_confirmation = request.form.get('password_confirmation', '')

        if not full_name or len(full_name) > 100:
            flash('Enter a name up to 100 characters long.', 'error')
        elif not email or len(email) > 120:
            flash('Enter a valid email address up to 120 characters long.', 'error')
        elif role not in ACCOUNT_ROLES:
            flash('Choose Investigator, Auditor, or Viewer.', 'error')
        elif len(password) < 12:
            flash('Use a password with at least 12 characters.', 'error')
        elif len(password.encode('utf-8')) > 72:
            flash('Password must be no longer than 72 bytes.', 'error')
        elif password != password_confirmation:
            flash('The passwords do not match.', 'error')
        elif User.query.filter(func.lower(User.email) == email).first():
            flash('An account with that email already exists.', 'error')
        else:
            user = User(
                email=email,
                full_name=full_name,
                role=role,
                password_hash=bcrypt.generate_password_hash(password).decode('utf-8'),
            )
            db.session.add(user)
            db.session.commit()
            log_audit_event(
                current_user.id,
                current_user.role,
                'USER_CREATED',
                'User',
                user.id,
                'SUCCESS',
                f'Created {role} account for {email}',
            )
            flash(f'{role.title()} account created for {email}.', 'success')
            return redirect(url_for('users.index'))

    users = User.query.order_by(User.created_at.desc()).all()
    return render_template('users/index.html', users=users, account_roles=ALL_ROLES)


@users_bp.route('/<user_id>/update', methods=['POST'])
@login_required
@role_required('ADMIN')
def update(user_id):
    user = User.query.get_or_404(user_id)
    new_role = request.form.get('role', '')
    new_active = 'true' in request.form.getlist('is_active')
    if new_role not in ALL_ROLES:
        flash('Choose a valid user role.', 'error')
        return redirect(url_for('users.index'))

    if user.id == current_user.id and (new_role != 'ADMIN' or not new_active):
        flash('You cannot demote or disable your own administrator account.', 'error')
        return redirect(url_for('users.index'))

    if user.role == 'ADMIN' and (new_role != 'ADMIN' or not new_active):
        active_admins = User.query.filter_by(role='ADMIN', is_active=True).count()
        if active_admins <= 1:
            flash('The last active administrator cannot be demoted or disabled.', 'error')
            return redirect(url_for('users.index'))

    old_role = user.role
    old_active = user.is_active
    revoked_case_ids = []
    if old_role == 'VIEWER' and (new_role != 'VIEWER' or not new_active):
        revoked_grants = CaseViewerGrant.query.filter_by(viewer_id=user.id).all()
        revoked_case_ids = [grant.case_id for grant in revoked_grants]
        for grant in revoked_grants:
            db.session.delete(grant)
    user.role = new_role
    user.is_active = new_active
    db.session.commit()

    if old_role != new_role:
        log_audit_event(current_user.id, current_user.role, 'USER_ROLE_CHANGED', 'User', user.id, 'SUCCESS', f'Changed role for {user.email} from {old_role} to {new_role}')
    for case_id in revoked_case_ids:
        log_audit_event(current_user.id, current_user.role, 'CASE_VIEWER_ACCESS_REVOKED', 'Case', case_id, 'SUCCESS', f'Revoked Viewer access after account update for {user.email}')
    if old_active != new_active:
        log_audit_event(current_user.id, current_user.role, 'USER_ACCOUNT_STATUS_CHANGED', 'User', user.id, 'SUCCESS', f'{"Enabled" if new_active else "Disabled"} account for {user.email}')
    flash(f'Account updated for {user.email}.', 'success')
    return redirect(url_for('users.index'))