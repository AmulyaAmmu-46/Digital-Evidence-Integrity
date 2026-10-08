from flask import Blueprint, render_template, redirect, url_for, flash, request, abort
from flask_login import login_required, current_user
from app.models.case import Case
from app.models.user import User
from app.models.case_viewer_grant import CaseViewerGrant
from app.extensions import db
from app.services.audit_service import log_audit_event
from app.utils.decorators import role_required
from app.utils.authorization import can_edit_case, case_for_user, visible_cases
import datetime

cases_bp = Blueprint('cases', __name__)

@cases_bp.route('/')
@login_required
def index():
    query = request.args.get('q', '')
    cases_query = visible_cases(Case.query, current_user)
    if query:
        cases_query = cases_query.filter(Case.title.ilike(f'%{query}%') | Case.case_id.ilike(f'%{query}%'))
    cases = cases_query.order_by(Case.created_at.desc()).all()
    return render_template('cases/index.html', cases=cases, query=query)

@cases_bp.route('/create', methods=['GET', 'POST'])
@login_required
@role_required('ADMIN', 'INVESTIGATOR')
def create():
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        description = request.form.get('description', '').strip()
        category = request.form.get('category', '')
        priority = request.form.get('priority', '')
        if not title or len(title) > 200 or category not in ('Cyber Incident', 'Data Breach', 'Malware Investigation', 'Insider Threat', 'Fraud Investigation', 'Network Investigation', 'Other') or priority not in ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL'):
            flash('Enter valid case details.', 'error')
            investigators = User.query.filter_by(role='INVESTIGATOR', is_active=True).order_by(User.full_name).all()
            return render_template('cases/create.html', investigators=investigators), 400

        assigned_to = current_user.id if current_user.role == 'INVESTIGATOR' else None
        if current_user.role == 'ADMIN':
            assigned_to = request.form.get('assigned_to') or None
            if assigned_to and not User.query.filter_by(id=assigned_to, role='INVESTIGATOR', is_active=True).first():
                abort(400)
        
        # Generate Case ID (e.g., CASE-2026-0001)
        year = datetime.datetime.now().year
        count = Case.query.filter(Case.case_id.like(f'CASE-{year}-%')).count() + 1
        case_id_str = f"CASE-{year}-{count:04d}"
        
        new_case = Case(
            case_id=case_id_str,
            title=title,
            description=description,
            category=category,
            priority=priority,
            created_by=current_user.id,
            assigned_to=assigned_to
        )
        
        db.session.add(new_case)
        db.session.commit()
        
        log_audit_event(current_user.id, current_user.role, 'CASE_CREATED', 'Case', new_case.id, 'SUCCESS', f'Created case {case_id_str}')
        if assigned_to:
            log_audit_event(current_user.id, current_user.role, 'CASE_ASSIGNED', 'Case', new_case.id, 'SUCCESS', f'Assigned case {case_id_str}')
        flash(f'Case {case_id_str} created successfully.', 'success')
        return redirect(url_for('cases.view', id=new_case.id))
        
    investigators = User.query.filter_by(role='INVESTIGATOR', is_active=True).order_by(User.full_name).all()
    return render_template('cases/create.html', investigators=investigators)

@cases_bp.route('/<id>')
@login_required
def view(id):
    case = case_for_user(id, current_user)
    log_audit_event(current_user.id, current_user.role, 'CASE_VIEWED', 'Case', case.id, 'SUCCESS', f'Viewed case {case.case_id}')
    investigators = User.query.filter_by(role='INVESTIGATOR', is_active=True).order_by(User.full_name).all()
    viewers = User.query.filter_by(role='VIEWER', is_active=True).order_by(User.full_name).all()
    viewer_grants = CaseViewerGrant.query.filter_by(case_id=case.id).all()
    viewer_grant_ids = [grant.viewer_id for grant in viewer_grants]
    return render_template('cases/view.html', case=case, investigators=investigators, viewers=viewers, viewer_grants=viewer_grants, viewer_grant_ids=viewer_grant_ids)


