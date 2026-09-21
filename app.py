import os
import uuid
from collections import defaultdict, deque
from datetime import date, datetime, timedelta, timezone
from functools import wraps
from pathlib import Path
from zoneinfo import ZoneInfo

from flask import Flask, abort, flash, jsonify, redirect, render_template, request, send_from_directory, session, url_for
from flask_migrate import Migrate, upgrade
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import CSRFProtect
from sqlalchemy import event, func, inspect, text
from sqlalchemy.exc import SQLAlchemyError
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

KST = ZoneInfo("Asia/Seoul")
UTC = timezone.utc
ALLOWED_EXTENSIONS = {"pdf", "doc", "docx", "xls", "xlsx", "ppt", "pptx", "hwp", "hwpx", "jpg", "jpeg", "png"}
MAX_UPLOAD_BYTES = 20 * 1024 * 1024

db = SQLAlchemy()
migrate = Migrate()
csrf = CSRFProtect()
login_attempts = defaultdict(deque)
VALID_ROLES = {"admin", "editor", "viewer"}
VALID_DOCUMENT_STATUSES = {"draft", "active", "confirmed", "obsolete"}
VALID_COMPLAINT_STATUSES = {"received", "investigating", "action", "completed", "overdue"}
VALID_LABELING_STATUSES = {"preparing", "review", "current", "obsolete"}
LABELING_STATUS_LABELS = {"preparing": "시안 준비 중", "review": "검토 중", "current": "최신본", "obsolete": "이전본"}
LABELING_TYPES = [("vial", "바이알"), ("blister", "블리스터 포장 완제품"), ("ifu", "IFU"), ("quick_guide", "퀵가이드"), ("product_box", "제품박스")]
LABELING_ICONS = {"vial": "▥", "blister": "▦", "ifu": "IFU", "quick_guide": "QG", "product_box": "□"}
COMPLAINT_STATUS_LABELS = {
    "received": "접수", "investigating": "조사 중", "action": "조치 중",
    "completed": "처리 완료", "overdue": "기한 초과",
}
KOREA_PROVINCES = ["서울", "부산", "대구", "인천", "광주", "대전", "울산", "세종", "경기", "강원", "충북", "충남", "전북", "전남", "경북", "경남", "제주"]
WORK_SECTIONS = {
    "GMP": [("records", "문서 및 기록관리"), ("external", "외부출처문서"), ("purchasing", "구매관리"), ("monitoring", "모니터링 및 측정"), ("analysis", "데이터 분석"), ("validation", "유효성 관리"), ("complaints", "고객불만"), ("labeling", "라벨링·패키지 이력관리")],
    "GTP": [("records", "문서 및 기록관리"), ("monitoring", "모니터링 및 측정"), ("validation", "유효성 관리"), ("complaints", "고객불만"), ("labeling", "라벨링·패키지 이력관리")],
}


def utcnow():
    return datetime.now(UTC)


def database_uri():
    keys = ["DB_HOST", "DB_PORT", "DB_NAME", "DB_USER", "DB_PASSWORD"]
    missing = [key for key in keys if not os.getenv(key)]
    if missing:
        raise RuntimeError("PostgreSQL 환경변수가 준비되지 않았습니다: " + ", ".join(missing))
    from urllib.parse import quote_plus
    return (
        f"postgresql+psycopg://{quote_plus(os.environ['DB_USER'])}:"
        f"{quote_plus(os.environ['DB_PASSWORD'])}@{os.environ['DB_HOST']}:"
        f"{os.environ['DB_PORT']}/{os.environ['DB_NAME']}"
    )


def create_app(test_config=None):
    app = Flask(__name__)
    app.config.update(
        SECRET_KEY=os.getenv("SECRET_KEY") or ("test-secret" if test_config else None),
        SQLALCHEMY_DATABASE_URI=database_uri() if not test_config else test_config["SQLALCHEMY_DATABASE_URI"],
        SQLALCHEMY_ENGINE_OPTIONS={"pool_pre_ping": True, "pool_recycle": 300, "pool_size": 5, "max_overflow": 5},
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        PERMANENT_SESSION_LIFETIME=timedelta(minutes=60),
        SESSION_COOKIE_HTTPONLY=True,
        # AI SPACE is HTTPS-only in production. Tests explicitly disable this.
        SESSION_COOKIE_SECURE=True,
        SESSION_COOKIE_SAMESITE="Lax",
        MAX_CONTENT_LENGTH=MAX_UPLOAD_BYTES,
        WTF_CSRF_TIME_LIMIT=3600,
        UPLOAD_FOLDER=os.getenv("UPLOAD_FOLDER", "/app/user_data"),
    )
    if test_config:
        app.config.update(test_config)
    if not app.config["SECRET_KEY"]:
        raise RuntimeError("SECRET_KEY 환경변수가 필요합니다.")

    db.init_app(app)
    migrate.init_app(app, db)
    csrf.init_app(app)

    @event.listens_for(db.session, "after_rollback")
    def _after_rollback(session):
        session.expire_all()

    register_routes(app)
    register_errors(app)
    register_context(app)

    with app.app_context():
        Path(app.config["UPLOAD_FOLDER"]).mkdir(parents=True, exist_ok=True)
        if not app.config.get("TESTING"):
            run_migrations_once()
            bootstrap_admin()
    return app


