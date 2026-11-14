# ── Kenya constants (required by routes/churches.py) ──────────────────────────
KENYAN_COUNTIES = [
    'Mombasa','Kwale','Kilifi','Tana River','Lamu','Taita Taveta',
    'Garissa','Wajir','Mandera','Marsabit','Isiolo','Meru',
    'Tharaka-Nithi','Embu','Kitui','Machakos','Makueni',
    'Nyandarua','Nyeri','Kirinyaga',"Murang'a",'Kiambu',
    'Turkana','West Pokot','Samburu','Trans Nzoia','Uasin Gishu',
    'Elgeyo-Marakwet','Nandi','Baringo','Laikipia','Nakuru',
    'Narok','Kajiado','Kericho','Bomet','Kakamega','Vihiga',
    'Bungoma','Busia','Siaya','Kisumu','Homa Bay','Migori',
    'Kisii','Nyamira','Nairobi',
]  # 47 counties

DENOMINATIONS = [
    'Ministry of Repentance and Holiness',
    'Pentecostal Assemblies of God (PAG)',
    'Anglican Church of Kenya (ACK)',
    'Roman Catholic',
    'Presbyterian Church of East Africa (PCEA)',
    'Africa Inland Church (AIC)',
    'Full Gospel Churches of Kenya',
    'Seventh Day Adventist (SDA)',
    'Baptist Convention of Kenya',
    'Methodist Church in Kenya',
    'Redeemed Gospel Church',
    'Deliverance Church',
    'CITAM (Christ is the Answer Ministries)',
    'Nairobi Chapel',
    'Assemblies of God',
    'Africa Gospel Church',
    'Friends Church Kenya (Quakers)',
    'Salvation Army Kenya',
    'Other',
]

CHURCH_SIZES = [
    'Small (under 50 members)',
    'Medium (50-200 members)',
    'Large (200-1,000 members)',
    'Cathedral (1,000+ members)',
]

SUBSCRIPTION_PLANS = ['trial', 'seed', 'growth', 'parish', 'cathedral']

PLAN_LIMITS = {
    'trial':    {'members': 50,    'price_kes': 0},
    'seed':     {'members': 100,   'price_kes': 1500},
    'growth':   {'members': 500,   'price_kes': 4500},
    'parish':   {'members': 2000,  'price_kes': 9000},
    'cathedral':{'members': 99999, 'price_kes': 18000},
}

from datetime import datetime, date
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
import random
import string

db = SQLAlchemy()
bcrypt = Bcrypt()

ROLES = ['admin', 'pastor', 'secretary', 'treasurer', 'viewer']

KENYAN_COUNTIES = [
    'Mombasa', 'Kwale', 'Kilifi', 'Tana River', 'Lamu', 'Taita Taveta',
    'Garissa', 'Wajir', 'Mandera', 'Marsabit', 'Isiolo', 'Meru',
    'Tharaka-Nithi', 'Embu', 'Kitui', 'Machakos', 'Makueni',
    'Nyandarua', 'Nyeri', 'Kirinyaga', "Murang'a", 'Kiambu',
    'Turkana', 'West Pokot', 'Samburu', 'Trans Nzoia', 'Uasin Gishu',
    'Elgeyo-Marakwet', 'Nandi', 'Baringo', 'Laikipia', 'Nakuru',
    'Narok', 'Kajiado', 'Kericho', 'Bomet', 'Kakamega', 'Vihiga',
    'Bungoma', 'Busia', 'Siaya', 'Kisumu', 'Homa Bay', 'Migori',
    'Kisii', 'Nyamira', 'Nairobi'
]

DENOMINATIONS = [
    'Migosi Main Altar',
    'Ministry of Repentance and Holiness',
    'Pentecostal Assemblies of God (PAG)',
    'Anglican Church of Kenya (ACK)',
    'Roman Catholic',
    'Presbyterian Church of East Africa (PCEA)',
    'Africa Inland Church (AIC)',
    'Full Gospel Churches of Kenya',
    'Seventh Day Adventist (SDA)',
    'Baptist Convention of Kenya',
    'Methodist Church in Kenya',
    'Redeemed Gospel Church',
    'Deliverance Church',
    'CITAM (Christ is the Answer Ministries)',
    'Nairobi Chapel',
    'House of Grace',
    'New Life Fellowship',
    'Calvary Temple',
    'Assemblies of God',
    'Africa Gospel Church',
    'Friends Church Kenya (Quakers)',
    'Salvation Army Kenya',
    'Other'
]

CHURCH_SIZES = [
    'Small (under 50 members)',
    'Medium (50-200 members)',
    'Large (200-1,000 members)',
    'Cathedral (1,000+ members)'
]

SUBSCRIPTION_PLANP = ['trial', 'seed', 'growth', 'parish', 'cathedral']

PLAN_LIMITS = {
    'trial':     {'members': 50,    'price_kes': 0},
    'seed':      {'members': 100,    'price_kes': 1500},
    'growth':    {'members': 500,    'price_kes': 4500},
    'parish':    {'members': 2000,   'price_kes': 9000},
    'cathedral': {'members': 99999,  'price_kes': 18000},
}

SERVICE_TYPES = [
    'Sunday Morning', 'Sunday Evening', 'Wednesday Bible Study',
    'Friday Prayer', 'Special Service', 'Youth Service', 'Other'
]

TRANSACTION_TYPES = ['tithe', 'offering', 'donation', 'expense', 'project_fund', 'other']

FINANCE_CATEGORIES = [
    'General Offering', 'Tithe', 'Building Fund', 'Mission Fund',
    'Welfare Fund', 'Youth Fund', 'Expense - Utilities', 'Expense - Salaries',
    'Expense - Equipment', 'Expense - Events', 'Other'
]


class Church(db.Model):
    __tablename__ = 'churches'
    id                = db.Column(db.Integer, primary_key=True)
    name              = db.Column(db.String(200), nullable=False)
    county            = db.Column(db.String(80))
    sub_county        = db.Column(db.String(80))
    denomination      = db.Column(db.String(100))
    size              = db.Column(db.String(50))
    paybill           = db.Column(db.String(20))
    till_number       = db.Column(db.String(20))
    phone             = db.Column(db.String(20))
    email             = db.Column(db.String(120))
    address           = db.Column(db.Text)
    member_prefix     = db.Column(db.String(10), default='CHR')
    subscription_plan = db.Column(db.String(20), default='trial')
    trial_ends_at     = db.Column(db.DateTime)
    paid_until        = db.Column(db.DateTime)
    denomination_id   = db.Column(db.Integer)
    region_id         = db.Column(db.Integer, index=True)
    is_seat           = db.Column(db.Boolean, default=False)
    region_sms_ok     = db.Column(db.Boolean, default=False)
    is_active         = db.Column(db.Boolean, default=True)
    created_at        = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at        = db.Column(db.DateTime, default=datetime.utcnow,
                                   onupdate=datetime.utcnow)
    users   = db.relationship('User',   backref='church', lazy='dynamic')
    members = db.relationship('Member', backref='church', lazy='dynamic')
    events  = db.relationship('Event',  backref='church', lazy='dynamic')

    def to_dict(self):
        return {
            'id': self.id, 'name': self.name,
            'county': self.county, 'sub_county': self.sub_county,
            'denomination': self.denomination, 'size': self.size,
            'paybill': self.paybill, 'till_number': self.till_number,
            'phone': self.phone, 'email': self.email,
            'address': self.address, 'member_prefix': self.member_prefix,
            'subscription_plan': self.subscription_plan,
            'trial_ends_at': self.trial_ends_at.isoformat() if self.trial_ends_at else None,
            'is_active': self.is_active,
            'member_count': self.members.count(),
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class User(db.Model):
    __tablename__ = 'users'
    id            = db.Column(db.Integer, primary_key=True)
    church_id     = db.Column(db.Integer, db.ForeignKey('churches.id'), nullable=True)
    username      = db.Column(db.String(80), unique=True, nullable=True)
    email         = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    role          = db.Column(db.String(20), nullable=False, default='viewer')
    full_name     = db.Column(db.String(150))
    is_active     = db.Column(db.Boolean, default=True)
    created_at    = db.Column(db.DateTime, default=datetime.utcnow)
    last_login    = db.Column(db.DateTime)
    failed_logins = db.Column(db.Integer, default=0)
    locked_until  = db.Column(db.DateTime)
    token_version = db.Column(db.Integer, default=0)
    is_platform_owner = db.Column(db.Boolean, default=False)

    def set_password(self, p):
        self.password_hash = bcrypt.generate_password_hash(p).decode('utf-8')
    def check_password(self, p):
        return bcrypt.check_password_hash(self.password_hash, p)
    def to_dict(self):
        return {
            'id': self.id, 'church_id': self.church_id,
            'username': getattr(self, 'username', '') or '',
            'email': self.email, 'full_name': self.full_name,
            'role': self.role, 'is_active': self.is_active,
            'is_platform_owner': bool(self.is_platform_owner),
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'last_login': self.last_login.isoformat() if self.last_login else None
        }
    def can(self, action):
        perms = {
            'admin':     ['read', 'write', 'delete', 'manage_users', 'manage_finance', 'reports'],
            'pastor':    ['read', 'write', 'reports'],
            'secretary': ['read', 'write'],
            'treasurer': ['read', 'write', 'manage_finance', 'reports'],
            'viewer':    ['read']
        }
        return action in perms.get(self.role, [])


class Member(db.Model):
    __tablename__ = 'members'
    id                = db.Column(db.Integer, primary_key=True)
    church_id         = db.Column(db.Integer, db.ForeignKey('churches.id'), nullable=True)
    member_id         = db.Column(db.String(15), unique=True, nullable=False)
    first_name        = db.Column(db.String(80), nullable=False)
    last_name         = db.Column(db.String(80), nullable=False)
    email             = db.Column(db.String(120))
    phone             = db.Column(db.String(20))
    date_of_birth     = db.Column(db.Date)
    gender            = db.Column(db.String(10))
    county            = db.Column(db.String(80))
    sub_county        = db.Column(db.String(80))
    address           = db.Column(db.Text)
    occupation        = db.Column(db.String(100))
    marital_status    = db.Column(db.String(20))
    next_of_kin       = db.Column(db.String(150))
    next_of_kin_phone = db.Column(db.String(20))
    cell_group        = db.Column(db.String(80))
    baptism_date      = db.Column(db.Date)
    date_joined       = db.Column(db.Date, default=date.today)
    membership_status = db.Column(db.String(20), default='active')
    notes             = db.Column(db.Text)
    consent_at        = db.Column(db.DateTime)
    consent_version   = db.Column(db.String(20))
    sms_ok            = db.Column(db.Boolean, default=False)
    sms_ok_at         = db.Column(db.DateTime)
    erased_at         = db.Column(db.DateTime)
    created_at        = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at        = db.Column(db.DateTime, default=datetime.utcnow,
                                   onupdate=datetime.utcnow)
    attendance_records = db.relationship('Attendance', backref='member', lazy='dynamic')
    finance_records    = db.relationship('Finance',    backref='member', lazy='dynamic')

    @staticmethod
    def generate_member_id(prefix='CHR'):
        while True:
            mid = f"{prefix}-{''.join(random.choices(string.digits, k=6))}"
            if not Member.query.filter_by(member_id=mid).first():
                return mid

    @property
    def full_name(self):
        return f'{self.first_name} {self.last_name}'

    def to_dict(self, include_stats=False):
        data = {
            'id': self.id, 'church_id': self.church_id,
            'member_id': self.member_id,
            'first_name': self.first_name, 'last_name': self.last_name,
            'full_name': self.full_name,
            'email': self.email, 'phone': self.phone,
            'date_of_birth': self.date_of_birth.isoformat() if self.date_of_birth else None,
            'gender': self.gender, 'county': self.county,
            'sub_county': self.sub_county,
            'address': self.address, 'occupation': self.occupation,
            'marital_status': self.marital_status,
            'next_of_kin': self.next_of_kin,
            'next_of_kin_phone': self.next_of_kin_phone,
            'cell_group': self.cell_group,
            'baptism_date': self.baptism_date.isoformat() if self.baptism_date else None,
            'date_joined': self.date_joined.isoformat() if self.date_joined else None,
            'membership_status': self.membership_status,
            'notes': self.notes,
            'consent_at': self.consent_at.isoformat() if self.consent_at else None,
            'consent_version': self.consent_version,
            'erased': self.erased_at is not None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }
        if include_stats:
            data['total_attendance'] = self.attendance_records.count()
            data['total_giving'] = float(sum(
                f.amount for f in self.finance_records
                if f.transaction_type in ('tithe', 'offering') and f.status != 'void'))
        return data


class Attendance(db.Model):
    __tablename__ = 'attendance'
    id           = db.Column(db.Integer, primary_key=True)
    church_id    = db.Column(db.Integer, db.ForeignKey('churches.id'), nullable=True)
    member_id    = db.Column(db.Integer, db.ForeignKey('members.id'), nullable=False)
    service_type = db.Column(db.String(50), nullable=False)
    service_date = db.Column(db.Date, nullable=False)
    notes        = db.Column(db.Text)
    recorded_by  = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at   = db.Column(db.DateTime, default=datetime.utcnow)
    def to_dict(self):
        return {
            'id': self.id, 'church_id': self.church_id,
            'member_id': self.member_id,
            'member_name': self.member.full_name if self.member else None,
            'member_code': self.member.member_id if self.member else None,
            'service_type': self.service_type,
            'service_date': self.service_date.isoformat() if self.service_date else None,
            'notes': self.notes,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class Finance(db.Model):
    __tablename__ = 'finance'
    id               = db.Column(db.Integer, primary_key=True)
    church_id        = db.Column(db.Integer, db.ForeignKey('churches.id'), nullable=True)
    reference        = db.Column(db.String(20), unique=True, nullable=False)
    transaction_type = db.Column(db.String(20), nullable=False)
    category         = db.Column(db.String(80))
    amount           = db.Column(db.Numeric(12, 2), nullable=False)
    currency         = db.Column(db.String(5), default='KES')
    description      = db.Column(db.Text)
    member_id        = db.Column(db.Integer, db.ForeignKey('members.id'), nullable=True)
    payment_method   = db.Column(db.String(30))
    mpesa_ref        = db.Column(db.String(30))
    transaction_date = db.Column(db.Date, nullable=False)
    recorded_by      = db.Column(db.Integer, db.ForeignKey('users.id'))
    verified         = db.Column(db.Boolean, default=False)
    verified_by      = db.Column(db.Integer)
    verified_at      = db.Column(db.DateTime)
    status           = db.Column(db.String(10), default='posted')
    voided_by        = db.Column(db.Integer)
    voided_at        = db.Column(db.DateTime)
    void_reason      = db.Column(db.Text)
    notes            = db.Column(db.Text)
    created_at       = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at       = db.Column(db.DateTime, default=datetime.utcnow,
                                  onupdate=datetime.utcnow)
    @staticmethod
    def generate_reference():
        d = datetime.now().strftime('%Y%m%d')
        s = ''.join(random.choices(string.ascii_uppercase+string.digits, k=4))
        return f'FIN-{d}-{s}'
    def to_dict(self):
        return {
            'id': self.id, 'church_id': self.church_id,
            'reference': self.reference,
            'transaction_type': self.transaction_type,
            'category': self.category,
            'amount': float(self.amount), 'currency': self.currency,
            'description': self.description, 'member_id': self.member_id,
            'member_name': self.member.full_name if self.member else None,
            'payment_method': self.payment_method, 'mpesa_ref': self.mpesa_ref,
            'transaction_date': self.transaction_date.isoformat() if self.transaction_date else None,
            'verified': bool(self.verified), 'notes': self.notes,
            'status': self.status or 'posted',
            'recorded_by': self.recorded_by, 'verified_by': self.verified_by,
            'void_reason': self.void_reason,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class Event(db.Model):
    __tablename__ = 'events'
    id                 = db.Column(db.Integer, primary_key=True)
    church_id          = db.Column(db.Integer, db.ForeignKey('churches.id'), nullable=True)
    title              = db.Column(db.String(200), nullable=False)
    description        = db.Column(db.Text)
    event_type         = db.Column(db.String(50))
    location           = db.Column(db.String(200))
    start_date         = db.Column(db.DateTime, nullable=False)
    end_date           = db.Column(db.DateTime)
    is_recurring       = db.Column(db.Boolean, default=False)
    recurrence_pattern = db.Column(db.String(50))
    max_attendees      = db.Column(db.Integer)
    status             = db.Column(db.String(20), default='upcoming')
    created_by         = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at         = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at         = db.Column(db.DateTime, default=datetime.utcnow,
                                    onupdate=datetime.utcnow)
    def to_dict(self):
        return {
            'id': self.id, 'church_id': self.church_id,
            'title': self.title, 'description': self.description,
            'event_type': self.event_type, 'location': self.location,
            'start_date': self.start_date.isoformat() if self.start_date else None,
            'end_date': self.end_date.isoformat() if self.end_date else None,
            'is_recurring': self.is_recurring,
            'recurrence_pattern': self.recurrence_pattern,
            'max_attendees': self.max_attendees, 'status': self.status,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }

class TokenBlocklist(db.Model):
    """Revoked JWTs. A token whose jti is listed here is rejected."""
    __tablename__ = 'token_blocklist'
    id         = db.Column(db.Integer, primary_key=True)
    jti        = db.Column(db.String(36), unique=True, nullable=False, index=True)
    token_type = db.Column(db.String(10), nullable=False)
    user_id    = db.Column(db.Integer, index=True)
    revoked_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    expires_at = db.Column(db.DateTime)


class AuditLog(db.Model):
    """Append-only record of who changed what. Rows are never edited or deleted."""
    __tablename__ = 'audit_log'
    id         = db.Column(db.Integer, primary_key=True)
    church_id  = db.Column(db.Integer, index=True)
    user_id    = db.Column(db.Integer, index=True)
    action     = db.Column(db.String(40), nullable=False)
    entity     = db.Column(db.String(40), nullable=False)
    entity_id  = db.Column(db.Integer, index=True)
    before     = db.Column('before_json', db.Text)
    after      = db.Column('after_json', db.Text)
    ip         = db.Column(db.String(64))
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def to_dict(self):
        import json
        return {
            'id': self.id, 'user_id': self.user_id, 'action': self.action,
            'entity': self.entity, 'entity_id': self.entity_id,
            'before': json.loads(self.before) if self.before else None,
            'after': json.loads(self.after) if self.after else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


from sqlalchemy import event as _sa_event  # noqa: E402


@_sa_event.listens_for(AuditLog, 'before_update')
@_sa_event.listens_for(AuditLog, 'before_delete')
def _audit_is_append_only(mapper, connection, target):
    raise RuntimeError('audit_log is append-only')


class PaymentRequest(db.Model):
    """A payment prompt a member was asked to confirm on their phone."""
    __tablename__ = 'payment_requests'
    id                  = db.Column(db.Integer, primary_key=True)
    church_id           = db.Column(db.Integer, db.ForeignKey('churches.id'), index=True, nullable=False)
    member_id           = db.Column(db.Integer, db.ForeignKey('members.id'))
    phone_masked        = db.Column(db.String(20))
    amount              = db.Column(db.Numeric(12, 2), nullable=False)
    transaction_type    = db.Column(db.String(20), default='tithe')
    status              = db.Column(db.String(12), default='pending', index=True)
    checkout_request_id = db.Column(db.String(80), unique=True, index=True)
    merchant_request_id = db.Column(db.String(80))
    mpesa_receipt       = db.Column(db.String(30))
    result_code         = db.Column(db.String(10))
    result_desc         = db.Column(db.String(255))
    finance_id          = db.Column(db.Integer)
    requested_by        = db.Column(db.Integer)
    created_at          = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    completed_at        = db.Column(db.DateTime)

    def to_dict(self):
        return {
            'id': self.id, 'member_id': self.member_id, 'phone': self.phone_masked,
            'amount': float(self.amount), 'transaction_type': self.transaction_type,
            'status': self.status, 'mpesa_receipt': self.mpesa_receipt,
            'result_desc': self.result_desc, 'finance_id': self.finance_id,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class PaymentEvent(db.Model):
    """A Paybill payment someone made without being asked (inbox item)."""
    __tablename__ = 'payment_events'
    id         = db.Column(db.Integer, primary_key=True)
    church_id  = db.Column(db.Integer, db.ForeignKey('churches.id'), index=True, nullable=False)
    trans_id   = db.Column(db.String(30), unique=True, nullable=False, index=True)
    amount     = db.Column(db.Numeric(12, 2), nullable=False)
    msisdn     = db.Column(db.String(64))
    payer_name = db.Column(db.String(120))
    bill_ref   = db.Column(db.String(60))
    trans_time = db.Column(db.String(20))
    status     = db.Column(db.String(12), default='unmatched', index=True)
    member_id  = db.Column(db.Integer)
    finance_id = db.Column(db.Integer)
    note       = db.Column(db.String(200))
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def to_dict(self):
        return {
            'id': self.id, 'trans_id': self.trans_id, 'amount': float(self.amount),
            'payer_name': self.payer_name, 'bill_ref': self.bill_ref,
            'trans_time': self.trans_time, 'status': self.status,
            'member_id': self.member_id, 'finance_id': self.finance_id, 'note': self.note,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class PaymentAccount(db.Model):
    """Where a church receives money: its own Paybill, Till, bank paybill or bank account."""
    __tablename__ = 'payment_accounts'
    id           = db.Column(db.Integer, primary_key=True)
    church_id    = db.Column(db.Integer, db.ForeignKey('churches.id'), index=True, nullable=False)
    kind         = db.Column(db.String(20), nullable=False)
    label        = db.Column(db.String(120), nullable=False)
    business_no  = db.Column(db.String(12))
    account_no   = db.Column(db.String(40))
    bank_name    = db.Column(db.String(80))
    instructions = db.Column(db.String(500))
    is_active    = db.Column(db.Boolean, default=True)
    created_at   = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def to_dict(self):
        return {
            'id': self.id, 'kind': self.kind, 'label': self.label,
            'business_no': self.business_no, 'account_no': self.account_no,
            'bank_name': self.bank_name, 'instructions': self.instructions,
        }


class Invoice(db.Model):
    """A subscription invoice the platform owner issues and confirms."""
    __tablename__ = 'invoices'
    id           = db.Column(db.Integer, primary_key=True)
    church_id    = db.Column(db.Integer, db.ForeignKey('churches.id'), index=True, nullable=False)
    plan         = db.Column(db.String(20), nullable=False)
    months       = db.Column(db.Integer, nullable=False, default=1)
    amount       = db.Column(db.Numeric(12, 2), nullable=False)
    status       = db.Column(db.String(10), default='due', index=True)
    method       = db.Column(db.String(10))
    reference    = db.Column(db.String(40))
    period_start = db.Column(db.DateTime)
    period_end   = db.Column(db.DateTime)
    created_by   = db.Column(db.Integer)
    paid_by      = db.Column(db.Integer)
    paid_at      = db.Column(db.DateTime)
    claim_method    = db.Column(db.String(10))
    claim_reference = db.Column(db.String(40))
    claimed_at      = db.Column(db.DateTime)
    created_at   = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def to_dict(self):
        def iso(v):
            return v.isoformat() if v else None
        return {
            'id': self.id, 'church_id': self.church_id, 'plan': self.plan, 'months': self.months,
            'amount': float(self.amount), 'status': self.status, 'method': self.method,
            'reference': self.reference, 'period_start': iso(self.period_start),
            'period_end': iso(self.period_end), 'paid_at': iso(self.paid_at), 'created_at': iso(self.created_at),
            'claim_method': self.claim_method, 'claim_reference': self.claim_reference,
            'claimed_at': iso(self.claimed_at),
        }


class PlatformSetting(db.Model):
    """The platform owner's own settings, such as where churches pay ChurchOS. Never church data."""
    __tablename__ = 'platform_settings'
    id         = db.Column(db.Integer, primary_key=True)
    key        = db.Column(db.String(60), unique=True, nullable=False)
    value      = db.Column(db.String(500))
    updated_by = db.Column(db.Integer)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow)


class SmsMessage(db.Model):
    """One text message to one member, and what happened to it."""
    __tablename__ = 'sms_messages'
    id          = db.Column(db.Integer, primary_key=True)
    church_id   = db.Column(db.Integer, db.ForeignKey('churches.id'), index=True, nullable=False)
    member_id   = db.Column(db.Integer, db.ForeignKey('members.id'), index=True)
    batch_id    = db.Column(db.String(36), index=True)
    phone       = db.Column(db.String(16))
    body        = db.Column(db.String(480))
    status      = db.Column(db.String(12), default='sent', index=True)
    provider_id = db.Column(db.String(60), index=True)
    detail      = db.Column(db.String(120))
    segments    = db.Column(db.Integer, default=1)
    cost        = db.Column(db.String(20))
    created_by  = db.Column(db.Integer)
    created_at  = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    updated_at  = db.Column(db.DateTime)

    def to_dict(self):
        return {
            'id': self.id, 'member_id': self.member_id, 'phone': self.phone, 'body': self.body or '',
            'status': self.status, 'detail': self.detail, 'segments': self.segments, 'cost': self.cost,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class SmsOptOut(db.Model):
    """A phone number that replied STOP. It is never messaged until staff record new consent for it."""
    __tablename__ = 'sms_optouts'
    id         = db.Column(db.Integer, primary_key=True)
    phone      = db.Column(db.String(16), unique=True, nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class ChurchRequest(db.Model):
    """A church asking for ChurchOS. It waits here until the platform owner approves or declines it."""
    __tablename__ = 'church_requests'
    id                = db.Column(db.Integer, primary_key=True)
    church_name       = db.Column(db.String(120), nullable=False)
    contact_name      = db.Column(db.String(80), nullable=False)
    phone             = db.Column(db.String(16), nullable=False, index=True)
    email             = db.Column(db.String(120))
    county            = db.Column(db.String(80))
    denomination_text = db.Column(db.String(160))
    members_estimate  = db.Column(db.Integer)
    note              = db.Column(db.String(500))
    status            = db.Column(db.String(10), default='pending', index=True)
    church_id         = db.Column(db.Integer)
    decided_by        = db.Column(db.Integer)
    decided_at        = db.Column(db.DateTime)
    decision_note     = db.Column(db.String(300))
    accepted_terms_at = db.Column(db.DateTime)
    terms_version     = db.Column(db.String(10))
    created_at        = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id, 'church_name': self.church_name, 'contact_name': self.contact_name,
            'phone': self.phone, 'email': self.email, 'county': self.county,
            'denomination': self.denomination_text, 'members_estimate': self.members_estimate,
            'note': self.note, 'status': self.status, 'church_id': self.church_id,
            'decision_note': self.decision_note,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'decided_at': self.decided_at.isoformat() if self.decided_at else None,
        }


class Denomination(db.Model):
    """A denomination or ministry, with the words its churches use."""
    __tablename__ = 'denominations'
    id                     = db.Column(db.Integer, primary_key=True)
    name                   = db.Column(db.String(160), unique=True, nullable=False)
    short_name             = db.Column(db.String(20))
    status                 = db.Column(db.String(10), default='listed', index=True)
    region_label           = db.Column(db.String(40), default='Region')
    unit_label             = db.Column(db.String(40), default='Church')
    region_leader_title    = db.Column(db.String(40), default='Regional leader')
    unit_leader_title      = db.Column(db.String(40), default='Pastor')
    seat_label             = db.Column(db.String(40), default='Headquarters church')
    requested_by_church_id = db.Column(db.Integer, index=True)
    created_at             = db.Column(db.DateTime, default=datetime.utcnow)

    def labels(self):
        return {'region_label': self.region_label, 'unit_label': self.unit_label,
                'region_leader_title': self.region_leader_title, 'unit_leader_title': self.unit_leader_title,
                'seat_label': self.seat_label}

    def to_dict(self):
        return dict({'id': self.id, 'name': self.name, 'short_name': self.short_name, 'status': self.status},
                    **self.labels())


class Region(db.Model):
    """A group of churches (altars) under one leader, seated at one of them."""
    __tablename__ = 'regions'
    id              = db.Column(db.Integer, primary_key=True)
    name            = db.Column(db.String(120), nullable=False)
    denomination_id = db.Column(db.Integer, db.ForeignKey('denominations.id'))
    seat_church_id  = db.Column(db.Integer, db.ForeignKey('churches.id'), unique=True, nullable=False)
    leader_user_id  = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at      = db.Column(db.DateTime, default=datetime.utcnow)


class RegionInvite(db.Model):
    """An invitation from a region to a church. Nothing is shared until the church accepts."""
    __tablename__ = 'region_invites'
    id           = db.Column(db.Integer, primary_key=True)
    region_id    = db.Column(db.Integer, db.ForeignKey('regions.id'), index=True, nullable=False)
    church_id    = db.Column(db.Integer, db.ForeignKey('churches.id'), index=True, nullable=False)
    status       = db.Column(db.String(10), default='pending', index=True)
    invited_by   = db.Column(db.Integer)
    responded_by = db.Column(db.Integer)
    created_at   = db.Column(db.DateTime, default=datetime.utcnow)
    responded_at = db.Column(db.DateTime)

    def to_dict(self):
        return {'id': self.id, 'region_id': self.region_id, 'church_id': self.church_id, 'status': self.status,
                'created_at': self.created_at.isoformat() if self.created_at else None}
