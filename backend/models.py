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
            'verified': self.verified, 'notes': self.notes,
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
