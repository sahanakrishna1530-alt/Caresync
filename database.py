
"""
database.py - Database connection and initialization for CareSync.
Uses SQLite with parameterized queries for safe persistence.
Supports booking, filtering, cancellation, and rescheduling.
"""

import os
import sqlite3
from datetime import datetime

DEFAULT_DB_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "caresync.db"
)


def get_db_path(custom_path=None):
    """Return the database path, allowing overrides for testing."""
    if custom_path:
        return custom_path
    return os.environ.get("CARESYNC_DB_PATH", DEFAULT_DB_PATH)


def get_db_connection(db_path=None):
    """Create a SQLite connection with dictionary-like row access."""
    conn = sqlite3.connect(get_db_path(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(db_path=None):
    """
    Initialize tables and seed doctors when needed.
    Safely migrates existing appointment databases.
    """
    conn = get_db_connection(db_path)
    cursor = conn.cursor()

    try:
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
                consultation_type TEXT,
                price INTEGER,
                address TEXT,
                FOREIGN KEY (doctor_id)
                    REFERENCES doctors (id) ON DELETE CASCADE
            )
        """)

        # Add newer columns to databases created by older versions.
        existing_columns = {
            row["name"]
            for row in cursor.execute(
                "PRAGMA table_info(appointments)"
            ).fetchall()
        }

        new_columns = {
            "consultation_type": "TEXT",
            "price": "INTEGER",
            "address": "TEXT"
        }

        for column, column_type in new_columns.items():
            if column not in existing_columns:
                cursor.execute(
                    f"ALTER TABLE appointments "
                    f"ADD COLUMN {column} {column_type}"
                )

        # Add sample doctors only when the table is empty.
        cursor.execute("SELECT COUNT(*) AS count FROM doctors")

        if cursor.fetchone()["count"] == 0:
            sample_doctors = [
                ("Dr. Sarah Jenkins", "Cardiology",
                 "09:00", "17:00", "Room 201"),
                ("Dr. Marcus Vance", "Neurology",
                 "09:00", "16:30", "Room 305"),
                ("Dr. Elena Rostova", "Pediatrics",
                 "08:30", "15:30", "Room 104"),
                ("Dr. David Kim", "Orthopedics",
                 "10:00", "18:00", "Room 412"),
                ("Dr. Priya Sharma", "General Medicine",
                 "09:00", "17:00", "Room 102")
            ]

            cursor.executemany("""
                INSERT INTO doctors (
                    name,
                    specialty,
                    working_hours_start,
                    working_hours_end,
                    room_number
                ) VALUES (?, ?, ?, ?, ?)
            """, sample_doctors)

        conn.commit()

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()


def get_all_doctors(db_path=None):
    """Retrieve all doctors."""
    conn = get_db_connection(db_path)

    try:
        rows = conn.execute(
            "SELECT * FROM doctors ORDER BY name ASC"
        ).fetchall()

        return [dict(row) for row in rows]

    finally:
        conn.close()


def get_doctor_by_id(doctor_id, db_path=None):
    """Retrieve one doctor by ID."""
    conn = get_db_connection(db_path)

    try:
        row = conn.execute(
            "SELECT * FROM doctors WHERE id = ?",
            (doctor_id,)
        ).fetchone()

        return dict(row) if row else None

    finally:
        conn.close()


def get_appointments(
    db_path=None,
    doctor_id=None,
    date=None,
    status=None
):
    """Retrieve appointments with optional filters and doctor details."""
    conn = get_db_connection(db_path)

    try:
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
                a.consultation_type,
                a.price,
                a.address,
                d.name AS doctor_name,
                d.specialty AS doctor_specialty,
                d.room_number AS doctor_room
            FROM appointments a
            JOIN doctors d ON a.doctor_id = d.id
            WHERE 1 = 1
        """

        params = []

        if doctor_id is not None and doctor_id != "":
            query += " AND a.doctor_id = ?"
            params.append(doctor_id)

        if date:
            query += " AND a.appointment_date = ?"
            params.append(date)

        if status:
            query += " AND a.status = ?"
            params.append(status)

        query += """
            ORDER BY a.appointment_date ASC, a.start_time ASC
        """

        rows = conn.execute(query, params).fetchall()
        return [dict(row) for row in rows]

    finally:
        conn.close()


def get_appointment_by_id(appointment_id, db_path=None):
    """Retrieve one appointment with its doctor's details."""
    conn = get_db_connection(db_path)

    try:
        row = conn.execute("""
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
                a.consultation_type,
                a.price,
                a.address,
                d.name AS doctor_name,
                d.specialty AS doctor_specialty,
                d.room_number AS doctor_room
            FROM appointments a
            JOIN doctors d ON a.doctor_id = d.id
            WHERE a.id = ?
        """, (appointment_id,)).fetchone()

        return dict(row) if row else None

    finally:
        conn.close()


def insert_appointment(
    patient_name,
    doctor_id,
    appointment_date,
    start_time,
    end_time,
    duration_minutes,
    reason="",
    db_path=None,
    consultation_type="in_person",
    price=None,
    address=""
):
    """Insert an appointment and return its ID."""
    conn = get_db_connection(db_path)

    try:
        now_str = datetime.now().isoformat()

        cursor = conn.execute("""
            INSERT INTO appointments (
                patient_name,
                doctor_id,
                appointment_date,
                start_time,
                end_time,
                duration_minutes,
                reason,
                status,
                created_at,
                consultation_type,
                price,
                address
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, 'SCHEDULED', ?, ?, ?, ?)
        """, (
            patient_name,
            doctor_id,
            appointment_date,
            start_time,
            end_time,
            duration_minutes,
            reason,
            now_str,
            consultation_type,
            price,
            address
        ))

        conn.commit()
        return cursor.lastrowid

    finally:
        conn.close()


def update_appointment_status(
    appointment_id,
    new_status,
    db_path=None
):
    """Update an appointment's status."""
    conn = get_db_connection(db_path)

    try:
        cursor = conn.execute("""
            UPDATE appointments
            SET status = ?
            WHERE id = ?
        """, (new_status, appointment_id))

        conn.commit()
        return cursor.rowcount > 0

    finally:
        conn.close()


def update_appointment_schedule(
    appointment_id,
    appointment_date,
    start_time,
    end_time,
    duration_minutes,
    db_path=None
):
    """
    Update the schedule of an existing scheduled appointment.

    Only the date, start time, end time, and duration are changed.
    All patient and consultation details remain unchanged.

    Returns:
        (True, success_message) on success
        (False, error_message) if the update cannot be performed
    """
    conn = get_db_connection(db_path)

    try:
        # Acquire the SQLite write lock before checking and updating.
        conn.execute("BEGIN IMMEDIATE")

        appointment = conn.execute("""
            SELECT status
            FROM appointments
            WHERE id = ?
        """, (appointment_id,)).fetchone()

        if not appointment:
            conn.rollback()
            return False, "Appointment not found."

        if appointment["status"] != "SCHEDULED":
            conn.rollback()
            return False, (
                "Only scheduled appointments can be rescheduled."
            )

        cursor = conn.execute("""
            UPDATE appointments
            SET appointment_date = ?,
                start_time = ?,
                end_time = ?,
                duration_minutes = ?
            WHERE id = ?
              AND status = 'SCHEDULED'
        """, (
            appointment_date,
            start_time,
            end_time,
            duration_minutes,
            appointment_id
        ))

        if cursor.rowcount != 1:
            conn.rollback()
            return False, "Appointment could not be rescheduled."

        conn.commit()

        return True, "Appointment rescheduled successfully."

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()
