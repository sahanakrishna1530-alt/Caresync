
"""
scheduler.py - CareSync scheduling, validation, availability,
conflict detection, alternative slots, and cancellations.
"""

from datetime import datetime, date
from database import (
    get_doctor_by_id,
    get_appointments,
    insert_appointment,
    update_appointment_status,
    get_appointment_by_id
)


# Prices are controlled by the server, never by browser input.
CONSULTATION_TYPES = {
    "video": {"name": "Video Visit", "price": 299},
    "phone": {"name": "Phone Call", "price": 199},
    "in_person": {"name": "In Person", "price": 499},
    "home": {"name": "Home Visit", "price": 699}
}


def time_to_minutes(time_str: str) -> int:
    """Convert HH:MM into minutes since midnight."""
    hours, minutes = map(int, time_str.split(":"))
    return hours * 60 + minutes


def minutes_to_time(minutes: int) -> str:
    """Convert minutes since midnight into HH:MM."""
    hours = (minutes // 60) % 24
    mins = minutes % 60
    return f"{hours:02d}:{mins:02d}"


def calculate_end_time(start_time: str, duration_minutes: int) -> str:
    """Calculate appointment end time."""
    return minutes_to_time(
        time_to_minutes(start_time) + duration_minutes
    )


def check_overlap(start_a, end_a, start_b, end_b) -> bool:
    """Return True when two appointment intervals overlap."""
    a_start = time_to_minutes(start_a)
    a_end = time_to_minutes(end_a)
    b_start = time_to_minutes(start_b)
    b_end = time_to_minutes(end_b)
    return max(a_start, b_start) < min(a_end, b_end)


def validate_appointment_input(
    patient_name,
    doctor_id,
    appointment_date,
    start_time,
    duration_minutes
):
    """Validate the core appointment fields."""
    if not isinstance(patient_name, str) or not patient_name.strip():
        return False, "Patient name is required and cannot be empty."

    if len(patient_name.strip()) < 2:
        return False, "Patient name must be at least 2 characters long."

    try:
        doctor_id = int(doctor_id)
    except (ValueError, TypeError):
        return False, "Invalid doctor ID."

    try:
        parsed_date = datetime.strptime(
            appointment_date, "%Y-%m-%d"
        ).date()
    except (ValueError, TypeError):
        return False, "Invalid date format. Expected YYYY-MM-DD."

    if parsed_date < date.today():
        return False, "Appointment date cannot be in the past."

    try:
        datetime.strptime(start_time, "%H:%M")
    except (ValueError, TypeError):
        return False, "Invalid time format. Expected HH:MM."

    try:
        duration_minutes = int(duration_minutes)
    except (ValueError, TypeError):
        return False, "Duration must be a valid number of minutes."

    if duration_minutes < 10 or duration_minutes > 240:
        return False, "Duration must be between 10 and 240 minutes."

    if duration_minutes % 5 != 0:
        return False, "Duration must be in 5-minute increments."

    return True, None


def check_doctor_availability(
    doctor_id,
    appointment_date,
    start_time,
    duration_minutes,
    db_path=None,
    exclude_appointment_id=None
):
    """Check working hours and overlapping scheduled appointments."""
    doctor = get_doctor_by_id(doctor_id, db_path=db_path)

    if not doctor:
        return False, f"Doctor with ID {doctor_id} does not exist.", None

    requested_start = time_to_minutes(start_time)
    requested_end = requested_start + duration_minutes
    requested_end_time = minutes_to_time(requested_end)

    work_start = time_to_minutes(doctor["working_hours_start"])
    work_end = time_to_minutes(doctor["working_hours_end"])

    # Do not allow an appointment to continue into the next day.
    if requested_end > 24 * 60:
        return False, "Appointment cannot extend past midnight.", None

    if requested_start < work_start or requested_end > work_end:
        return False, (
            f"Requested slot ({start_time} - {requested_end_time}) falls "
            f"outside {doctor['name']}'s working hours "
            f"({doctor['working_hours_start']} - "
            f"{doctor['working_hours_end']})."
        ), None

    appointments = get_appointments(
        db_path=db_path,
        doctor_id=doctor_id,
        date=appointment_date,
        status="SCHEDULED"
    )

    for appt in appointments:
        if (
            exclude_appointment_id is not None
            and int(appt["id"]) == int(exclude_appointment_id)
        ):
            continue

        if check_overlap(
            start_time,
            requested_end_time,
            appt["start_time"],
            appt["end_time"]
        ):
            message = (
                f"{doctor['name']} is already booked from "
                f"{appt['start_time']} to {appt['end_time']} "
                f"for patient {appt['patient_name']}."
            )
            return False, message, appt

    return True, f"{doctor['name']} is available.", None


def find_alternative_slots(
    doctor_id,
    appointment_date,
    duration_minutes,
    requested_start_time=None,
    db_path=None,
    max_suggestions=4
):
    """Find nearby available time slots."""
    doctor = get_doctor_by_id(doctor_id, db_path=db_path)
    if not doctor:
        return []

    work_start = time_to_minutes(doctor["working_hours_start"])
    work_end = time_to_minutes(doctor["working_hours_end"])

    appointments = get_appointments(
        db_path=db_path,
        doctor_id=doctor_id,
        date=appointment_date,
        status="SCHEDULED"
    )

    requested_minutes = (
        time_to_minutes(requested_start_time)
        if requested_start_time else work_start
    )

    candidates = []
    current = work_start

    while current + duration_minutes <= work_end:
        start = minutes_to_time(current)
        end = minutes_to_time(current + duration_minutes)

        overlaps = any(
            check_overlap(start, end, appt["start_time"], appt["end_time"])
            for appt in appointments
        )

        if not overlaps and start != requested_start_time:
            candidates.append({
                "start_time": start,
                "end_time": end,
                "duration_minutes": duration_minutes,
                "diff": abs(current - requested_minutes),
                "display": f"{start} - {end}"
            })

        current += 15

    candidates.sort(key=lambda slot: (slot["diff"], slot["start_time"]))

    return [
        {key: value for key, value in slot.items() if key != "diff"}
        for slot in candidates[:max_suggestions]
    ]


def book_appointment(
    patient_name,
    doctor_id,
    appointment_date,
    start_time,
    duration_minutes,
    reason="",
    db_path=None,
    consultation_type="in_person",
    address=""
):
    """
    Validate and book an appointment.
    Prices are calculated from CONSULTATION_TYPES, not client input.
    """
    valid, error = validate_appointment_input(
        patient_name,
        doctor_id,
        appointment_date,
        start_time,
        duration_minutes
    )

    if not valid:
        return {
            "success": False,
            "error_type": "VALIDATION_ERROR",
            "message": error,
            "alternatives": []
        }

    if not isinstance(consultation_type, str):
        consultation_type = ""

    consultation_type = consultation_type.strip().lower()

    if consultation_type not in CONSULTATION_TYPES:
        return {
            "success": False,
            "error_type": "VALIDATION_ERROR",
            "message": "Please select a valid consultation type.",
            "alternatives": []
        }

    address = address.strip() if isinstance(address, str) else ""

    if consultation_type == "home" and not address:
        return {
            "success": False,
            "error_type": "VALIDATION_ERROR",
            "message": "An address is required for a Home Visit.",
            "alternatives": []
        }

    # Ignore any price supplied by the browser.
    price = CONSULTATION_TYPES[consultation_type]["price"]

    patient_name = patient_name.strip()
    doctor_id = int(doctor_id)
    duration_minutes = int(duration_minutes)
    reason = reason.strip() if isinstance(reason, str) else ""

    available, message, conflict = check_doctor_availability(
        doctor_id=doctor_id,
        appointment_date=appointment_date,
        start_time=start_time,
        duration_minutes=duration_minutes,
        db_path=db_path
    )

    if not available:
        alternatives = find_alternative_slots(
            doctor_id=doctor_id,
            appointment_date=appointment_date,
            duration_minutes=duration_minutes,
            requested_start_time=start_time,
            db_path=db_path
        )

        return {
            "success": False,
            "error_type": "CONFLICT" if conflict else "UNAVAILABLE",
            "message": message,
            "conflict": conflict,
            "alternatives": alternatives
        }

    end_time = calculate_end_time(start_time, duration_minutes)

    new_id = insert_appointment(
        patient_name=patient_name,
        doctor_id=doctor_id,
        appointment_date=appointment_date,
        start_time=start_time,
        end_time=end_time,
        duration_minutes=duration_minutes,
        reason=reason,
        db_path=db_path,
        consultation_type=consultation_type,
        price=price,
        address=address if consultation_type == "home" else ""
    )

    appointment = get_appointment_by_id(new_id, db_path=db_path)

    return {
        "success": True,
        "message": (
            f"Appointment booked successfully with "
            f"{appointment['doctor_name']} on {appointment_date} "
            f"at {start_time}."
        ),
        "appointment": appointment
    }


def cancel_appointment(appointment_id, db_path=None):
    """Cancel an existing appointment by ID."""
    try:
        appointment_id = int(appointment_id)
    except (ValueError, TypeError):
        return {"success": False, "message": "Invalid appointment ID."}

    appointment = get_appointment_by_id(
        appointment_id, db_path=db_path
    )

    if not appointment:
        return {
            "success": False,
            "message": f"Appointment #{appointment_id} not found."
        }

    if appointment["status"] == "CANCELLED":
        return {
            "success": False,
            "message": f"Appointment #{appointment_id} is already cancelled."
        }

    updated = update_appointment_status(
        appointment_id, "CANCELLED", db_path=db_path
    )

    if updated:
        return {
            "success": True,
            "message": (
                f"Appointment #{appointment_id} for "
                f"{appointment['patient_name']} has been cancelled."
            )
        }

    return {
        "success": False,
        "message": "Failed to update appointment status."
    }
