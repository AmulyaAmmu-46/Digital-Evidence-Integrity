from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app, send_file, abort
from flask_login import login_required, current_user
from app.models.evidence import Evidence
from app.models.case import Case
from app.models.user import User
from app.models.custody import CustodyEvent
from app.extensions import db
from app.services.audit_service import log_audit_event
from app.services.hashing import calculate_sha256
from app.utils.decorators import role_required
from app.utils.authorization import can_edit_case, case_for_user, visible_cases
import os
import datetime
import uuid
from werkzeug.utils import secure_filename

evidence_bp = Blueprint('evidence', __name__)

ALLOWED_EXTENSIONS = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif', 'doc', 'docx', 'csv', 'pcap', 'log', 'zip', 'tar', 'gz'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def valid_file_content(file_storage, extension):
    header = file_storage.stream.read(512)
    file_storage.stream.seek(0)
    signatures = {
        'pdf': header.startswith(b'%PDF-'),
        'png': header.startswith(b'\x89PNG\r\n\x1a\n'),
        'jpg': header.startswith(b'\xff\xd8\xff'),
        'jpeg': header.startswith(b'\xff\xd8\xff'),
        'gif': header.startswith((b'GIF87a', b'GIF89a')),
        'doc': header.startswith(b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1'),
        'docx': header.startswith(b'PK\x03\x04'),
        'zip': header.startswith(b'PK\x03\x04'),
        'gz': header.startswith(b'\x1f\x8b'),
        'tar': len(header) >= 262 and header[257:262] == b'ustar',
        'pcap': header.startswith((b'\xd4\xc3\xb2\xa1', b'\xa1\xb2\xc3\xd4', b'\x4d\x3c\xb2\xa1', b'\xa1\xb2\x3c\x4d', b'\x0a\x0d\x0d\x0a')),
    }
    if extension in signatures:
        return signatures[extension]
    return extension in ('txt', 'csv', 'log') and b'\x00' not in header


def stored_file_path(evidence):
    upload_root = os.path.realpath(current_app.config['UPLOAD_FOLDER'])
    path = os.path.realpath(evidence.storage_path)
    try:
        if os.path.commonpath((upload_root, path)) != upload_root:
            abort(404)
    except ValueError:
        abort(404)
    return path


def add_custody_event(evidence, action, reason, notes=None, previous_custodian=None, new_custodian=None, result='SUCCESS'):
    db.session.add(CustodyEvent(
        evidence_db_id=evidence.id,
        case_db_id=evidence.case_db_id,
        action=action,
        result=result,
        performed_by=current_user.id,
        previous_custodian=previous_custodian,
        new_custodian=new_custodian,
        reason=reason,
        notes=notes,
    ))

@evidence_bp.route('/')
@login_required
def index():
    query = request.args.get('q', '')
    case_ids = [case.id for case in visible_cases(Case.query, current_user).all()]
    evidence_query = Evidence.query.filter(Evidence.case_db_id.in_(case_ids))
    if query:
        evidence_query = evidence_query.filter(Evidence.name.ilike(f'%{query}%') | Evidence.evidence_id.ilike(f'%{query}%'))
    evidence = evidence_query.order_by(Evidence.created_at.desc()).all()
    return render_template('evidence/index.html', evidence=evidence, query=query)

@evidence_bp.route('/upload/<case_id>', methods=['GET', 'POST'])
@login_required
@role_required('ADMIN', 'INVESTIGATOR')
def upload(case_id):
    case = case_for_user(case_id, current_user)
    if not can_edit_case(current_user, case):
        abort(404)
    
    if request.method == 'POST':
        if 'file' not in request.files:
            flash('No file part', 'error')
            return redirect(request.url)
            
        file = request.files['file']
        if file.filename == '':
            flash('No selected file', 'error')
            return redirect(request.url)
            
        extension = file.filename.rsplit('.', 1)[1].lower() if '.' in file.filename else ''
        if file and allowed_file(file.filename) and valid_file_content(file, extension):
            original_filename = secure_filename(file.filename)
            name = request.form.get('name', '').strip()
            evidence_type = request.form.get('evidence_type', '').strip()
            description = request.form.get('description', '').strip()
            source = request.form.get('source', '').strip()
            if not original_filename or len(original_filename) > 255 or not name or len(name) > 200 or not evidence_type or len(evidence_type) > 50 or len(source) > 200 or len(description) > 10000:
                flash('Enter valid evidence details and choose an allowed file.', 'error')
                return redirect(request.url)
            
            # Generate Evidence ID
            year = datetime.datetime.now().year
            count = Evidence.query.filter(Evidence.evidence_id.like(f'EVD-{year}-%')).count() + 1
            evidence_id_str = f"EVD-{year}-{count:04d}"
            
            # Create unique server filename to prevent overwriting
            server_filename = f"{uuid.uuid4().hex}.{original_filename.rsplit('.', 1)[1].lower()}"
            storage_path = os.path.join(current_app.config['UPLOAD_FOLDER'], server_filename)
            
            try:
                file.save(storage_path)
                file_hash = calculate_sha256(storage_path)
                file_size = os.path.getsize(storage_path)
            except OSError:
                file_hash = None
                file_size = 0
            if file_hash is None:
                if os.path.exists(storage_path):
                    os.remove(storage_path)
                flash('Unable to read the uploaded file.', 'error')
                return redirect(request.url)
            
            new_evidence = Evidence(
                evidence_id=evidence_id_str,
                case_db_id=case.id,
                name=name,
                original_filename=original_filename,
                evidence_type=evidence_type,
                mime_type=file.mimetype,
                file_size=file_size,
                description=description,
                source=source,
                collected_by=current_user.id,
                sha256_hash=file_hash,
                storage_path=storage_path,
                status='UPLOADED'
            )
            
            db.session.add(new_evidence)
            db.session.flush()
            
            add_custody_event(new_evidence, 'EVIDENCE_UPLOADED', 'Initial evidence upload', f'SHA-256: {file_hash}', new_custodian=current_user.id)
            log_audit_event(current_user.id, current_user.role, 'EVIDENCE_REGISTERED', 'Evidence', new_evidence.id, 'SUCCESS', f'Registered evidence {evidence_id_str} to case {case.case_id}')
            log_audit_event(current_user.id, current_user.role, 'EVIDENCE_UPLOADED', 'Evidence', new_evidence.id, 'SUCCESS', f'Uploaded evidence {evidence_id_str}; SHA-256 {file_hash}')
            
            flash(f'Evidence {evidence_id_str} uploaded successfully.', 'success')
            return redirect(url_for('cases.view', id=case.id))
        else:
            flash('Invalid file type.', 'error')
            
    return render_template('evidence/upload.html', case=case)

@evidence_bp.route('/<id>')
@login_required
def view(id):
    evidence = Evidence.query.get_or_404(id)
    case = case_for_user(evidence.case_db_id, current_user)
    add_custody_event(evidence, 'EVIDENCE_VIEWED', 'Evidence details viewed')
    log_audit_event(current_user.id, current_user.role, 'EVIDENCE_VIEWED', 'Evidence', evidence.id, 'SUCCESS', f'Viewed evidence {evidence.evidence_id}')
    transfer_targets = []
    if current_user.role in ('ADMIN', 'INVESTIGATOR'):
        investigators = User.query.filter_by(role='INVESTIGATOR', is_active=True)
        if current_user.role != 'ADMIN':
            authorized_ids = [case.created_by, case.assigned_to]
            investigators = investigators.filter(User.id.in_(authorized_ids))
        transfer_targets = investigators.order_by(User.full_name).all()
    current_custody = CustodyEvent.query.filter_by(evidence_db_id=evidence.id).filter(
        CustodyEvent.new_custodian.isnot(None)
    ).order_by(CustodyEvent.timestamp.desc()).first()
    current_custodian_id = current_custody.new_custodian if current_custody else evidence.collected_by
    return render_template('evidence/view.html', evidence=evidence, transfer_targets=transfer_targets, current_custodian_id=current_custodian_id)

@evidence_bp.route('/<id>/verify', methods=['POST'])
@login_required
@role_required('ADMIN', 'INVESTIGATOR', 'AUDITOR')
def verify(id):
    evidence = Evidence.query.get_or_404(id)
    case_for_user(evidence.case_db_id, current_user)
    try:
        current_hash = calculate_sha256(stored_file_path(evidence))
    except OSError:
        current_hash = None
    
    if current_hash is None:
        evidence.status = 'INTEGRITY_FAILED'
        add_custody_event(evidence, 'INTEGRITY_FAILED', 'Integrity check failed', f'Original SHA-256: {evidence.sha256_hash}; current file is missing or inaccessible', result='FAILURE')
        log_audit_event(current_user.id, current_user.role, 'INTEGRITY_FAILED', 'Evidence', evidence.id, 'FAILURE', f'Original SHA-256: {evidence.sha256_hash}; current hash unavailable')
        flash('Integrity Check Failed: File is missing from storage.', 'error')
        return redirect(url_for('evidence.view', id=evidence.id))
        
    if current_hash == evidence.sha256_hash:
        evidence.status = 'VERIFIED'
        
        # Custody event for verification
        add_custody_event(evidence, 'EVIDENCE_VERIFIED', 'Integrity check completed', f'Original SHA-256: {evidence.sha256_hash}; current SHA-256: {current_hash}')
        log_audit_event(current_user.id, current_user.role, 'EVIDENCE_VERIFIED', 'Evidence', evidence.id, 'SUCCESS', f'Original SHA-256: {evidence.sha256_hash}; current SHA-256: {current_hash}')
        flash('Integrity Verified Successfully. Hash matches.', 'success')
    else:
        evidence.status = 'INTEGRITY_FAILED'
        add_custody_event(evidence, 'INTEGRITY_FAILED', 'Integrity check failed', f'Original SHA-256: {evidence.sha256_hash}; current SHA-256: {current_hash}', result='FAILURE')
        log_audit_event(current_user.id, current_user.role, 'INTEGRITY_FAILED', 'Evidence', evidence.id, 'FAILURE', f'Original SHA-256: {evidence.sha256_hash}; current SHA-256: {current_hash}')
        flash('Integrity Check FAILED! Hash mismatch detected.', 'error')
        
    return redirect(url_for('evidence.view', id=evidence.id))

@evidence_bp.route('/<id>/download')
@login_required
@role_required('ADMIN', 'INVESTIGATOR')
def download(id):
    evidence = Evidence.query.get_or_404(id)
    case_for_user(evidence.case_db_id, current_user)
    path = stored_file_path(evidence)
    if not os.path.isfile(path):
        abort(404)
    
    # Audit log
    log_audit_event(current_user.id, current_user.role, 'EVIDENCE_DOWNLOADED', 'Evidence', evidence.id, 'SUCCESS', f'Downloaded {evidence.original_filename}')
    
    # Custody log (optional for download, but good for tracking)
    add_custody_event(evidence, 'EVIDENCE_DOWNLOADED', 'Investigative analysis', 'Downloaded local copy')
    db.session.commit()
    
    return send_file(path, as_attachment=True, download_name=evidence.original_filename)


@evidence_bp.route('/<id>/transfer', methods=['POST'])
@login_required
@role_required('ADMIN', 'INVESTIGATOR')
def transfer(id):
    evidence = Evidence.query.get_or_404(id)
    case = case_for_user(evidence.case_db_id, current_user)
    if not can_edit_case(current_user, case):
        abort(404)

    recipient_id = request.form.get('new_custodian', '')
    reason = request.form.get('reason', '').strip()
    recipient = User.query.filter_by(id=recipient_id, role='INVESTIGATOR', is_active=True).first()
    if not recipient or (current_user.role != 'ADMIN' and recipient.id not in (case.created_by, case.assigned_to)) or not reason:
        abort(400)

    previous_event = CustodyEvent.query.filter_by(evidence_db_id=evidence.id).filter(
        CustodyEvent.new_custodian.isnot(None)
    ).order_by(CustodyEvent.timestamp.desc()).first()
    previous_custodian = previous_event.new_custodian if previous_event else evidence.collected_by
    if previous_custodian == recipient.id:
        abort(400)

    add_custody_event(evidence, 'EVIDENCE_TRANSFERRED', reason, previous_custodian=previous_custodian, new_custodian=recipient.id)
    log_audit_event(current_user.id, current_user.role, 'EVIDENCE_TRANSFERRED', 'Evidence', evidence.id, 'SUCCESS', f'Transferred {evidence.evidence_id} to {recipient.email}: {reason}')
    flash('Evidence custody transferred.', 'success')
    return redirect(url_for('evidence.view', id=evidence.id))
