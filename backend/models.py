from datetime import datetime, date
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
import random
import string

db = SQLAlchemy()
bcrypt = Bcrypt()

# ─── ROLES ──────────────────────────────────────────────
ROLES = ['admin', 'pastor', 'secretary', 'treasurer', 'viewer']

# ─── USER ───────────────────────────────────────────────
class User(db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='viewer')
    full_name = db.Column(db.String(150))
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime)

    def set_password(self, password):
        self.password_hash = bcrypt.generate_password_hash(password).decode('utf-8')

    def check_password(self, password):
        return bcrypt.check_password_hash(self.password_hash, password)

    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'full_name': self.full_name,
            'role': self.role,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'last_login': self.last_login.isoformat() if self.last_login else None
        }

    def can(self, action):
        permissions = {
            'admin':     ['read', 'write', 'delete', 'manage_users', 'manage_finance', 'reports'],
            'pastor':    ['read', 'write', 'reports'],
            'secretary': ['read', 'write'],
            'treasurer': ['read', 'write', 'manage_finance', 'reports'],
            'viewer':    ['read']
        }
        return action in permissions.get(self.role, [])


# ─── MEMBER ─────────────────────────────────────────────
class Member(db.Model):
    __tablename__ = 'members'

    id = db.Column(db.Integer, primary_key=True)
    member_id = db.Column(db.String(15), unique=True, nullable=False)  # CHR-XXXXXX
    first_name = db.Column(db.String(80), nullable=False)
    last_name = db.Column(db.String(80), nullable=False)
    email = db.Column(db.String(120))
    phone = db.Column(db.String(20))
    date_of_birth = db.Column(db.Date)
    gender = db.Column(db.String(10))
    address = db.Column(db.Text)
    occupation = db.Column(db.String(100))
    marital_status = db.Column(db.String(20))
    next_of_kin = db.Column(db.String(150))
    next_of_kin_phone = db.Column(db.String(20))
    cell_group = db.Column(db.String(80))
    baptism_date = db.Column(db.Date)
    date_joined = db.Column(db.Date, default=date.today)
    membership_status = db.Column(db.String(20), default='active')  # active, inactive, transferred, deceased
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    attendance_records = db.relationship('Attendance', backref='member', lazy='dynamic')
    finance_records = db.relationship('Finance', backref='member', lazy='dynamic')

    @staticmethod
    def generate_member_id():
        while True:
            suffix = ''.join(random.choices(string.digits, k=6))
            mid = f'CHR-{suffix}'
            if not Member.query.filter_by(member_id=mid).first():
                return mid

    @property
    def full_name(self):
        return f'{self.first_name} {self.last_name}'

    def to_dict(self, include_stats=False):
        data = {
            'id': self.id,
            'member_id': self.member_id,
            'first_name': self.first_name,
            'last_name': self.last_name,
            'full_name': self.full_name,
            'email': self.email,
            'phone': self.phone,
            'date_of_birth': self.date_of_birth.isoformat() if self.date_of_birth else None,
            'gender': self.gender,
            'address': self.address,
            'occupation': self.occupation,
            'marital_status': self.marital_status,
            'next_of_kin': self.next_of_kin,
            'next_of_kin_phone': self.next_of_kin_phone,
            'cell_group': self.cell_group,
            'baptism_date': self.baptism_date.isoformat() if self.baptism_date else None,
            'date_joined': self.date_joined.isoformat() if self.date_joined else None,
            'membership_status': self.membership_status,
            'notes': self.notes,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }
        if include_stats:
            data['total_attendance'] = self.attendance_records.count()
            data['total_giving'] = sum(
                f.amount for f in self.finance_records.filter_by(transaction_type='tithe')
            ) + sum(
                f.amount for f in self.finance_records.filter_by(transaction_type='offering')
            )
        return data


