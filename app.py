
"""
app.py - CareSync Flask application.
Provides website pages, booking APIs, availability checks, and statistics.
"""

import os
from datetime import date
from flask import Flask, render_template, request, jsonify

from database import (
    init_db,
    get_all_doctors,
    get_appointments,
)
from scheduler import (
    book_appointment,
    cancel_appointment,
    check_doctor_availability,
    find_alternative_slots,
    CONSULTATION_TYPES,
)

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get(
    "SECRET_KEY",
    "caresync-hackathon-secret-key-2026"
)

# Initialize tables and sample doctors when the app starts.
with app.app_context():
    init_db()


CONSULTATION_NAMES = {
    key: value["name"]
    for key, value in CONSULTATION_TYPES.items()
}


def get_request_data():
    """Read JSON or ordinary form data safely."""
    if request.is_json:
        return request.get_json(silent=True) or {}
    return request.form


def safe_text(value):
    """Convert a supplied value to trimmed text safely."""
    return value.strip() if isinstance(value, str) else ""


# ------------------------------------------------------------------
# Website pages
# ------------------------------------------------------------------

@app.route("/")
def index():
    """Render the CareSync homepage."""
    return render_template("index.html")


@app.route("/book")
def booking():
    """Render the separate appointment booking page."""
    doctors = get_all_doctors()

    consultation_type = request.args.get("type", "in_person")
    if consultation_type not in CONSULTATION_TYPES:
        consultation_type = "in_person"

    selected = CONSULTATION_TYPES[consultation_type]

    return render_template(
        "booking.html",
        doctors=doctors,
        consultation_type=consultation_type,
        consultation_name=selected["name"],
        consultation_price=selected["price"],
        consultation_prices={
            key: value["price"]
            for key, value in CONSULTATION_TYPES.items()
        },
        today=date.today().isoformat(),
    )


@app.route("/dashboard")
def dashboard():
    """Render the appointment management dashboard."""
    doctors = get_all_doctors()
    today_str = date.today().isoformat()
    appointments = get_appointments()

    scheduled_count = sum(
        1 for appointment in appointments
        if appointment["status"] == "SCHEDULED"
    )
    cancelled_count = sum(
        1 for appointment in appointments
        if appointment["status"] == "CANCELLED"
    )
    today_count = sum(
        1 for appointment in appointments
        if appointment["appointment_date"] == today_str
        and appointment["status"] == "SCHEDULED"
    )

    metrics = {
        "total": len(appointments),
        "scheduled": scheduled_count,
        "cancelled": cancelled_count,
        "today": today_count,
        "doctors_count": len(doctors),
    }

    return render_template(
        "dashboard.html",
        doctors=doctors,
        appointments=appointments,
        today=today_str,
        metrics=metrics,
    )


# ------------------------------------------------------------------
# REST API endpoints
# ------------------------------------------------------------------

@app.route("/api/doctors", methods=["GET"])
def api_get_doctors():
    """Return all registered doctors."""
    return jsonify({
        "success": True,
        "doctors": get_all_doctors(),
    })


@app.route("/api/appointments", methods=["GET"])
def api_get_appointments():
    """Return appointments, optionally filtered."""
    doctor_id = request.args.get("doctor_id", type=int)
    appointment_date = request.args.get("date")
    status = request.args.get("status")

    if status and status.upper() == "ALL":
        status = None
    elif status:
        status = status.upper()

    appointments = get_appointments(
        doctor_id=doctor_id,
        date=appointment_date,
        status=status,
    )

    return jsonify({
        "success": True,
        "appointments": appointments,
    })


