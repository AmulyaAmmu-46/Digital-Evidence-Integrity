from app.extensions import db
from datetime import datetime
import uuid

def generate_uuid():
    return str(uuid.uuid4())

class Evidence(db.Model):
    __tablename__ = 'evidence'
    
    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    evidence_id = db.Column(db.String(20), unique=True, nullable=False) # e.g., EVD-2026-0001
    case_db_id = db.Column(db.String(36), db.ForeignKey('cases.id'), nullable=False)
    
    name = db.Column(db.String(200), nullable=False)
    original_filename = db.Column(db.String(255), nullable=False)
    evidence_type = db.Column(db.String(50), nullable=False)
    mime_type = db.Column(db.String(100), nullable=True)
    file_size = db.Column(db.BigInteger, nullable=False)
    description = db.Column(db.Text, nullable=True)
    source = db.Column(db.String(200), nullable=True)
    
    collected_by = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=True)
    collection_date = db.Column(db.DateTime, nullable=True)
    
    upload_timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    sha256_hash = db.Column(db.String(64), nullable=False)
    status = db.Column(db.String(20), nullable=False, default='UPLOADED')
    storage_path = db.Column(db.String(500), nullable=False)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    collector = db.relationship('User', foreign_keys=[collected_by])
    custody_events = db.relationship('CustodyEvent', backref='evidence', lazy=True, cascade='all, delete-orphan')

    def __repr__(self):
        return f"<Evidence {self.evidence_id}>"
