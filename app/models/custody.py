from app.extensions import db
from datetime import datetime
import uuid

def generate_uuid():
    return str(uuid.uuid4())

class CustodyEvent(db.Model):
    __tablename__ = 'custody_events'
    
    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    evidence_db_id = db.Column(db.String(36), db.ForeignKey('evidence.id'), nullable=False)
    case_db_id = db.Column(db.String(36), db.ForeignKey('cases.id'), nullable=False)
    
    action = db.Column(db.String(50), nullable=False)
    result = db.Column(db.String(20), nullable=False, default='SUCCESS')
    performed_by = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False)
    
    previous_custodian = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=True)
    new_custodian = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=True)
    
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    reason = db.Column(db.Text, nullable=True)
    notes = db.Column(db.Text, nullable=True)
    event_hash = db.Column(db.String(64), nullable=True) # Could be hash of event details

    prev_cust = db.relationship('User', foreign_keys=[previous_custodian])
    new_cust = db.relationship('User', foreign_keys=[new_custodian])

    def __repr__(self):
        return f"<CustodyEvent {self.action} on {self.evidence_db_id}>"