# ─── ATTENDANCE ─────────────────────────────────────────
SERVICE_TYPES = [
    'Sunday Morning', 'Sunday Evening', 'Wednesday Bible Study',
    'Friday Prayer', 'Special Service', 'Youth Service', 'Other'
]

class Attendance(db.Model):
    __tablename__ = 'attendance'

    id = db.Column(db.Integer, primary_key=True)
    member_id = db.Column(db.Integer, db.ForeignKey('members.id'), nullable=False)
    service_type = db.Column(db.String(50), nullable=False)
    service_date = db.Column(db.Date, nullable=False)
    notes = db.Column(db.Text)
    recorded_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'member_id': self.member_id,
            'member_name': self.member.full_name if self.member else None,
            'member_code': self.member.member_id if self.member else None,
            'service_type': self.service_type,
            'service_date': self.service_date.isoformat() if self.service_date else None,
            'notes': self.notes,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


# ─── FINANCE ────────────────────────────────────────────
TRANSACTION_TYPES = ['tithe', 'offering', 'donation', 'expense', 'project_fund', 'other']
FINANCE_CATEGORIES = [
    'General Offering', 'Tithe', 'Building Fund', 'Mission Fund',
    'Welfare Fund', 'Youth Fund', 'Expense - Utilities', 'Expense - Salaries',
    'Expense - Equipment', 'Expense - Events', 'Other'
]

class Finance(db.Model):
    __tablename__ = 'finance'

    id = db.Column(db.Integer, primary_key=True)
    reference = db.Column(db.String(20), unique=True, nullable=False)  # FIN-YYYYMMDD-XXXX
    transaction_type = db.Column(db.String(20), nullable=False)
    category = db.Column(db.String(80))
    amount = db.Column(db.Numeric(12, 2), nullable=False)
    currency = db.Column(db.String(5), default='KES')
    description = db.Column(db.Text)
    member_id = db.Column(db.Integer, db.ForeignKey('members.id'), nullable=True)
    payment_method = db.Column(db.String(30))  # cash, mpesa, bank, cheque
    mpesa_ref = db.Column(db.String(30))
    transaction_date = db.Column(db.Date, nullable=False)
    recorded_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    verified = db.Column(db.Boolean, default=False)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    @staticmethod
    def generate_reference():
        from datetime import datetime
        date_str = datetime.now().strftime('%Y%m%d')
        suffix = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
        return f'FIN-{date_str}-{suffix}'

    def to_dict(self):
        return {
            'id': self.id,
            'reference': self.reference,
            'transaction_type': self.transaction_type,
            'category': self.category,
            'amount': float(self.amount),
            'currency': self.currency,
            'description': self.description,
            'member_id': self.member_id,
            'member_name': self.member.full_name if self.member else None,
            'payment_method': self.payment_method,
            'mpesa_ref': self.mpesa_ref,
            'transaction_date': self.transaction_date.isoformat() if self.transaction_date else None,
            'verified': self.verified,
            'notes': self.notes,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


# ─── EVENT ──────────────────────────────────────────────
class Event(db.Model):
    __tablename__ = 'events'

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    event_type = db.Column(db.String(50))  # service, conference, outreach, meeting, other
    location = db.Column(db.String(200))
    start_date = db.Column(db.DateTime, nullable=False)
    end_date = db.Column(db.DateTime)
    is_recurring = db.Column(db.Boolean, default=False)
    recurrence_pattern = db.Column(db.String(50))
    max_attendees = db.Column(db.Integer)
    status = db.Column(db.String(20), default='upcoming')  # upcoming, ongoing, completed, cancelled
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'description': self.description,
            'event_type': self.event_type,
            'location': self.location,
            'start_date': self.start_date.isoformat() if self.start_date else None,
            'end_date': self.end_date.isoformat() if self.end_date else None,
            'is_recurring': self.is_recurring,
            'recurrence_pattern': self.recurrence_pattern,
            'max_attendees': self.max_attendees,
            'status': self.status,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }
