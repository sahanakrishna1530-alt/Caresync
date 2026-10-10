"""
scheduler.py - Core scheduling logic, overlap detection, doctor availability checks,
and smart alternative slot suggestions for CareSync.
"""

from datetime import datetime, date, timedelta
from database import (
    get_doctor_by_id,
    get_appointments,
    insert_appointment,
    update_appointment_status,
    get_appointment_by_id
)


def time_to_minutes(time_str: str) -> int:
    """Convert an 'HH:MM' 24-hour time string into minutes since midnight."""
    hours, minutes = map(int, time_str.split(":"))
    return hours * 60 + minutes


def minutes_to_time(minutes: int) -> str:
    """Convert minutes since midnight back into an 'HH:MM' string."""
    hours = (minutes // 60) % 24
    mins = minutes % 60
    return f"{hours:02d}:{mins:02d}"


def calculate_end_time(start_time: str, duration_minutes: int) -> str:
    """Calculate the end time ('HH:MM') given a start time and duration."""
    start_mins = time_to_minutes(start_time)
    end_mins = start_mins + duration_minutes
    return minutes_to_time(end_mins)


def check_overlap(start_a: str, end_a: str, start_b: str, end_b: str) -> bool:
    """
    Determine if two time intervals [start_a, end_a) and [start_b, end_b) overlap.
    Back-to-back appointments (e.g. 10:00-10:30 and 10:30-11:00) do NOT overlap.
    """
    a_start = time_to_minutes(start_a)
    a_end = time_to_minutes(end_a)
    b_start = time_to_minutes(start_b)
    b_end = time_to_minutes(end_b)

    return max(a_start, b_start) < min(a_end, b_end)


def validate_appointment_input(patient_name: str, doctor_id: int, appointment_date: str, start_time: str, duration_minutes: int):
    """
    Validate appointment input data.
    Returns (is_valid: bool, error_message: str or None).
    """
    if not patient_name or not patient_name.strip():
        return False, "Patient name is required and cannot be empty."

    if len(patient_name.strip()) < 2:
        return False, "Patient name must be at least 2 characters long."

    try:
        doctor_id = int(doctor_id)
    except (ValueError, TypeError):
        return False, "Invalid doctor ID."

    # Validate date format (YYYY-MM-DD)
    try:
        parsed_date = datetime.strptime(appointment_date, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return False, "Invalid date format. Expected YYYY-MM-DD."

    # Validate time format (HH:MM)
    try:
        datetime.strptime(start_time, "%H:%M")
    except (ValueError, TypeError):
        return False, "Invalid time format. Expected HH:MM in 24-hour format."

    # Validate duration
    try:
        duration_minutes = int(duration_minutes)
        if duration_minutes < 0 or duration_minutes > 240:
            return False, "Duration must be between 10 and 240 minutes."
    except (ValueError, TypeError):
        return False, "Duration must be a valid number of minutes."

    return True, None


def check_doctor_availability(doctor_id: int, appointment_date: str, start_time: str, duration_minutes: int, db_path=None, exclude_appointment_id=None):
    """
    Check if a doctor is available for a requested slot.
    Returns (is_available: bool, reason: str, conflicting_appointment: dict or None).
    """
    doctor = get_doctor_by_id(doctor_id, db_path=db_path)
    if not doctor:
        return False, f"Doctor with ID {doctor_id} does not exist.", None

    requested_start_mins = time_to_minutes(start_time)
    requested_end_mins = requested_start_mins + duration_minutes
    requested_end_time = minutes_to_time(requested_end_mins)

    work_start_mins = time_to_minutes(doctor["working_hours_start"])
    work_end_mins = time_to_minutes(doctor["working_hours_end"])

    # Check doctor's shift bounds
    if requested_start_mins < work_start_mins or requested_end_mins > work_end_mins:
        return False, (
            f"Requested slot ({start_time} - {requested_end_time}) falls outside "
            f"{doctor['name']}'s working hours ({doctor['working_hours_start']} - {doctor['working_hours_end']})."
        ), None

    # Fetch active scheduled appointments for the doctor on that date
    appointments = get_appointments(db_path=db_path, doctor_id=doctor_id, date=appointment_date, status="SCHEDULED")

    for appt in appointments:
        if exclude_appointment_id and appt["id"] == exclude_appointment_id:
            continue

        if check_overlap(start_time, requested_end_time, appt["start_time"], appt["end_time"]):
            conflict_msg = (
                f"{doctor['name']} is already booked from {appt['start_time']} to {appt['end_time']} "
                f"for patient {appt['patient_name']}."
            )
            return False, conflict_msg, appt

    return True, f"{doctor['name']} is available.", None


def find_alternative_slots(doctor_id: int, appointment_date: str, duration_minutes: int, requested_start_time: str = None, db_path=None, max_suggestions: int = 4):
    """
    Find alternative available time slots for the doctor on the given date.
    Prioritizes slots closest to the requested start time.
    """
    doctor = get_doctor_by_id(doctor_id, db_path=db_path)
    if not doctor:
        return []

    work_start_mins = time_to_minutes(doctor["working_hours_start"])
    work_end_mins = time_to_minutes(doctor["working_hours_end"])

    existing_appts = get_appointments(db_path=db_path, doctor_id=doctor_id, date=appointment_date, status="SCHEDULED")

    # Slot generation step (15 minutes for flexibility)
    step_minutes = 15
    candidates = []

    req_mins = time_to_minutes(requested_start_time) if requested_start_time else work_start_mins

    current_mins = work_start_mins
    while current_mins + duration_minutes <= work_end_mins:
        slot_start = minutes_to_time(current_mins)
        slot_end = minutes_to_time(current_mins + duration_minutes)

        # Check if slot overlaps with any scheduled appointment
        has_overlap = False
        for appt in existing_appts:
            if check_overlap(slot_start, slot_end, appt["start_time"], appt["end_time"]):
                has_overlap = True
                break

        # Also skip if it is exactly the slot requested that is already known to conflict
        if not has_overlap and slot_start != requested_start_time:
            time_diff = abs(current_mins - req_mins)
            candidates.append({
                "start_time": slot_start,
                "end_time": slot_end,
                "duration_minutes": duration_minutes,
                "diff": time_diff,
                "display": f"{slot_start} - {slot_end}"
            })

        current_mins += step_minutes

    # Sort candidates by proximity to requested time, then by earliest
    candidates.sort(key=lambda s: (s["diff"], s["start_time"]))

    # Return top N suggestions without the internal 'diff' key
    return [
        {
            "start_time": c["start_time"],
            "end_time": c["end_time"],
            "duration_minutes": c["duration_minutes"],
            "display": c["display"]
        }
        for c in candidates[:max_suggestions]
    ]


def book_appointment(patient_name: str, doctor_id: int, appointment_date: str, start_time: str, duration_minutes: int, reason: str = "", db_path=None):
    """
    Validate input, verify availability, prevent conflicts, and persist the appointment.
    Returns a dict with 'success', 'message', and either 'appointment' or 'alternatives'.
    """
    # 1. Validate inputs
    is_valid, validation_error = validate_appointment_input(
        patient_name, doctor_id, appointment_date, start_time, duration_minutes
    )
    if not is_valid:
        return {
            "success": False,
            "error_type": "VALIDATION_ERROR",
            "message": validation_error,
            "alternatives": []
        }

    # Normalize fields
    patient_name = patient_name.strip()
    doctor_id = int(doctor_id)
    duration_minutes = int(duration_minutes)
    reason = (reason or "").strip()

    # 2. Check doctor availability
    is_available, message, conflict = check_doctor_availability(
        doctor_id=doctor_id,
        appointment_date=appointment_date,
        start_time=start_time,
        duration_minutes=duration_minutes,
        db_path=db_path
    )

    if not is_available:
        # Search for alternative suggestions on the same date
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

    # 3. Calculate end time and insert
    end_time = calculate_end_time(start_time, duration_minutes)
    new_id = insert_appointment(
        patient_name=patient_name,
        doctor_id=doctor_id,
        appointment_date=appointment_date,
        start_time=start_time,
        end_time=end_time,
        duration_minutes=duration_minutes,
        reason=reason,
        db_path=db_path
    )

    appointment = get_appointment_by_id(new_id, db_path=db_path)
    return {
        "success": True,
        "message": f"Appointment booked successfully with {appointment['doctor_name']} on {appointment_date} at {start_time}.",
        "appointment": appointment
    }


def cancel_appointment(appointment_id: int, db_path=None):
    """
    Cancel an existing appointment by ID.
    Returns a dict with 'success' and 'message'.
    """
    try:
        appointment_id = int(appointment_id)
    except (ValueError, TypeError):
        return {"success": False, "message": "Invalid appointment ID."}

    appt = get_appointment_by_id(appointment_id, db_path=db_path)
    if not appt:
        return {"success": False, "message": f"Appointment #{appointment_id} not found."}

    if appt["status"] == "CANCELLED":
        return {"success": False, "message": f"Appointment #{appointment_id} is already cancelled."}

    success = update_appointment_status(appointment_id, "CANCELLED", db_path=db_path)
    if success:
        return {
            "success": True,
            "message": f"Appointment #{appointment_id} for {appt['patient_name']} has been cancelled."
        }
    return {"success": False, "message": "Failed to update appointment status."}
