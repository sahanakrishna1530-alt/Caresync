"""
app.py - Flask web application for CareSync: Smart Hospital Appointment Scheduler.
Provides HTML views for the booking portal and dashboard, alongside RESTful API endpoints.
"""

import os
from datetime import date, datetime
from flask import Flask, render_template, request, jsonify, redirect, url_for

from database import (
    init_db,
    get_all_doctors,
    get_doctor_by_id,
    get_appointments,
    get_appointment_by_id
)
from scheduler import (
    book_appointment,
    cancel_appointment,
    check_doctor_availability,
    find_alternative_slots
)

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "caresync-hackathon-secret-key-2026")

# Initialize database tables and sample doctors on launch
with app.app_context():
    init_db()


# ---------------------------------------------------------------------------
# HTML Page Routes
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    """Render the appointment booking portal and today's schedule glance."""
    doctors = get_all_doctors()
    today_str = date.today().isoformat()
    recent_appointments = get_appointments(date=today_str, status="SCHEDULED")
    return render_template(
        "index.html",
        doctors=doctors,
        today=today_str,
        recent_appointments=recent_appointments
    )


@app.route("/dashboard")
def dashboard():
    """Render the hospital appointment management dashboard."""
    doctors = get_all_doctors()
    today_str = date.today().isoformat()
    appointments = get_appointments()

    # Calculate summary metrics
    total_appointments = len(appointments)
    scheduled_count = sum(1 for a in appointments if a["status"] == "SCHEDULED")
    cancelled_count = sum(1 for a in appointments if a["status"] == "CANCELLED")
    today_count = sum(1 for a in appointments if a["appointment_date"] == today_str and a["status"] == "SCHEDULED")

    return render_template(
        "dashboard.html",
        doctors=doctors,
        appointments=appointments,
        today=today_str,
        metrics={
            "total": total_appointments,
            "scheduled": scheduled_count,
            "cancelled": cancelled_count,
            "today": today_count,
            "doctors_count": len(doctors)
        }
    )


# ---------------------------------------------------------------------------
# REST API Endpoints
# ---------------------------------------------------------------------------

@app.route("/api/doctors", methods=["GET"])
def api_get_doctors():
    """Return the list of all registered doctors."""
    doctors = get_all_doctors()
    return jsonify({"success": True, "doctors": doctors})


@app.route("/api/appointments", methods=["GET"])
def api_get_appointments():
    """Return appointments filtered by doctor, date, or status."""
    doctor_id = request.args.get("doctor_id", type=int)
    appointment_date = request.args.get("date")
    status = request.args.get("status")

    if status and status.upper() == "ALL":
        status = None

    appointments = get_appointments(
        doctor_id=doctor_id,
        date=appointment_date,
        status=status
    )
    return jsonify({"success": True, "appointments": appointments})


@app.route("/api/appointments", methods=["POST"])
def api_book_appointment():
    """
    Book a new appointment.
    Accepts JSON payload: { patient_name, doctor_id, appointment_date, start_time, duration_minutes, reason }
    Supports form data as well for compatibility.
    """
    if request.is_json:
        data = request.get_json()
    else:
        data = request.form

    patient_name = data.get("patient_name", "").strip()
    doctor_id = data.get("doctor_id")
    appointment_date = data.get("appointment_date", "").strip()
    start_time = data.get("start_time", "").strip()
    duration_minutes = data.get("duration_minutes", 30)
    reason = data.get("reason", "").strip()

    # Call scheduler
    result = book_appointment(
        patient_name=patient_name,
        doctor_id=doctor_id,
        appointment_date=appointment_date,
        start_time=start_time,
        duration_minutes=duration_minutes,
        reason=reason
    )

    if result["success"]:
        return jsonify(result), 201

    if result.get("error_type") == "VALIDATION_ERROR":
        return jsonify(result), 400

    # Conflict or doctor outside working hours
    return jsonify(result), 409


@app.route("/api/appointments/<int:appointment_id>/cancel", methods=["POST"])
def api_cancel_appointment(appointment_id):
    """Cancel an appointment."""
    result = cancel_appointment(appointment_id)
    if result["success"]:
        return jsonify(result), 200
    return jsonify(result), 400


@app.route("/api/check-availability", methods=["GET"])
def api_check_availability():
    """
    Real-time check whether a specific doctor and slot is available.
    Returns status and smart alternatives if unavailable.
    """
    doctor_id = request.args.get("doctor_id", type=int)
    appointment_date = request.args.get("date")
    start_time = request.args.get("time")
    duration_minutes = request.args.get("duration", default=30, type=int)

    if not (doctor_id and appointment_date and start_time):
        return jsonify({"success": False, "message": "Missing required query parameters."}), 400

    is_avail, message, conflict = check_doctor_availability(
        doctor_id=doctor_id,
        appointment_date=appointment_date,
        start_time=start_time,
        duration_minutes=duration_minutes
    )

    alternatives = []
    if not is_avail:
        alternatives = find_alternative_slots(
            doctor_id=doctor_id,
            appointment_date=appointment_date,
            duration_minutes=duration_minutes,
            requested_start_time=start_time
        )

    return jsonify({
        "success": True,
        "available": is_avail,
        "message": message,
        "conflict": conflict,
        "alternatives": alternatives
    })


@app.route("/api/stats", methods=["GET"])
def api_get_stats():
    """Return high-level hospital appointment statistics."""
    today_str = date.today().isoformat()
    appointments = get_appointments()
    doctors = get_all_doctors()

    total = len(appointments)
    scheduled = sum(1 for a in appointments if a["status"] == "SCHEDULED")
    cancelled = sum(1 for a in appointments if a["status"] == "CANCELLED")
    today = sum(1 for a in appointments if a["appointment_date"] == today_str and a["status"] == "SCHEDULED")

    return jsonify({
        "success": True,
        "stats": {
            "total": total,
            "scheduled": scheduled,
            "cancelled": cancelled,
            "today": today,
            "doctors": len(doctors)
        }
    })


# ---------------------------------------------------------------------------
# Error Handlers
# ---------------------------------------------------------------------------

@app.errorhandler(404)
def not_found(error):
    if request.path.startswith("/api/"):
        return jsonify({"success": False, "message": "API endpoint not found."}), 404
    return render_template("index.html", error="Page not found", doctors=get_all_doctors()), 404


@app.errorhandler(500)
def server_error(error):
    if request.path.startswith("/api/"):
        return jsonify({"success": False, "message": "Internal server error."}), 500
    return render_template("index.html", error="Internal server error", doctors=get_all_doctors()), 500


if __name__ == "__main__":
    # Standard Flask development server
    port = int(os.environ.get("PORT", 5000))
    print(f"Starting CareSync on http://127.0.0.1:{port}")
    app.run(host="127.0.0.1", port=port, debug=True)
