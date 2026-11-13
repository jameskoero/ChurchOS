import logging
import os
from datetime import datetime, timedelta

from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_jwt_extended import JWTManager
from flask_migrate import Migrate
from sqlalchemy.exc import IntegrityError

from config import config
from extensions import limiter
from models import (db, bcrypt, User, Church, TokenBlocklist,
                    Member, Attendance, Finance, Event)
from schema_sync import sync_schema

migrate = Migrate()
jwt = JWTManager()
log = logging.getLogger('churchos')

DEFAULT_ORIGIN = 'https://churchos-app.vercel.app'
MIN_BOOTSTRAP_PASSWORD = 12


def allowed_origins(app):
    """The production frontend plus anything listed in FRONTEND_URL."""
    raw = str(app.config.get('FRONTEND_URL') or '')
    origins = [o.strip().rstrip('/') for o in raw.split(',') if o.strip()]
    if DEFAULT_ORIGIN not in origins:
        origins.append(DEFAULT_ORIGIN)
    return origins


def create_app(config_name=None, overrides=None):
    if config_name is None:
        config_name = os.environ.get('FLASK_ENV', 'production')
    app = Flask(__name__)
    app.config.from_object(config.get(config_name, config['default']))
    app.config.setdefault('RATELIMIT_ENABLED', True)
    app.config.setdefault('RATELIMIT_HEADERS_ENABLED', True)
    if overrides:
        app.config.update(overrides)

    db.init_app(app)
    bcrypt.init_app(app)
    migrate.init_app(app, db)
    jwt.init_app(app)
    limiter.init_app(app)

    # CORS: named origins only. Never "*".
    CORS(app, resources={
        r"/api/.*": {
            "origins": allowed_origins(app),
            "methods": ["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
            "allow_headers": ["Content-Type", "Authorization"],
        }
    })

    from routes.auth       import auth_bp
    from routes.members    import members_bp
    from routes.attendance import attendance_bp
    from routes.finance    import finance_bp
    from routes.events     import events_bp
    from routes.users      import users_bp
    from routes.dashboard  import dashboard_bp
    from routes.churches   import churches_bp
    from routes.payments   import payments_bp
    from routes.insights   import insights_bp
    from routes.accounts   import accounts_bp
    from routes.reports    import reports_bp
    from routes.billing    import billing_bp, install_guard
    from routes.checkin    import checkin_bp
    from routes.sms        import sms_bp
    from routes.governance import governance_bp
    app.register_blueprint(auth_bp,       url_prefix='/api/auth')
    app.register_blueprint(members_bp,    url_prefix='/api/members')
    app.register_blueprint(attendance_bp, url_prefix='/api/attendance')
    app.register_blueprint(finance_bp,    url_prefix='/api/finance')
    app.register_blueprint(events_bp,     url_prefix='/api/events')
    app.register_blueprint(users_bp,      url_prefix='/api/users')
    app.register_blueprint(dashboard_bp,  url_prefix='/api/dashboard')
    app.register_blueprint(churches_bp,   url_prefix='/api/churches')
    app.register_blueprint(payments_bp,   url_prefix='/api/payments')
    app.register_blueprint(insights_bp,   url_prefix='/api/insights')
    app.register_blueprint(accounts_bp,   url_prefix='/api/accounts')
    app.register_blueprint(reports_bp,    url_prefix='/api/reports')
    app.register_blueprint(billing_bp,    url_prefix='/api/billing')
    app.register_blueprint(checkin_bp,    url_prefix='/api/checkin')
    app.register_blueprint(sms_bp,        url_prefix='/api/sms')
    app.register_blueprint(governance_bp, url_prefix='/api/governance')
    install_guard(app)

    # ── JWT: every token is checked against the blocklist and the user ──────
    @jwt.token_in_blocklist_loader
    def is_revoked(jwt_header, jwt_payload):
        jti = jwt_payload.get('jti')
        if db.session.query(TokenBlocklist.id).filter_by(jti=jti).first() is not None:
            return True
        try:
            user = db.session.get(User, int(jwt_payload.get('sub')))
        except (TypeError, ValueError):
            return True
        if user is None or not user.is_active:
            return True
        return int(jwt_payload.get('tv', 0) or 0) != int(user.token_version or 0)

    @jwt.revoked_token_loader
    def revoked(h, p):
        return jsonify({'error': 'Session ended. Sign in again.', 'code': 'TOKEN_REVOKED'}), 401

    @jwt.expired_token_loader
    def expired(h, p):
        return jsonify({'error': 'Token expired', 'code': 'TOKEN_EXPIRED'}), 401

    @jwt.invalid_token_loader
    def invalid(e):
        return jsonify({'error': 'Invalid token', 'code': 'INVALID_TOKEN'}), 401

    @jwt.unauthorized_loader
    def missing(e):
        return jsonify({'error': 'Token required', 'code': 'TOKEN_MISSING'}), 401

    # ── Errors as JSON, never stack traces ───────────────────────────────────
    @app.errorhandler(403)
    def forbidden(e):
        return jsonify({'error': 'Not allowed', 'code': 'FORBIDDEN'}), 403

    @app.errorhandler(404)
    def not_found(e):
        return jsonify({'error': 'Not found', 'code': 'NOT_FOUND'}), 404

    @app.errorhandler(405)
    def not_allowed(e):
        return jsonify({'error': 'Method not allowed', 'code': 'METHOD_NOT_ALLOWED'}), 405

    @app.errorhandler(429)
    def too_many(e):
        return jsonify({'error': 'Too many requests. Wait a minute and try again.',
                        'code': 'RATE_LIMITED'}), 429

    @app.errorhandler(500)
    def server_error(e):
        db.session.rollback()
        return jsonify({'error': 'Server error', 'code': 'SERVER_ERROR'}), 500

    @app.after_request
    def security_headers(resp):
        resp.headers.setdefault('X-Content-Type-Options', 'nosniff')
        resp.headers.setdefault('X-Frame-Options', 'DENY')
        resp.headers.setdefault('Referrer-Policy', 'no-referrer')
        resp.headers.setdefault('Content-Security-Policy',
                                "default-src 'none'; frame-ancestors 'none'")
        resp.headers.setdefault('Strict-Transport-Security',
                                'max-age=31536000; includeSubDomains')
        if request.path.startswith('/api/'):
            resp.headers.setdefault('Cache-Control', 'no-store')
        return resp

    @app.route('/api/health')
    def health():
        return jsonify({'status': 'ok', 'app': 'ChurchOS', 'version': '3.0.0'}), 200

    with app.app_context():
        _init_db()
        _bootstrap()
        _tenancy_upgrade()
    return app


def _init_db():
    """Create missing tables, then add missing columns. Safe on every start."""
    try:
        db.create_all()
    except Exception:
        # Two workers can race on the first start after a deploy.
        db.session.rollback()
        db.create_all()
    added = sync_schema(db)
    if added:
        log.warning('[schema] added columns: %s', ', '.join(added))
    from routes.governance import seed_denominations
    seed_denominations(db)


def _bootstrap():
    """Create the first church and admin ONLY when no admin exists.

    The password comes from ADMIN_BOOTSTRAP_PASSWORD. It is never written
    in code, never logged, and an existing password is never changed here.
    """
    if User.query.filter_by(role='admin').first() is not None:
        return 'exists'
    password = os.environ.get('ADMIN_BOOTSTRAP_PASSWORD', '')
    if len(password) < MIN_BOOTSTRAP_PASSWORD:
        log.warning('[bootstrap] no admin user exists and ADMIN_BOOTSTRAP_PASSWORD '
                    'is unset or shorter than %d characters; admin not created',
                    MIN_BOOTSTRAP_PASSWORD)
        return 'skipped'
    church = Church.query.order_by(Church.id).first()
    if church is None:
        church = Church(
            name=os.environ.get('BOOTSTRAP_CHURCH_NAME', 'My Church'),
            member_prefix='CHR',
            subscription_plan='trial',
            trial_ends_at=datetime.utcnow() + timedelta(days=30),
            is_active=True,
        )
        db.session.add(church)
        db.session.flush()
    admin = User(
        username=os.environ.get('ADMIN_BOOTSTRAP_USERNAME', 'admin'),
        email=os.environ.get('ADMIN_BOOTSTRAP_EMAIL', 'admin@churchos.app'),
        full_name='System Administrator',
        role='admin',
        church_id=church.id,
        is_active=True,
    )
    admin.set_password(password)
    db.session.add(admin)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return 'race'
    log.warning('[bootstrap] admin user created')
    return 'created'


def _tenancy_upgrade():
    """Name a platform owner and give every church-less row a church.

    Before church separation, rows were saved with no church at all. They
    belonged to the one church in use, so they go to the first admin's church.
    Safe to run on every start: it only touches rows whose church is empty.
    """
    first_admin = User.query.filter_by(role='admin').order_by(User.id).first()
    if first_admin is None:
        return
    if User.query.filter_by(is_platform_owner=True).first() is None:
        wanted = os.environ.get('PLATFORM_OWNER_EMAIL', '').strip().lower()
        owner = User.query.filter_by(email=wanted).first() if wanted else None
        (owner or first_admin).is_platform_owner = True
        log.warning('[tenancy] platform owner set')
    home = first_admin.church_id
    if home is None:
        church = Church.query.order_by(Church.id).first()
        home = church.id if church else None
    if home is not None:
        for model in (User, Member, Attendance, Finance, Event):
            moved = model.query.filter(model.church_id.is_(None)).update(
                {'church_id': home}, synchronize_session=False)
            if moved:
                log.warning('[tenancy] %s: %d rows given church %s',
                            model.__tablename__, moved, home)
    db.session.commit()
