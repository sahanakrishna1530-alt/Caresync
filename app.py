
"""
CareSync - Smart Hospital Appointment Scheduler
Flask application routes and REST API.
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
    CONSULTATION_TYPES,
    book_appointment,
    cancel_appointment,
    reschedule_appointment,
    check_doctor_availability,
    find_alternative_slots,
)


app = Flask(__name__)

app.config["SECRET_KEY"] = os.environ.get(
    "SECRET_KEY",
    "caresync-hackathon-secret-key-2026",
)

with app.app_context():
    init_db()


# -------------------- CONSULTATION SETTINGS --------------------

CONSULTATION_NAMES = {
    "video": "Video Visit",
    "phone": "Phone Call",
    "in_person": "In Person",
    "home": "Home Visit",
}

CONSULTATION_PRICES = {
    key: value["price"]
    for key, value in CONSULTATION_TYPES.items()
}


# -------------------- HOME PAGE --------------------

@app.route("/")
def index():
    doctors = get_all_doctors()
    today_str = date.today().isoformat()

    recent_appointments = get_appointments(
        date=today_str,
        status="SCHEDULED",
    )

    return render_template(
        "index.html",
        doctors=doctors,
        today=today_str,
        recent_appointments=recent_appointments,
    )


# -------------------- BOOKING PAGE --------------------

@app.route("/book")
def booking():
    doctors = get_all_doctors()

    consultation_type = request.args.get(
        "type",
        "in_person",
    )

    if consultation_type not in CONSULTATION_NAMES:
        consultation_type = "in_person"

    return render_template(
        "booking.html",
        doctors=doctors,
        consultation_type=consultation_type,
        consultation_name=CONSULTATION_NAMES[consultation_type],
        consultation_price=CONSULTATION_PRICES[consultation_type],
        consultation_prices=CONSULTATION_PRICES,
        today=date.today().isoformat(),
    )


# -------------------- HOSPITAL DASHBOARD --------------------

@app.route("/dashboard")
def dashboard():
    doctors = get_all_doctors()
    today_str = date.today().isoformat()
    appointments = get_appointments()

    metrics = {
        "total": len(appointments),
        "scheduled": sum(
            1 for appointment in appointments
            if appointment["status"] == "SCHEDULED"
        ),
        "cancelled": sum(
            1 for appointment in appointments
            if appointment["status"] == "CANCELLED"
        ),
        "today": sum(
            1 for appointment in appointments
            if appointment["appointment_date"] == today_str
            and appointment["status"] == "SCHEDULED"
        ),
        "doctors_count": len(doctors),
    }

    return render_template(
        "dashboard.html",
        doctors=doctors,
        appointments=appointments,
        today=today_str,
        metrics=metrics,
    )


# -------------------- DOCTOR API --------------------

@app.route("/api/doctors", methods=["GET"])
def api_get_doctors():
    return jsonify({
        "success": True,
        "doctors": get_all_doctors(),
    })


# -------------------- APPOINTMENT LIST API --------------------

@app.route("/api/appointments", methods=["GET"])
def api_get_appointments():
    doctor_id = request.args.get("doctor_id", type=int)
    appointment_date = request.args.get("date")
    status = request.args.get("status")

    if status and status.upper() == "ALL":
        status = None

    appointments = get_appointments(
        doctor_id=doctor_id,
        date=appointment_date,
        status=status,
    )

    return jsonify({
        "success": True,
        "appointments": appointments,
    })


# -------------------- BOOK APPOINTMENT API --------------------

@app.route("/api/appointments", methods=["POST"])
def api_book_appointment():
    data = (
        request.get_json(silent=True)
        if request.is_json
        else request.form
    )

    if data is None:
        return jsonify({
            "success": False,
            "message": "Invalid request data.",
        }), 400

    patient_name = data.get("patient_name", "").strip()
    doctor_id = data.get("doctor_id")
    appointment_date = data.get("appointment_date", "").strip()
    start_time = data.get("start_time", "").strip()
    duration_minutes = data.get("duration_minutes", 30)
    reason = data.get("reason", "").strip()

    consultation_type = data.get(
        "consultation_type",
        "in_person",
    )
    address = data.get("address", "").strip()

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

    if result.get("error_type") == "DATABASE_ERROR":
        return jsonify(result), 500

    return jsonify(result), 409


# -------------------- CANCEL APPOINTMENT API --------------------

@app.route(
    "/api/appointments/<int:appointment_id>/cancel",
    methods=["POST"],
)
def api_cancel_appointment(appointment_id):
    result = cancel_appointment(appointment_id)

    if result["success"]:
        return jsonify(result), 200

    status_code = (
        404
        if result.get("message") == "Appointment not found."
        else 400
    )

    return jsonify(result), status_code


# -------------------- RESCHEDULE APPOINTMENT API --------------------

@app.route(
    "/api/appointments/<int:appointment_id>/reschedule",
    methods=["POST"],
)
def api_reschedule_appointment(appointment_id):
    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({
            "success": False,
            "error_type": "VALIDATION_ERROR",
            "message": "Please provide appointment details as JSON.",
        }), 400

    appointment_date = data.get("appointment_date")
    start_time = data.get("start_time")
    duration_minutes = data.get("duration_minutes", 30)

    if not isinstance(appointment_date, str) or not appointment_date.strip():
        return jsonify({
            "success": False,
            "error_type": "VALIDATION_ERROR",
            "message": "Appointment date is required.",
        }), 400

    if not isinstance(start_time, str) or not start_time.strip():
        return jsonify({
            "success": False,
            "error_type": "VALIDATION_ERROR",
            "message": "Appointment start time is required.",
        }), 400

    result = reschedule_appointment(
        appointment_id=appointment_id,
        appointment_date=appointment_date.strip(),
        start_time=start_time.strip(),
        duration_minutes=duration_minutes,
    )

    if result["success"]:
        return jsonify(result), 200

    error_type = result.get("error_type")

    if error_type == "NOT_FOUND":
        status_code = 404
    elif error_type in ("VALIDATION_ERROR", "INVALID_STATUS"):
        status_code = 400
    elif error_type in ("CONFLICT", "UNAVAILABLE"):
        status_code = 409
    else:
        status_code = 500

    return jsonify(result), status_code


# -------------------- AVAILABILITY API --------------------

@app.route("/api/check-availability", methods=["GET"])
def api_check_availability():
    doctor_id = request.args.get("doctor_id", type=int)
    appointment_date = request.args.get("date")
    start_time = request.args.get("time")
    duration_minutes = request.args.get(
        "duration",
        default=30,
        type=int,
    )

    if not (doctor_id and appointment_date and start_time):
        return jsonify({
            "success": False,
            "message": "Missing required query parameters.",
        }), 400

    is_available, message, conflict = check_doctor_availability(
        doctor_id=doctor_id,
        appointment_date=appointment_date,
        start_time=start_time,
        duration_minutes=duration_minutes,
    )

    alternatives = []

    if not is_available:
        alternatives = find_alternative_slots(
            doctor_id=doctor_id,
            appointment_date=appointment_date,
            duration_minutes=duration_minutes,
            requested_start_time=start_time,
        )

    return jsonify({
        "success": True,
        "available": is_available,
        "message": message,
        "conflict": conflict,
        "alternatives": alternatives,
    })


# -------------------- STATISTICS API --------------------

@app.route("/api/stats", methods=["GET"])
def api_get_stats():
    today_str = date.today().isoformat()
    appointments = get_appointments()
    doctors = get_all_doctors()

    return jsonify({
        "success": True,
        "stats": {
            "total": len(appointments),
            "scheduled": sum(
                1 for appointment in appointments
                if appointment["status"] == "SCHEDULED"
            ),
            "cancelled": sum(
                1 for appointment in appointments
                if appointment["status"] == "CANCELLED"
            ),
            "today": sum(
                1 for appointment in appointments
                if appointment["appointment_date"] == today_str
                and appointment["status"] == "SCHEDULED"
            ),
            "doctors": len(doctors),
        },
    })


# -------------------- ERROR HANDLERS --------------------

@app.errorhandler(404)
def not_found(error):
    if request.path.startswith("/api/"):
        return jsonify({
            "success": False,
            "message": "API endpoint not found.",
        }), 404

    return render_template(
        "index.html",
        error="Page not found",
        doctors=get_all_doctors(),
        today=date.today().isoformat(),
        recent_appointments=[],
    ), 404


@app.errorhandler(500)
def server_error(error):
    if request.path.startswith("/api/"):
        return jsonify({
            "success": False,
            "message": "Internal server error.",
        }), 500

    return "CareSync encountered an internal error.", 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(
        host="127.0.0.1",
        port=port,
        debug=True,
    )