def run_migrations_once():
    lock_id = 93827164
    with db.engine.connect() as lock_connection:
        try:
            lock_connection.execute(text("SELECT pg_advisory_lock(:lock_id)"), {"lock_id": lock_id})
            upgrade(directory="migrations")
        finally:
            lock_connection.execute(text("SELECT pg_advisory_unlock(:lock_id)"), {"lock_id": lock_id})
            lock_connection.commit()


class TimestampMixin:
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)


class User(TimestampMixin, db.Model):
    id = db.Column(db.Uuid, primary_key=True, default=uuid.uuid4)
    login_id = db.Column(db.String(80), nullable=False, unique=True, index=True)
    name = db.Column(db.String(100), nullable=False)
    department = db.Column(db.String(100), nullable=False, default="")
    position = db.Column(db.String(100), nullable=False, default="")
    role = db.Column(db.String(20), nullable=False, default="viewer")
    password_hash = db.Column(db.String(255), nullable=False)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    must_change_password = db.Column(db.Boolean, nullable=False, default=True)
    last_login_at = db.Column(db.DateTime(timezone=True))
    __table_args__ = (db.Index("uq_user_login_id_lower", func.lower(login_id), unique=True),)

    @staticmethod
    def normalize_login_id(value):
        return value.strip().casefold()

    def set_password(self, value):
        self.password_hash = generate_password_hash(value)

    def check_password(self, value):
        return check_password_hash(self.password_hash, value)


class Document(TimestampMixin, db.Model):
    id = db.Column(db.Uuid, primary_key=True, default=uuid.uuid4)
    category = db.Column(db.String(10), nullable=False, index=True)
    section = db.Column(db.String(50), nullable=False, default="records", index=True)
    document_no = db.Column(db.String(100), nullable=False)
    title = db.Column(db.String(250), nullable=False)
    revision = db.Column(db.String(50), nullable=False, default="0")
    effective_date = db.Column(db.Date)
    status = db.Column(db.String(20), nullable=False, default="draft")
    description = db.Column(db.Text, nullable=False, default="")
    file_name = db.Column(db.String(255))
    stored_name = db.Column(db.String(255))
    created_by = db.Column(db.Uuid, db.ForeignKey("user.id"), nullable=False)
    updated_by = db.Column(db.Uuid, db.ForeignKey("user.id"), nullable=False)
    confirmed_at = db.Column(db.DateTime(timezone=True))
    __table_args__ = (db.UniqueConstraint("category", "section", "document_no", "revision", name="uq_document_revision"),)


class Complaint(TimestampMixin, db.Model):
    id = db.Column(db.Uuid, primary_key=True, default=uuid.uuid4)
    complaint_no = db.Column(db.String(40), nullable=False, unique=True)
    standard = db.Column(db.String(10), nullable=False, default="GMP")
    market = db.Column(db.String(20), nullable=False, index=True)
    country = db.Column(db.String(100), nullable=False)
    province = db.Column(db.String(50), index=True)
    receipt_date = db.Column(db.Date, nullable=False, index=True)
    customer_name = db.Column(db.String(200), nullable=False)
    product_name = db.Column(db.String(200), nullable=False)
    model_name = db.Column(db.String(100), nullable=False)
    lot_no = db.Column(db.String(100), nullable=False)
    volume = db.Column(db.String(50), nullable=False, default="")
    shipment_qty = db.Column(db.Integer, nullable=False, default=0)
    shipment_type = db.Column(db.String(100), nullable=False, default="")
    complaint_qty = db.Column(db.Integer, nullable=False, default=0)
    complaint_type = db.Column(db.String(150), nullable=False)
    original_summary = db.Column(db.String(250), nullable=False, default="")
    complaint_detail = db.Column(db.Text, nullable=False)
    investigation = db.Column(db.Text, nullable=False, default="")
    investigation_result = db.Column(db.Text, nullable=False, default="")
    action_detail = db.Column(db.Text, nullable=False, default="")
    capa_required = db.Column(db.Boolean, nullable=False, default=False)
    handling_type = db.Column(db.String(100), nullable=False, default="")
    handled_date = db.Column(db.Date)
    status = db.Column(db.String(30), nullable=False, default="received", index=True)
    closure_reason = db.Column(db.Text, nullable=False, default="")
    owner = db.Column(db.String(100), nullable=False, default="")
    created_by = db.Column(db.Uuid, db.ForeignKey("user.id"))
    updated_by = db.Column(db.Uuid, db.ForeignKey("user.id"))


