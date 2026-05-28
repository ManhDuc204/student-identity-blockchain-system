from datetime import datetime

from flask_sqlalchemy import SQLAlchemy

# IMPORTANT:
# Flask app in app.py must provide the SQLAlchemy instance.
# This module starts with an uninitialized db placeholder.

db = SQLAlchemy()



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

    data_hash = db.Column(db.String(64), unique=True, nullable=False)  # sha256 hex
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


