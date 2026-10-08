from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from app.models.user import User
from app.extensions import db, bcrypt
from app.services.audit_service import log_audit_event
from urllib.parse import urlsplit

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))
        
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        
        user = User.query.filter_by(email=email).first()
        password_length = len(password.encode('utf-8'))
        if user and password and password_length <= 72 and bcrypt.check_password_hash(user.password_hash, password):
            if not user.is_active:
                log_audit_event(user.id, user.role, 'LOGIN_FAILED', 'User', user.id, 'FAILURE', 'Disabled account attempted login')
                flash('Account is disabled.', 'error')
                return redirect(url_for('auth.login'))
                
            login_user(user)
            log_audit_event(user.id, user.role, 'LOGIN_SUCCESS', 'User', user.id, 'SUCCESS', 'User logged in successfully')
            next_page = request.args.get('next')
            if next_page:
                parsed_next = urlsplit(next_page)
                if not parsed_next.scheme and not parsed_next.netloc and next_page.startswith('/') and not next_page.startswith('//'):
                    return redirect(next_page)
            return redirect(url_for('dashboard.index'))
        else:
            if user:
                log_audit_event(user.id, user.role, 'LOGIN_FAILED', 'User', user.id, 'FAILURE', 'Invalid password')
            else:
                log_audit_event(None, None, 'LOGIN_FAILED', 'User', None, 'FAILURE', f'Attempted login for {email}')
            flash('Login Unsuccessful. Please check email and password', 'error')
            
    return render_template('auth/login.html')

@auth_bp.route('/logout', methods=['POST'])
@login_required
def logout():
    log_audit_event(current_user.id, current_user.role, 'LOGOUT', 'User', current_user.id, 'SUCCESS', 'User logged out')
    logout_user()
    return redirect(url_for('auth.login'))