class LabelingAsset(TimestampMixin, db.Model):
    id = db.Column(db.Uuid, primary_key=True, default=uuid.uuid4)
    standard = db.Column(db.String(10), nullable=False, default="GMP")
    item_type = db.Column(db.String(40), nullable=False, index=True)
    item_name = db.Column(db.String(100), nullable=False)
    product_name = db.Column(db.String(200), nullable=False, default="")
    control_no = db.Column(db.String(100), nullable=False, default="")
    revision = db.Column(db.String(50), nullable=False, default="-")
    effective_date = db.Column(db.Date)
    status = db.Column(db.String(30), nullable=False, default="preparing", index=True)
    description = db.Column(db.Text, nullable=False, default="")
    file_name = db.Column(db.String(255))
    stored_name = db.Column(db.String(255))
    created_by = db.Column(db.Uuid, db.ForeignKey("user.id"))
    updated_by = db.Column(db.Uuid, db.ForeignKey("user.id"))


class AuditLog(db.Model):
    id = db.Column(db.Uuid, primary_key=True, default=uuid.uuid4)
    actor_id = db.Column(db.Uuid, db.ForeignKey("user.id"))
    actor_login_id = db.Column(db.String(80), nullable=False, default="anonymous")
    action = db.Column(db.String(80), nullable=False)
    target_type = db.Column(db.String(50), nullable=False, default="system")
    target_id = db.Column(db.String(100))
    detail = db.Column(db.String(500), nullable=False, default="")
    ip_address = db.Column(db.String(64))
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow, index=True)


class SystemSetting(TimestampMixin, db.Model):
    id = db.Column(db.Uuid, primary_key=True, default=uuid.uuid4)
    key = db.Column(db.String(100), nullable=False, unique=True)
    value = db.Column(db.String(500), nullable=False, default="")
    updated_by = db.Column(db.Uuid, db.ForeignKey("user.id"), nullable=False)


def audit(action, target_type="system", target_id=None, detail="", actor=None):
    actor = actor or current_user()
    db.session.add(AuditLog(
        actor_id=actor.id if actor else None,
        actor_login_id=actor.login_id if actor else request.form.get("login_id", "anonymous")[:80],
        action=action, target_type=target_type, target_id=str(target_id) if target_id else None,
        detail=detail[:500], ip_address=(request.headers.get("X-Forwarded-For", request.remote_addr) or "")[:64],
    ))


def bootstrap_admin():
    try:
        if not inspect(db.engine).has_table("user"):
            return
        if db.session.scalar(db.select(func.count(User.id))) != 0:
            return
        admin_id = os.getenv("BOOTSTRAP_ADMIN_ID")
        password = os.getenv("BOOTSTRAP_ADMIN_PASSWORD")
        name = os.getenv("BOOTSTRAP_ADMIN_NAME", "시스템관리자")
        if not admin_id or not password:
            return
        user = User(login_id=User.normalize_login_id(admin_id), name=name, role="admin", is_active=True, must_change_password=True)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        raise


def current_user():
    uid = session.get("user_id")
    return db.session.get(User, uuid.UUID(uid)) if uid else None


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        user = current_user()
        if not user or not user.is_active:
            session.clear()
            if request.path.startswith("/api/"):
                return jsonify(error="인증이 필요합니다."), 401
            return redirect(url_for("login", next=request.path))
        if user.must_change_password and request.endpoint not in {"change_password", "logout", "static"}:
            return redirect(url_for("change_password"))
        return view(*args, **kwargs)
    return wrapped


def roles_required(*roles):
    def decorator(view):
        @wraps(view)
        @login_required
        def wrapped(*args, **kwargs):
            if current_user().role not in roles:
                abort(403)
            return view(*args, **kwargs)
        return wrapped
    return decorator


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def safe_next(value):
    return value if value and value.startswith("/") and not value.startswith("//") else url_for("dashboard")