@cases_bp.route('/<id>/edit', methods=['GET', 'POST'])
@login_required
@role_required('ADMIN', 'INVESTIGATOR')
def edit(id):
    case = case_for_user(id, current_user)
    if not can_edit_case(current_user, case):
        abort(404)

    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        category = request.form.get('category', '')
        priority = request.form.get('priority', '')
        if not title or len(title) > 200 or category not in ('Cyber Incident', 'Data Breach', 'Malware Investigation', 'Insider Threat', 'Fraud Investigation', 'Network Investigation', 'Other') or priority not in ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL'):
            flash('Enter valid case details.', 'error')
            return render_template('cases/edit.html', case=case), 400

        previous_status = case.status
        case.title = title
        case.description = request.form.get('description', '').strip()
        case.category = category
        case.priority = priority
        if current_user.role == 'ADMIN':
            status = request.form.get('status', case.status)
            if status not in ('OPEN', 'IN_PROGRESS', 'CLOSED', 'ARCHIVED'):
                abort(400)
            case.status = status
            case.closed_at = datetime.datetime.utcnow() if status in ('CLOSED', 'ARCHIVED') else None
        db.session.commit()
        log_audit_event(current_user.id, current_user.role, 'CASE_UPDATED', 'Case', case.id, 'SUCCESS', f'Updated case {case.case_id}')
        if previous_status != case.status:
            log_audit_event(current_user.id, current_user.role, 'STATUS_CHANGED', 'Case', case.id, 'SUCCESS', f'Changed case {case.case_id} from {previous_status} to {case.status}')
        flash(f'Case {case.case_id} updated.', 'success')
        return redirect(url_for('cases.view', id=case.id))

    return render_template('cases/edit.html', case=case)


@cases_bp.route('/<id>/assign', methods=['POST'])
@login_required
@role_required('ADMIN')
def assign(id):
    case = Case.query.get_or_404(id)
    assigned_to = request.form.get('assigned_to') or None
    if assigned_to and not User.query.filter_by(id=assigned_to, role='INVESTIGATOR', is_active=True).first():
        abort(400)
    previous_assignee = case.assigned_to
    case.assigned_to = assigned_to
    db.session.commit()
    log_audit_event(current_user.id, current_user.role, 'CASE_ASSIGNED', 'Case', case.id, 'SUCCESS', f'Changed assignment for case {case.case_id} from {previous_assignee or "unassigned"} to {assigned_to or "unassigned"}')
    flash(f'Assignment updated for {case.case_id}.', 'success')
    return redirect(url_for('cases.view', id=case.id))


@cases_bp.route('/<id>/viewers', methods=['POST'])
@login_required
@role_required('ADMIN')
def update_viewers(id):
    case = Case.query.get_or_404(id)
    requested_ids = set(request.form.getlist('viewer_ids'))
    requested_viewers = User.query.filter(
        User.id.in_(requested_ids),
        User.role == 'VIEWER',
        User.is_active.is_(True),
    ).all() if requested_ids else []
    if len(requested_viewers) != len(requested_ids):
        abort(400)

    existing_grants = {grant.viewer_id: grant for grant in CaseViewerGrant.query.filter_by(case_id=case.id).all()}
    granted = []
    revoked = []
    for viewer_id in requested_ids - set(existing_grants):
        db.session.add(CaseViewerGrant(case_id=case.id, viewer_id=viewer_id, granted_by=current_user.id))
        granted.append(viewer_id)
    for viewer_id in set(existing_grants) - requested_ids:
        db.session.delete(existing_grants[viewer_id])
        revoked.append(viewer_id)
    db.session.commit()

    for viewer_id in granted:
        log_audit_event(current_user.id, current_user.role, 'CASE_VIEWER_ACCESS_GRANTED', 'Case', case.id, 'SUCCESS', f'Granted Viewer {viewer_id} read access to {case.case_id}')
    for viewer_id in revoked:
        log_audit_event(current_user.id, current_user.role, 'CASE_VIEWER_ACCESS_REVOKED', 'Case', case.id, 'SUCCESS', f'Revoked Viewer {viewer_id} read access to {case.case_id}')
    flash(f'Viewer access updated for {case.case_id}.', 'success')
    return redirect(url_for('cases.view', id=case.id))
