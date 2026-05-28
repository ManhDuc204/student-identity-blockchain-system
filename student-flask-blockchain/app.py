import os
import json
import hashlib
from datetime import datetime, timedelta

from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_session import Session
from werkzeug.security import check_password_hash, generate_password_hash

from blockchain.connect_blockchain import (
    get_latest_block,
    get_stats,
    send_add_student_tx,
    send_delete_student_tx,
    get_student_hash_onchain,
)


from utils.security import sha256_hex
from utils.qr import generate_student_qr
from utils.pdf_export import export_students_pdf

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DB_DIR = os.path.join(BASE_DIR, "database")
DB_PATH = os.path.join(DB_DIR, "student.db")

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-key-change-me")

# Session
app.config["SESSION_TYPE"] = "filesystem"
app.config["SESSION_PERMANENT"] = True
app.config["PERMANENT_SESSION_LIFETIME"] = int(os.environ.get("SESSION_TIMEOUT_SECONDS", 1800))
Session(app)

# Database
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get(
    "DATABASE_URL",
    "sqlite:///{db}".format(db=DB_PATH),
)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

# Define models here to ensure they use the same SQLAlchemy instance
from flask_sqlalchemy import SQLAlchemy as _SQLAlchemy


class AdminUser(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)


class Student(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    student_id = db.Column(db.String(64), unique=True, nullable=False)
    full_name = db.Column(db.String(200), nullable=False)
    birth_date = db.Column(db.String(20), nullable=True)
    student_class = db.Column(db.String(80), nullable=True)
    faculty = db.Column(db.String(120), nullable=True)
    email = db.Column(db.String(120), nullable=True)
    phone = db.Column(db.String(40), nullable=True)

    data_hash = db.Column(db.String(64), unique=True, nullable=False)
    qr_filename = db.Column(db.String(200), nullable=True)
    avatar_filename = db.Column(db.String(200), nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class BlockchainTxLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    tx_hash = db.Column(db.String(120), nullable=False)
    block_number = db.Column(db.Integer, nullable=True)
    gas_used = db.Column(db.Integer, nullable=True)
    timestamp = db.Column(db.DateTime, nullable=True)

    event_student_id = db.Column(db.String(64), nullable=True)
    action = db.Column(db.String(20), nullable=True)  # ADDED / DELETED


def current_admin():
    return session.get("admin")


def require_admin(fn):
    def wrapper(*args, **kwargs):
        if not current_admin():
            return redirect(url_for("login"))
        return fn(*args, **kwargs)
    wrapper.__name__ = fn.__name__
    return wrapper


def init_admin_if_needed():
    # Tạo admin mặc định nếu chưa có
    username = os.environ.get("ADMIN_USERNAME", "admin")
    password = os.environ.get("ADMIN_PASSWORD", "admin123")

    admin = AdminUser.query.filter_by(username=username).first()
    if not admin:
        admin = AdminUser(username=username, password_hash=generate_password_hash(password))
        db.session.add(admin)
        db.session.commit()


@app.before_request
def ensure_session_timeout():
    # Session Flask đã có lifetime, chỉ để hiển thị ổn định
    session.permanent = True


# --------------------
# Routes
# --------------------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        admin = AdminUser.query.filter_by(username=username).first()
        if not admin or not check_password_hash(admin.password_hash, password):
            flash("Sai username hoặc password", "danger")
            return render_template("login.html")

        session["admin"] = {"username": username}
        flash("Đăng nhập thành công", "success")
        return redirect(url_for("dashboard"))

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("Đã đăng xuất", "info")
    return redirect(url_for("login"))


@app.route("/")
@require_admin
def dashboard():
    stats = get_stats()
    latest_block = get_latest_block()

    verified_count = Student.query.count()  # count local

    total_students = Student.query.count()

    return render_template(
        "dashboard.html",
        stats=stats,
        latest_block=latest_block,
        total_students=total_students,
        verified_count=verified_count,
    )


@app.route("/students")
@require_admin
def students():
    q = request.args.get("q", "").strip()
    query = Student.query
    if q:
        query = query.filter(
            (Student.student_id.like(f"%{q}%")) |
            (Student.full_name.like(f"%{q}%")) |
            (Student.email.like(f"%{q}%"))
        )

    all_students = query.order_by(Student.created_at.desc()).all()
    return render_template("students.html", students=all_students)


@app.route("/students/add", methods=["GET", "POST"])
@require_admin
def add_student():
    if request.method == "POST":
        student_id = request.form.get("student_id", "").strip()
        full_name = request.form.get("full_name", "").strip()
        birth_date = request.form.get("birth_date", "").strip()
        student_class = request.form.get("student_class", "").strip()
        faculty = request.form.get("faculty", "").strip()
        email = request.form.get("email", "").strip()
        phone = request.form.get("phone", "").strip()

        # Validate
        if not student_id or not full_name:
            flash("Vui lòng nhập student_id và họ tên", "danger")
            return redirect(url_for("add_student"))

        if Student.query.filter_by(student_id=student_id).first():
            flash("Trùng student_id. Vui lòng nhập mã khác.", "danger")
            return redirect(url_for("add_student"))

        # Avatar upload (optional)
        avatar_filename = None
        avatar = request.files.get("avatar")
        if avatar and avatar.filename:
            uploads_dir = os.path.join(app.static_folder, "uploads")
            os.makedirs(uploads_dir, exist_ok=True)
            safe_name = f"{student_id}_{int(datetime.utcnow().timestamp())}_{avatar.filename}".replace(" ", "_")
            avatar.save(os.path.join(uploads_dir, safe_name))
            avatar_filename = safe_name

        # Build deterministic payload for hashing
        payload = {
            "student_id": student_id,
            "full_name": full_name,
            "birth_date": birth_date,
            "student_class": student_class,
            "faculty": faculty,
            "email": email,
            "phone": phone,
        }
        # sha256 over canonical JSON
        data_hash_hex = sha256_hex(json.dumps(payload, ensure_ascii=False, sort_keys=True))

        try:
            # Send tx to blockchain
            tx_receipt = send_add_student_tx(student_id=student_id, data_hash_hex=data_hash_hex)

            # Save to DB
            qr_dir = os.path.join(app.static_folder, "qr")
            os.makedirs(qr_dir, exist_ok=True)
            qr_filename = generate_student_qr(student_id=student_id, qr_dir=qr_dir)

            student = Student(
                student_id=student_id,
                full_name=full_name,
                birth_date=birth_date,
                student_class=student_class,
                faculty=faculty,
                email=email,
                phone=phone,
                data_hash=data_hash_hex,
                qr_filename=qr_filename,
                avatar_filename=avatar_filename,
            )
            db.session.add(student)

            # tx log
            block_number = tx_receipt.blockNumber if tx_receipt else None
            gas_used = tx_receipt.gasUsed if tx_receipt else None
            # timestamp from block
            timestamp_dt = None
            if tx_receipt and block_number is not None:
                try:
                    timestamp_dt = get_latest_block().get("timestamp_dt")
                except Exception:
                    timestamp_dt = None

            tx_log = BlockchainTxLog(
                tx_hash=tx_receipt.transactionHash.hex() if tx_receipt else "",
                block_number=int(block_number) if block_number is not None else None,
                gas_used=int(gas_used) if gas_used is not None else None,
                timestamp=timestamp_dt,
                event_student_id=student_id,
                action="ADDED",
            )

            db.session.add(tx_log)
            db.session.commit()

            flash("Đã thêm sinh viên và ghi hash lên blockchain thành công!", "success")
            return redirect(url_for("students"))
        except Exception as e:
            db.session.rollback()
            flash(f"Lỗi khi ghi lên blockchain: {str(e)}", "danger")
            return redirect(url_for("add_student"))

    return render_template("add_student.html")


@app.route("/verify", methods=["GET", "POST"])
@require_admin
def verify():
    result = None
    if request.method == "POST":
        student_id = (request.form.get("student_id") or "").strip()
        if not student_id:
            flash("Vui lòng nhập student_id", "danger")
            return render_template("verify.html", result=None)

        student = Student.query.filter_by(student_id=student_id).first()
        if not student:
            result = {"status": "not_found", "message": "Không tìm thấy sinh viên trong database."}
            return render_template("verify.html", result=result)

        # Local hash vs on-chain hash
        onchain_hash_bytes32 = get_student_hash_onchain(student_id)
        if onchain_hash_bytes32 is None or str(onchain_hash_bytes32) == "0x0000000000000000000000000000000000000000000000000000000000":
            result = {"status": "missing_onchain", "message": "Sinh viên chưa được ghi hash lên blockchain."}
            return render_template("verify.html", result=result)

        # Compare bytes32 to hex string: stored hex is 64 hex chars
        onchain_hash_hex = onchain_hash_bytes32.hex() if hasattr(onchain_hash_bytes32, "hex") else str(onchain_hash_bytes32)
        onchain_hash_hex = onchain_hash_hex.replace("0x", "").lower()

        if onchain_hash_hex == student.data_hash.lower():
            result = {"status": "valid", "message": "Danh tính hợp lệ"}
        else:
            result = {"status": "invalid", "message": "Dữ liệu đã bị thay đổi"}

    return render_template("verify.html", result=result)


@app.route("/tx-logs")
@require_admin
def tx_logs():
    logs = BlockchainTxLog.query.order_by(BlockchainTxLog.id.desc()).limit(50).all()
    return render_template("tx_logs.html", logs=logs)


@app.route("/students/<student_id>/delete", methods=["POST"])
@require_admin
def delete_student_ui(student_id: str):
    student_id = (student_id or "").strip()
    if not student_id:
        flash("Invalid student_id", "danger")
        return redirect(url_for("students"))

    student = Student.query.filter_by(student_id=student_id).first()
    if not student:
        flash("Không tìm thấy sinh viên trong DB", "danger")
        return redirect(url_for("students"))

    try:
        # 1) ghi log DELETED lên blockchain (không xóa on-chain data)
        tx_receipt = send_delete_student_tx(student_id=student_id)

        # 2) xóa khỏi SQLite
        db.session.delete(student)

        block_number = tx_receipt.blockNumber if tx_receipt else None
        gas_used = tx_receipt.gasUsed if tx_receipt else None

        timestamp_dt = None
        if tx_receipt and block_number is not None:
            try:
                timestamp_dt = get_latest_block().get("timestamp_dt")
            except Exception:
                timestamp_dt = None

        tx_log = BlockchainTxLog(
            tx_hash=tx_receipt.transactionHash.hex() if tx_receipt else "",
            block_number=int(block_number) if block_number is not None else None,
            gas_used=int(gas_used) if gas_used is not None else None,
            timestamp=timestamp_dt,
            event_student_id=student_id,
            action="DELETED",
        )
        db.session.add(tx_log)

        db.session.commit()
        flash(f"Đã xóa khỏi DB và ghi log DELETED lên blockchain (tx: {tx_log.tx_hash[:18]}...)!", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Lỗi khi delete: {str(e)}", "danger")

    return redirect(url_for("students"))


@app.route("/students/export-pdf")
@require_admin
def export_pdf():

    q = request.args.get("q", "").strip()
    students_list = Student.query
    if q:
        students_list = students_list.filter(Student.full_name.like(f"%{q}%"))
    students_list = students_list.order_by(Student.created_at.desc()).all()

    pdf_path = export_students_pdf(students_list=students_list)
    return redirect(url_for("static", filename=os.path.relpath(pdf_path, app.static_folder)))


@app.route("/api/verify", methods=["POST"])
@require_admin
def api_verify():
    data = request.get_json(silent=True) or {}
    student_id = (data.get("student_id") or "").strip()

    student = Student.query.filter_by(student_id=student_id).first()
    if not student:
        return jsonify({"ok": False, "status": "not_found", "message": "Không tìm thấy sinh viên"})

    onchain_hash_bytes32 = get_student_hash_onchain(student_id)
    onchain_hash_hex = onchain_hash_bytes32.hex().replace("0x", "").lower()

    ok = onchain_hash_hex == student.data_hash.lower()
    return jsonify({
        "ok": True,
        "status": "valid" if ok else "invalid",
        "message": "Danh tính hợp lệ" if ok else "Dữ liệu đã bị thay đổi",
        "localHash": student.data_hash,
        "onchainHash": onchain_hash_hex,
    })


# --------------------
# Boot
# --------------------
if __name__ == "__main__":
    with app.app_context():
        os.makedirs(DB_DIR, exist_ok=True)

        # Safe schema migration (SQLite): ensures blockchain_tx_log.action exists.
        # Must run BEFORE any insertions into BlockchainTxLog.
        try:
            from migrate_db import ensure_blockchain_tx_log_schema

            ensure_blockchain_tx_log_schema(db_path=DB_PATH)
        except Exception as e:
            # Don't crash the whole app if migration fails; log clearly.
            print(f"[DB MIGRATE] Failed to ensure schema for blockchain_tx_log.action: {e}")

        db.create_all()
        init_admin_if_needed()

    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)