def register_routes(app):
    @app.before_request
    def session_policy():
        session.permanent = True

    @app.get("/health")
    @csrf.exempt
    def health():
        result = {"status": "error", "database": False, "database_backend": "postgresql", "database_writable": False, "application_ready": False}
        try:
            db.session.execute(text("SELECT 1"))
            result["database"] = True
            nested = db.session.begin_nested()
            db.session.execute(text("CREATE TEMP TABLE IF NOT EXISTS health_probe (id integer) ON COMMIT DROP"))
            db.session.execute(text("INSERT INTO health_probe (id) VALUES (1)"))
            nested.rollback()
            result.update(status="ok", database_writable=True, application_ready=True)
            return jsonify(result), 200
        except SQLAlchemyError:
            db.session.rollback()
            return jsonify(result), 503

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if current_user():
            return redirect(url_for("dashboard"))
        if request.method == "POST":
            login_id = User.normalize_login_id(request.form.get("login_id", ""))
            now = utcnow()
            attempts = login_attempts[login_id]
            while attempts and now - attempts[0] > timedelta(minutes=15):
                attempts.popleft()
            if len(attempts) >= 5:
                flash("로그인 시도가 제한되었습니다. 15분 후 다시 시도하세요.", "error")
                return render_template("login.html"), 429
            user = db.session.scalar(db.select(User).where(func.lower(User.login_id) == login_id))
            if not user or not user.is_active or not user.check_password(request.form.get("password", "")):
                attempts.append(now)
                audit("login_failed", detail="로그인 실패")
                db.session.commit()
                flash("아이디 또는 비밀번호를 확인하세요.", "error")
                return render_template("login.html"), 401
            attempts.clear()
            session.clear()
            session["user_id"] = str(user.id)
            user.last_login_at = now
            audit("login_success", "user", user.id, actor=user)
            db.session.commit()
            return redirect(url_for("change_password") if user.must_change_password else safe_next(request.args.get("next")))
        return render_template("login.html")

    @app.post("/logout")
    @login_required
    def logout():
        audit("logout", "user", current_user().id)
        db.session.commit()
        session.clear()
        response = redirect(url_for("login"))
        response.delete_cookie(app.config.get("SESSION_COOKIE_NAME", "session"))
        return response

    @app.get("/")
    @login_required
    def dashboard():
        counts = {category: db.session.scalar(db.select(func.count(Document.id)).where(Document.category == category)) for category in ("GMP", "GTP")}
        recent = db.session.scalars(db.select(Document).order_by(Document.updated_at.desc()).limit(8)).all()
        return render_template("dashboard.html", counts=counts, recent=recent)

    @app.get("/work/<standard>")
    @login_required
    def work_index(standard):
        standard = standard.upper()
        if standard not in WORK_SECTIONS:
            abort(404)
        section_counts = {slug: db.session.scalar(db.select(func.count(Document.id)).where(Document.category == standard, Document.section == slug)) for slug, _ in WORK_SECTIONS[standard]}
        if standard == "GMP":
            section_counts["complaints"] = db.session.scalar(db.select(func.count(Complaint.id)).where(Complaint.standard == "GMP"))
            section_counts["labeling"] = db.session.scalar(db.select(func.count(LabelingAsset.id)).where(LabelingAsset.standard == "GMP", LabelingAsset.status == "current"))
        return render_template("work_index.html", standard=standard, sections=WORK_SECTIONS[standard], section_counts=section_counts)

    @app.get("/api/session")
    @login_required
    def api_session():
        user = current_user()
        return jsonify(user={"id": str(user.id), "login_id": user.login_id, "name": user.name, "role": user.role})

    @app.route("/complaints/GMP", methods=["GET", "POST"])
    @login_required
    def complaints_dashboard():
        user = current_user()
        if request.method == "POST":
            if user.role not in {"admin", "editor"}:
                abort(403)
            market = request.form.get("market", "domestic")
            status_value = request.form.get("status", "received")
            province = request.form.get("province", "").strip() or None
            if market not in {"domestic", "overseas"} or status_value not in VALID_COMPLAINT_STATUSES:
                abort(400)
            if market == "domestic" and province not in KOREA_PROVINCES:
                flash("국내 고객불만은 시·도를 선택하세요.", "error")
                return redirect(url_for("complaints_dashboard", market=market))
            year = date.fromisoformat(request.form["receipt_date"]).year
            prefix = f"GMP-C-{year}-"
            used = db.session.scalars(db.select(Complaint.complaint_no).where(Complaint.complaint_no.like(f"{prefix}%"))).all()
            sequence = max([int(v.rsplit("-", 1)[-1]) for v in used if v.rsplit("-", 1)[-1].isdigit()] or [0]) + 1
            complaint = Complaint(
                complaint_no=f"{prefix}{sequence:03d}", standard="GMP", market=market,
                country=request.form.get("country", "한국").strip(), province=province,
                receipt_date=date.fromisoformat(request.form["receipt_date"]),
                customer_name=request.form["customer_name"].strip(), product_name=request.form["product_name"].strip(),
                model_name=request.form["model_name"].strip(), lot_no=request.form["lot_no"].strip(),
                volume=request.form.get("volume", "").strip(), shipment_qty=max(0, int(request.form.get("shipment_qty") or 0)),
                shipment_type=request.form.get("shipment_type", "").strip(), complaint_qty=max(0, int(request.form.get("complaint_qty") or 0)),
                complaint_type=request.form["complaint_type"].strip(), complaint_detail=request.form["complaint_detail"].strip(),
                investigation=request.form.get("investigation", "").strip(), investigation_result=request.form.get("investigation_result", "").strip(),
                action_detail=request.form.get("action_detail", "").strip(), status=status_value,
                owner=request.form.get("owner", "").strip(), created_by=user.id, updated_by=user.id,
            )
            db.session.add(complaint)
            audit("complaint_created", "complaint", complaint.id, complaint.complaint_no)
            db.session.commit()
            flash("고객불만이 등록되었습니다.", "success")
            return redirect(url_for("complaint_detail", complaint_id=complaint.id))

        market = request.args.get("market", "domestic")
        if market not in {"domestic", "overseas"}:
            market = "domestic"
        selected_province = request.args.get("province", "").strip()
        if selected_province and selected_province not in KOREA_PROVINCES:
            selected_province = ""
        status_value = request.args.get("status", "").strip()
        keyword = request.args.get("q", "").strip()
        query = db.select(Complaint).where(Complaint.standard == "GMP", Complaint.market == market)
        all_market_rows = db.session.scalars(query).all()
        province_counts = {p: sum(1 for row in all_market_rows if row.province == p) for p in KOREA_PROVINCES}
        if selected_province:
            query = query.where(Complaint.province == selected_province)
        if status_value in VALID_COMPLAINT_STATUSES:
            query = query.where(Complaint.status == status_value)
        if keyword:
            like = f"%{keyword}%"
            query = query.where(db.or_(Complaint.product_name.ilike(like), Complaint.model_name.ilike(like), Complaint.lot_no.ilike(like), Complaint.customer_name.ilike(like)))
        rows = db.session.scalars(query.order_by(Complaint.receipt_date.desc(), Complaint.created_at.desc())).all()
        today = date.today()
        summary = {
            "total": len(all_market_rows),
            "completed": sum(1 for r in all_market_rows if r.status == "completed"),
            "open": sum(1 for r in all_market_rows if r.status not in {"completed", "overdue"}),
            "overdue": sum(1 for r in all_market_rows if r.status == "overdue"),
            "quantity": sum(r.complaint_qty for r in all_market_rows),
        }
        return render_template("complaints.html", rows=rows, market=market, selected_province=selected_province,
            province_counts=province_counts, provinces=KOREA_PROVINCES, summary=summary, q=keyword,
            status=status_value, status_labels=COMPLAINT_STATUS_LABELS, today=today)

    @app.route("/complaints/<uuid:complaint_id>", methods=["GET", "POST"])
    @login_required
    def complaint_detail(complaint_id):
        complaint = db.get_or_404(Complaint, complaint_id)
        user = current_user()
        if request.method == "POST":
            if user.role not in {"admin", "editor"}:
                abort(403)
            status_value = request.form.get("status", "")
            if status_value not in VALID_COMPLAINT_STATUSES:
                abort(400)
            complaint.receipt_date = date.fromisoformat(request.form["receipt_date"])
            complaint.province = request.form.get("province", "").strip() or None
            complaint.customer_name = request.form["customer_name"].strip()
            complaint.owner = request.form.get("owner", "").strip()
            complaint.product_name = request.form["product_name"].strip()
            complaint.model_name = request.form["model_name"].strip()
            complaint.lot_no = request.form["lot_no"].strip()
            complaint.volume = request.form.get("volume", "").strip()
            complaint.shipment_qty = max(0, int(request.form.get("shipment_qty") or 0))
            complaint.complaint_qty = max(0, int(request.form.get("complaint_qty") or 0))
            complaint.complaint_type = request.form["complaint_type"].strip()
            complaint.complaint_detail = request.form["complaint_detail"].strip()
            complaint.investigation = request.form.get("investigation", "").strip()
            complaint.investigation_result = request.form.get("investigation_result", "").strip()
            complaint.action_detail = request.form.get("action_detail", "").strip()
            complaint.handling_type = request.form.get("handling_type", "").strip()
            complaint.handled_date = date.fromisoformat(request.form["handled_date"]) if request.form.get("handled_date") else None
            complaint.status = status_value
            complaint.capa_required = request.form.get("capa_required") == "on"
            complaint.closure_reason = request.form.get("closure_reason", "").strip()
            complaint.updated_by = user.id
            audit("complaint_updated", "complaint", complaint.id, complaint.complaint_no)
            db.session.commit()
            flash("고객불만 이력이 수정되었습니다.", "success")
            return redirect(url_for("complaint_detail", complaint_id=complaint.id))
        return render_template("complaint_detail.html", complaint=complaint, status_labels=COMPLAINT_STATUS_LABELS)

    @app.get("/labeling/GMP")
    @login_required
    def labeling_master():
        assets = []
        for slug, name in LABELING_TYPES:
            row = db.session.scalar(db.select(LabelingAsset).where(
                LabelingAsset.standard == "GMP", LabelingAsset.item_type == slug
            ).order_by(
                db.case((LabelingAsset.status == "current", 0), (LabelingAsset.status == "review", 1), else_=2),
                LabelingAsset.updated_at.desc()
            ))
            if row:
                assets.append(row)
        ready_count = sum(1 for row in assets if row.status == "current")
        return render_template("labeling_master.html", assets=assets, ready_count=ready_count,
            status_labels=LABELING_STATUS_LABELS, icons=LABELING_ICONS)

    @app.route("/labeling/<uuid:asset_id>", methods=["GET", "POST"])
    @login_required
    def labeling_detail(asset_id):
        asset = db.get_or_404(LabelingAsset, asset_id)
        user = current_user()
        if request.method == "POST":
            if user.role not in {"admin", "editor"}:
                abort(403)
            status_value = request.form.get("status", "")
            if status_value not in {"review", "current"}:
                abort(400)
            upload = request.files.get("file")
            if upload and upload.filename and (
                not allowed_file(upload.filename) or upload.filename.rsplit(".", 1)[1].lower() not in {"jpg", "jpeg", "png", "pdf"}
            ):
                flash("시안은 JPG, PNG 또는 PDF 파일만 등록할 수 있습니다.", "error")
                return redirect(url_for("labeling_detail", asset_id=asset.id))
            is_placeholder = asset.status == "preparing" and not asset.control_no
            target = asset if is_placeholder else LabelingAsset(
                standard=asset.standard, item_type=asset.item_type, item_name=asset.item_name,
                created_by=user.id
            )
            if status_value == "current":
                previous = db.session.scalars(db.select(LabelingAsset).where(
                    LabelingAsset.standard == asset.standard, LabelingAsset.item_type == asset.item_type,
                    LabelingAsset.status == "current", LabelingAsset.id != target.id
                )).all()
                for row in previous:
                    row.status = "obsolete"
                    row.updated_by = user.id
            target.product_name = request.form.get("product_name", "").strip()
            target.control_no = request.form["control_no"].strip()
            target.revision = request.form["revision"].strip()
            target.effective_date = date.fromisoformat(request.form["effective_date"]) if request.form.get("effective_date") else None
            target.status = status_value
            target.description = request.form.get("description", "").strip()
            target.updated_by = user.id
            if upload and upload.filename:
                original = secure_filename(upload.filename)
                stored = f"label_{uuid.uuid4().hex}_{original}"
                upload.save(Path(app.config["UPLOAD_FOLDER"]) / stored)
                target.file_name, target.stored_name = original, stored
            elif not is_placeholder:
                target.file_name, target.stored_name = asset.file_name, asset.stored_name
            db.session.add(target)
            audit("labeling_revision_created" if not is_placeholder else "labeling_master_registered",
                "labeling_asset", target.id, f"{target.item_name} {target.control_no} Rev.{target.revision}")
            db.session.commit()
            flash("마스터샘플이 저장되었습니다.", "success")
            return redirect(url_for("labeling_detail", asset_id=target.id))
        history = db.session.scalars(db.select(LabelingAsset).where(
            LabelingAsset.standard == asset.standard, LabelingAsset.item_type == asset.item_type
        ).order_by(LabelingAsset.created_at.desc())).all()
        return render_template("labeling_detail.html", asset=asset, history=history,
            status_labels=LABELING_STATUS_LABELS, icons=LABELING_ICONS)

    @app.get("/labeling/<uuid:asset_id>/file")
    @login_required
    def labeling_file(asset_id):
        asset = db.get_or_404(LabelingAsset, asset_id)
        if not asset.stored_name:
            abort(404)
        return send_from_directory(app.config["UPLOAD_FOLDER"], asset.stored_name,
            as_attachment=request.args.get("download") == "1", download_name=asset.file_name)

    @app.route("/documents/<category>", defaults={"section": "records"}, methods=["GET", "POST"])
    @app.route("/documents/<category>/<section>", methods=["GET", "POST"])
    @login_required
    def documents(category, section):
        category = category.upper()
        if category not in {"GMP", "GTP"}:
            abort(404)
        section_map = dict(WORK_SECTIONS[category])
        if section not in section_map:
            abort(404)
        section_name = section_map[section]
        if category == "GMP" and section == "complaints":
            return redirect(url_for("complaints_dashboard"))
        if category == "GMP" and section == "labeling":
            return redirect(url_for("labeling_master"))
        user = current_user()
        if request.method == "POST":
            if user.role not in {"admin", "editor"}:
                abort(403)
            upload = request.files.get("file")
            if upload and upload.filename and not allowed_file(upload.filename):
                flash("허용되지 않는 파일 형식입니다.", "error")
                return redirect(url_for("documents", category=category, section=section))
            status_value = request.form.get("status", "draft")
            if status_value not in VALID_DOCUMENT_STATUSES - {"confirmed"}:
                abort(400)
            doc = Document(
                category=category, section=section, document_no=request.form["document_no"].strip(), title=request.form["title"].strip(),
                revision=request.form.get("revision", "0").strip(), effective_date=date.fromisoformat(request.form["effective_date"]) if request.form.get("effective_date") else None,
                status=status_value, description=request.form.get("description", "").strip(),
                created_by=user.id, updated_by=user.id,
            )
            if upload and upload.filename:
                original = secure_filename(upload.filename)
                stored = f"{uuid.uuid4().hex}_{original}"
                upload.save(Path(app.config["UPLOAD_FOLDER"]) / stored)
                doc.file_name, doc.stored_name = original, stored
            try:
                db.session.add(doc)
                audit("document_created", "document", doc.id, f"{category} {doc.document_no}")
                db.session.commit()
                flash("문서가 등록되었습니다.", "success")
            except SQLAlchemyError:
                db.session.rollback()
                flash("동일한 문서번호와 개정번호가 있거나 저장에 실패했습니다.", "error")
            return redirect(url_for("documents", category=category, section=section))
        query = db.select(Document).where(Document.category == category, Document.section == section)
        keyword = request.args.get("q", "").strip()
        status = request.args.get("status", "").strip()
        if keyword:
            query = query.where(db.or_(Document.document_no.ilike(f"%{keyword}%"), Document.title.ilike(f"%{keyword}%")))
        if status:
            query = query.where(Document.status == status)
        rows = db.session.scalars(query.order_by(Document.updated_at.desc())).all()
        return render_template("documents.html", category=category, section=section, section_name=section_name, sections=WORK_SECTIONS[category], documents=rows, q=keyword, status=status)

    @app.post("/documents/<uuid:document_id>/delete")
    @roles_required("admin", "editor")
    def delete_document(document_id):
        doc = db.get_or_404(Document, document_id)
        user = current_user()
        if user.role == "editor" and (doc.status == "confirmed" or doc.created_by != user.id):
            abort(403)
        category = doc.category
        if doc.stored_name:
            path = Path(app.config["UPLOAD_FOLDER"]) / doc.stored_name
            if path.exists():
                path.unlink()
        audit("document_deleted", "document", doc.id, f"{doc.category} {doc.document_no}")
        db.session.delete(doc)
        db.session.commit()
        flash("문서가 삭제되었습니다.", "success")
        return redirect(url_for("documents", category=category, section=doc.section))

    @app.route("/documents/<uuid:document_id>/edit", methods=["GET", "POST"])
    @roles_required("admin", "editor")
    def edit_document(document_id):
        doc = db.get_or_404(Document, document_id)
        if doc.status == "confirmed" and current_user().role != "admin":
            abort(403)
        if request.method == "POST":
            if request.form.get("status") not in VALID_DOCUMENT_STATUSES - {"confirmed"}:
                abort(400)
            doc.document_no = request.form["document_no"].strip()
            doc.title = request.form["title"].strip()
            doc.revision = request.form["revision"].strip()
            doc.effective_date = date.fromisoformat(request.form["effective_date"]) if request.form.get("effective_date") else None
            doc.status = request.form["status"]
            doc.description = request.form.get("description", "").strip()
            doc.updated_by = current_user().id
            audit("document_updated", "document", doc.id, f"{doc.category} {doc.document_no}")
            try:
                db.session.commit(); flash("문서가 수정되었습니다.", "success")
                return redirect(url_for("documents", category=doc.category, section=doc.section))
            except SQLAlchemyError:
                db.session.rollback(); flash("중복 문서번호 또는 저장 오류입니다.", "error")
        return render_template("document_edit.html", document=doc)

    @app.get("/documents/<uuid:document_id>/download")
    @login_required
    def download_document(document_id):
        doc = db.get_or_404(Document, document_id)
        if not doc.stored_name:
            abort(404)
        return send_from_directory(app.config["UPLOAD_FOLDER"], doc.stored_name, as_attachment=True, download_name=doc.file_name)

    @app.post("/documents/<uuid:document_id>/confirm")
    @roles_required("admin")
    def confirm_document(document_id):
        doc = db.get_or_404(Document, document_id)
        doc.status, doc.confirmed_at, doc.updated_by = "confirmed", utcnow(), current_user().id
        audit("document_confirmed", "document", doc.id, f"{doc.category} {doc.document_no}")
        db.session.commit()
        flash("문서가 확정되었습니다.", "success")
        return redirect(url_for("documents", category=doc.category, section=doc.section))

    @app.route("/profile/password", methods=["GET", "POST"])
    @login_required
    def change_password():
        user = current_user()
        if request.method == "POST":
            current = request.form.get("current_password", "")
            new = request.form.get("new_password", "")
            confirm = request.form.get("confirm_password", "")
            if not user.check_password(current):
                flash("현재 비밀번호가 올바르지 않습니다.", "error")
            elif len(new) < 10 or not any(c.isalpha() for c in new) or not any(c.isdigit() for c in new) or new == current:
                flash("새 비밀번호는 영문·숫자를 포함한 10자 이상이어야 합니다.", "error")
            elif new != confirm:
                flash("새 비밀번호 확인이 일치하지 않습니다.", "error")
            else:
                user.set_password(new)
                user.must_change_password = False
                audit("password_changed", "user", user.id)
                db.session.commit()
                session.clear()
                flash("비밀번호가 변경되었습니다. 다시 로그인하세요.", "success")
                return redirect(url_for("login"))
        return render_template("password.html")

    @app.get("/profile")
    @login_required
    def profile():
        return render_template("profile.html")

    @app.route("/admin/users", methods=["GET", "POST"])
    @roles_required("admin")
    def users():
        if request.method == "POST":
            login_id = User.normalize_login_id(request.form["login_id"])
            if db.session.scalar(db.select(User).where(func.lower(User.login_id) == login_id)):
                flash("이미 사용 중인 로그인 ID입니다.", "error")
            else:
                temp_password = request.form["temporary_password"]
                if len(temp_password) < 10:
                    flash("임시 비밀번호는 10자 이상이어야 합니다.", "error")
                    return redirect(url_for("users"))
                role = request.form.get("role", "")
                if role not in VALID_ROLES:
                    abort(400)
                user = User(login_id=login_id, name=request.form["name"].strip(), department=request.form.get("department", "").strip(), position=request.form.get("position", "").strip(), role=role, must_change_password=True)
                user.set_password(temp_password)
                db.session.add(user)
                audit("user_created", "user", user.id, f"role={user.role}")
                db.session.commit()
                flash("사용자가 생성되었습니다.", "success")
            return redirect(url_for("users"))
        return render_template("users.html", users=db.session.scalars(db.select(User).order_by(User.login_id)).all())

    @app.post("/admin/users/<uuid:user_id>/toggle")
    @roles_required("admin")
    def toggle_user(user_id):
        user = db.get_or_404(User, user_id)
        if user.id == current_user().id:
            flash("현재 로그인한 관리자 계정은 비활성화할 수 없습니다.", "error")
        else:
            user.is_active = not user.is_active
            audit("user_updated", "user", user.id, f"active={user.is_active}")
            db.session.commit()
            flash("사용자 상태가 변경되었습니다.", "success")
        return redirect(url_for("users"))

    @app.post("/admin/users/<uuid:user_id>/update")
    @roles_required("admin")
    def update_user(user_id):
        user = db.get_or_404(User, user_id)
        role = request.form.get("role", "")
        if role not in VALID_ROLES:
            abort(400)
        user.name = request.form["name"].strip()
        user.department = request.form.get("department", "").strip()
        user.position = request.form.get("position", "").strip()
        user.role = role
        audit("user_updated", "user", user.id, f"role={user.role}")
        db.session.commit(); flash("사용자 정보가 수정되었습니다.", "success")
        return redirect(url_for("users"))

    @app.post("/admin/users/<uuid:user_id>/reset-password")
    @roles_required("admin")
    def reset_password(user_id):
        user = db.get_or_404(User, user_id)
        temporary = request.form.get("temporary_password", "")
        if len(temporary) < 10:
            flash("임시 비밀번호는 10자 이상이어야 합니다.", "error")
        else:
            user.set_password(temporary); user.must_change_password = True
            audit("temporary_password_issued", "user", user.id)
            db.session.commit(); flash("임시 비밀번호가 발급되었습니다.", "success")
        return redirect(url_for("users"))

    @app.route("/admin/settings", methods=["GET", "POST"])
    @roles_required("admin")
    def settings():
        if request.method == "POST":
            for key in ("document_manager", "retention_note"):
                row = db.session.scalar(db.select(SystemSetting).where(SystemSetting.key == key))
                if not row:
                    row = SystemSetting(key=key, updated_by=current_user().id); db.session.add(row)
                row.value = request.form.get(key, "").strip(); row.updated_by = current_user().id
            audit("settings_updated", "system")
            db.session.commit(); flash("설정이 저장되었습니다.", "success")
            return redirect(url_for("settings"))
        values = {r.key:r.value for r in db.session.scalars(db.select(SystemSetting)).all()}
        return render_template("settings.html", values=values)

    @app.get("/admin/audit")
    @roles_required("admin")
    def audit_logs():
        logs = db.session.scalars(db.select(AuditLog).order_by(AuditLog.created_at.desc()).limit(500)).all()
        return render_template("audit.html", logs=logs)


