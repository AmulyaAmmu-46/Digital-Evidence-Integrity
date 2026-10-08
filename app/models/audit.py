from app.extensions import db
from datetime import datetime
import uuid

def generate_uuid():
    return str(uuid.uuid4())

class AuditLog(db.Model):
    __tablename__ = 'audit_logs'
    
    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=True) # None for anonymous/system
    role = db.Column(db.String(20), nullable=True)
    
    action = db.Column(db.String(100), nullable=False)
    resource_type = db.Column(db.String(50), nullable=True) # e.g., 'Evidence', 'Case', 'User'
    resource_id = db.Column(db.String(36), nullable=True)
    
    ip_address = db.Column(db.String(45), nullable=True)
    result = db.Column(db.String(20), nullable=False) # 'SUCCESS', 'FAILURE'
    description = db.Column(db.Text, nullable=True)
    
    user = db.relationship('User', foreign_keys=[user_id])

    def __repr__(self):
        return f"<AuditLog {self.action} - {self.result}>"
