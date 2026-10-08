from datetime import datetime
import uuid

from app.extensions import db


def generate_uuid():
    return str(uuid.uuid4())


class CaseViewerGrant(db.Model):
    __tablename__ = 'case_viewer_grants'
    __table_args__ = (db.UniqueConstraint('case_id', 'viewer_id', name='uq_case_viewer_grant'),)

    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    case_id = db.Column(db.String(36), db.ForeignKey('cases.id'), nullable=False)
    viewer_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False)
    granted_by = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    viewer = db.relationship('User', foreign_keys=[viewer_id])
    grantor = db.relationship('User', foreign_keys=[granted_by])