def register_context(app):
    @app.context_processor
    def inject_globals():
        return {"current_user": current_user(), "to_kst": lambda dt: dt.astimezone(KST).strftime("%Y-%m-%d %H:%M") if dt else "-", "site_name": "서울 3-site 기술부(품질)", "section_label": lambda category, slug: dict(WORK_SECTIONS.get(category, [])).get(slug, slug)}


def register_errors(app):
    @app.teardown_request
    def rollback_on_error(error):
        if error:
            db.session.rollback()

    for code, message in [(403, "접근 권한이 없습니다."), (404, "페이지를 찾을 수 없습니다."), (500, "시스템 오류가 발생했습니다.")]:
        def handler(error, code=code, message=message):
            if code == 500:
                db.session.rollback()
            return render_template("error.html", code=code, message=message), code
        app.register_error_handler(code, handler)


try:
    app = create_app()
except RuntimeError as startup_error:
    app = Flask(__name__)
    app.config["STARTUP_ERROR"] = str(startup_error)

    @app.get("/health")
    def unavailable_health():
        return jsonify(status="error", database=False, database_backend="postgresql", database_writable=False, application_ready=False), 503

    @app.route("/", defaults={"path": ""})
    @app.route("/<path:path>")
    def unavailable(path):
        return "서비스 준비가 완료되지 않았습니다. PostgreSQL 및 필수 환경설정을 확인하세요.", 503


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "8000")), debug=False)
