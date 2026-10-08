from app.extensions import db
from flask_login import UserMixin
from datetime import datetime
import uuid

def generate_uuid():
    return str(uuid.uuid4())

class User(db.Model, UserMixin):
    __tablename__ = 'users'
    
    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    full_name = db.Column(db.String(100), nullable=False)
    role = db.Column(db.String(20), nullable=False) # ADMIN, INVESTIGATOR, AUDITOR, VIEWER
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    cases = db.relationship('Case', backref='investigator', lazy=True, foreign_keys='Case.assigned_to')
    custody_events = db.relationship('CustodyEvent', backref='performed_by_user', lazy=True, foreign_keys='CustodyEvent.performed_by')
    
    def __repr__(self):
        return f"<User {self.email} ({self.role})>"
