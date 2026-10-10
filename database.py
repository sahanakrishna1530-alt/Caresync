"""
database.py - Database connection and initialization for CareSync.
Uses SQLite with parameterized queries for safe and reliable persistence.
"""

import os
import sqlite3
from datetime import datetime

DEFAULT_DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "caresync.db")


def get_db_path(custom_path=None):
    """Return the database path, allowing overrides for testing."""
    if custom_path:
        return custom_path
    return os.environ.get("CARESYNC_DB_PATH", DEFAULT_DB_PATH)


def get_db_connection(db_path=None):
    """
    Establish a connection to the SQLite database.
    Returns a connection object configured with sqlite3.Row for dictionary-like row access.
    """
    path = get_db_path(db_path)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(db_path=None):
    """
    Initialize database tables and seed sample doctors if empty.
    Safe to run repeatedly (uses CREATE TABLE IF NOT EXISTS).
    """
    conn = get_db_connection(db_path)
    cursor = conn.cursor()

    # Create doctors table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS doctors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            specialty TEXT NOT NULL,
            working_hours_start TEXT NOT NULL DEFAULT '09:00',
            working_hours_end TEXT NOT NULL DEFAULT '17:00',
            room_number TEXT NOT NULL DEFAULT '101'
        )
    """)

    # Create appointments table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS appointments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_name TEXT NOT NULL,
            doctor_id INTEGER NOT NULL,
            appointment_date TEXT NOT NULL,
            start_time TEXT NOT NULL,
            end_time TEXT NOT NULL,
            duration_minutes INTEGER NOT NULL,
            reason TEXT DEFAULT '',
            status TEXT NOT NULL DEFAULT 'SCHEDULED',
            created_at TEXT NOT NULL,
            FOREIGN KEY (doctor_id) REFERENCES doctors (id) ON DELETE CASCADE
        )
    """)

    # Seed initial doctors if table is currently empty
    cursor.execute("SELECT COUNT(*) AS count FROM doctors")
    count = cursor.fetchone()["count"]

    if count == 0:
        sample_doctors = [
            ("Dr. Sarah Jenkins", "Cardiology", "09:00", "17:00", "Room 201"),
            ("Dr. Marcus Vance", "Neurology", "09:00", "16:30", "Room 305"),
            ("Dr. Elena Rostova", "Pediatrics", "08:30", "15:30", "Room 104"),
            ("Dr. David Kim", "Orthopedics", "10:00", "18:00", "Room 412"),
            ("Dr. Priya Sharma", "General Medicine", "09:00", "17:00", "Room 102")
        ]
        cursor.executemany("""
            INSERT INTO doctors (name, specialty, working_hours_start, working_hours_end, room_number)
            VALUES (?, ?, ?, ?, ?)
        """, sample_doctors)

    conn.commit()
    conn.close()


def get_all_doctors(db_path=None):
    """Retrieve all available doctors from the database."""
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM doctors ORDER BY name ASC")
    rows = cursor.fetchall()
    doctors = [dict(row) for row in rows]
    conn.close()
    return doctors


def get_doctor_by_id(doctor_id, db_path=None):
    """Retrieve a single doctor by ID."""
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM doctors WHERE id = ?", (doctor_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def get_appointments(db_path=None, doctor_id=None, date=None, status=None):
    """
    Retrieve appointments with optional filtering by doctor, date, or status.
    Joins with the doctors table to include doctor details.
    """
    conn = get_db_connection(db_path)
    cursor = conn.cursor()

    query = """
        SELECT 
            a.id,
            a.patient_name,
            a.doctor_id,
            a.appointment_date,
            a.start_time,
            a.end_time,
            a.duration_minutes,
            a.reason,
            a.status,
            a.created_at,
            d.name AS doctor_name,
            d.specialty AS doctor_specialty,
            d.room_number AS doctor_room
        FROM appointments a
        JOIN doctors d ON a.doctor_id = d.id
        WHERE 1=1
    """
    params = []

    if doctor_id:
        query += " AND a.doctor_id = ?"
        params.append(doctor_id)

    if date:
        query += " AND a.appointment_date = ?"
        params.append(date)

    if status:
        query += " AND a.status = ?"
        params.append(status)

    query += " ORDER BY a.appointment_date ASC, a.start_time ASC"

    cursor.execute(query, params)
    rows = cursor.fetchall()
    appointments = [dict(row) for row in rows]
    conn.close()
    return appointments


def get_appointment_by_id(appointment_id, db_path=None):
    """Retrieve an appointment by its ID."""
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT 
            a.id,
            a.patient_name,
            a.doctor_id,
            a.appointment_date,
            a.start_time,
            a.end_time,
            a.duration_minutes,
            a.reason,
            a.status,
            a.created_at,
            d.name AS doctor_name,
            d.specialty AS doctor_specialty,
            d.room_number AS doctor_room
        FROM appointments a
        JOIN doctors d ON a.doctor_id = d.id
        WHERE a.id = ?
    """, (appointment_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def insert_appointment(patient_name, doctor_id, appointment_date, start_time, end_time, duration_minutes, reason="", db_path=None):
    """Insert a new appointment record and return its generated ID."""
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    now_str = datetime.now().isoformat()
    cursor.execute("""
        INSERT INTO appointments (
            patient_name, doctor_id, appointment_date, start_time, end_time,
            duration_minutes, reason, status, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, 'SCHEDULED', ?)
    """, (patient_name, doctor_id, appointment_date, start_time, end_time, duration_minutes, reason, now_str))
    conn.commit()
    new_id = cursor.lastrowid
    conn.close()
    return new_id


def update_appointment_status(appointment_id, new_status, db_path=None):
    """Update status of an appointment (e.g., 'CANCELLED')."""
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE appointments
        SET status = ?
        WHERE id = ?
    """, (new_status, appointment_id))
    affected = cursor.rowcount
    conn.commit()
    conn.close()
    return affected > 0