@app.route("/api/appointments", methods=["POST"])
def api_book_appointment():
    """
    Create an appointment.

    Accepted fields:
    patient_name, doctor_id, appointment_date, start_time,
    duration_minutes, reason, consultation_type, address.

    Any browser-supplied price is ignored. The scheduler chooses
    the price from its server-side consultation price list.
    """
    data = get_request_data()

    patient_name = safe_text(data.get("patient_name"))
    doctor_id = data.get("doctor_id")
    appointment_date = safe_text(data.get("appointment_date"))
    start_time = safe_text(data.get("start_time"))
    duration_minutes = data.get("duration_minutes", 30)
    reason = safe_text(data.get("reason"))
    consultation_type = safe_text(
        data.get("consultation_type", "in_person")
    )
    address = safe_text(data.get("address"))

    result = book_appointment(
        patient_name=patient_name,
        doctor_id=doctor_id,
        appointment_date=appointment_date,
        start_time=start_time,
        duration_minutes=duration_minutes,
        reason=reason,
        consultation_type=consultation_type,
        address=address,
    )

    if result["success"]:
        return jsonify(result), 201

    if result.get("error_type") == "VALIDATION_ERROR":
        return jsonify(result), 400

    return jsonify(result), 409


@app.route(
    "/api/appointments/<int:appointment_id>/cancel",
    methods=["POST"]
)
def api_cancel_appointment(appointment_id):
    """Cancel an existing appointment."""
    result = cancel_appointment(appointment_id)

    if result["success"]:
        return jsonify(result), 200

    return jsonify(result), 400


@app.route("/api/check-availability", methods=["GET"])
def api_check_availability():
    """Check a doctor's availability and suggest alternatives."""
    doctor_id = request.args.get("doctor_id", type=int)
    appointment_date = request.args.get("date")
    start_time = request.args.get("time")
    duration_minutes = request.args.get("duration", default=30, type=int)

    if not doctor_id or not appointment_date or not start_time:
        return jsonify({
            "success": False,
            "message": "Missing required query parameters.",
        }), 400

    if duration_minutes < 10 or duration_minutes > 240:
        return jsonify({
            "success": False,
            "message": "Duration must be between 10 and 240 minutes.",
        }), 400

    try:
        available, message, conflict = check_doctor_availability(
            doctor_id=doctor_id,
            appointment_date=appointment_date,
            start_time=start_time,
            duration_minutes=duration_minutes,
        )
    except (ValueError, TypeError):
        return jsonify({
            "success": False,
            "message": "Invalid date, time, doctor, or duration.",
        }), 400

    alternatives = []
    if not available:
        alternatives = find_alternative_slots(
            doctor_id=doctor_id,
            appointment_date=appointment_date,
            duration_minutes=duration_minutes,
            requested_start_time=start_time,
        )

    return jsonify({
        "success": True,
        "available": available,
        "message": message,
        "conflict": conflict,
        "alternatives": alternatives,
    })


@app.route("/api/stats", methods=["GET"])
def api_get_stats():
    """Return current appointment statistics."""
    today_str = date.today().isoformat()
    appointments = get_appointments()
    doctors = get_all_doctors()

    return jsonify({
        "success": True,
        "stats": {
            "total": len(appointments),
            "scheduled": sum(
                1 for a in appointments if a["status"] == "SCHEDULED"
            ),
            "cancelled": sum(
                1 for a in appointments if a["status"] == "CANCELLED"
            ),
            "today": sum(
                1 for a in appointments
                if a["appointment_date"] == today_str
                and a["status"] == "SCHEDULED"
            ),
            "doctors": len(doctors),
        },
    })


# ------------------------------------------------------------------
# Error handlers
# ------------------------------------------------------------------

@app.errorhandler(404)
def not_found(error):
    """Return an appropriate response for missing pages."""
    if request.path.startswith("/api/"):
        return jsonify({
            "success": False,
            "message": "API endpoint not found.",
        }), 404

    return render_template("index.html"), 404


@app.errorhandler(500)
def server_error(error):
    """Return a safe error response."""
    if request.path.startswith("/api/"):
        return jsonify({
            "success": False,
            "message": "Internal server error.",
        }), 500

    return (
        "CareSync encountered an internal server error. Please try again.",
        500,
    )


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"Starting CareSync on port {port}")
    app.run(host="0.0.0.0", port=port, debug=False)
