from app.extensions import db
from datetime import datetime
import uuid

def generate_uuid():
    return str(uuid.uuid4())

class Case(db.Model):
    __tablename__ = 'cases'
    
    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    case_id = db.Column(db.String(20), unique=True, nullable=False) # e.g., CASE-2026-0001
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    category = db.Column(db.String(50), nullable=False)
    priority = db.Column(db.String(20), nullable=False, default='MEDIUM')
    status = db.Column(db.String(20), nullable=False, default='OPEN')
    
    created_by = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False)
    assigned_to = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=True)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    closed_at = db.Column(db.DateTime, nullable=True)
    
    creator = db.relationship('User', foreign_keys=[created_by])
    
    evidence = db.relationship('Evidence', backref='case', lazy=True, cascade='all, delete-orphan')

    def __repr__(self):
        return f"<Case {self.case_id}>"
