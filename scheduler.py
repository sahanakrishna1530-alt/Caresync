
"""
scheduler.py - CareSync scheduling, validation, availability,
conflict detection, alternative slots, cancellations, and rescheduling.
"""

from datetime import datetime, date

from database import (
    get_doctor_by_id,
    get_appointments,
    insert_appointment,
    update_appointment_status,
    get_appointment_by_id,
    update_appointment_schedule,
)


CONSULTATION_TYPES = {
    "video": {"name": "Video Visit", "price": 299},
    "phone": {"name": "Phone Call", "price": 199},
    "in_person": {"name": "In Person", "price": 499},
    "home": {"name": "Home Visit", "price": 699},
}


def time_to_minutes(time_str: str) -> int:
    hours, minutes = map(int, time_str.split(":"))
    return hours * 60 + minutes


def minutes_to_time(minutes: int) -> str:
    hours = (minutes // 60) % 24
    mins = minutes % 60
    return f"{hours:02d}:{mins:02d}"


def calculate_end_time(start_time: str, duration_minutes: int) -> str:
    return minutes_to_time(
        time_to_minutes(start_time) + duration_minutes
    )


def check_overlap(start_a, end_a, start_b, end_b) -> bool:
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
    duration_minutes,
):
    if not isinstance(patient_name, str) or not patient_name.strip():
        return False, "Patient name is required."

    if len(patient_name.strip()) < 2:
        return False, "Patient name must contain at least 2 characters."

    try:
        doctor_id = int(doctor_id)
        if doctor_id <= 0:
            raise ValueError
    except (TypeError, ValueError):
        return False, "Please select a valid doctor."

    try:
        requested_date = datetime.strptime(
            str(appointment_date), "%Y-%m-%d"
        ).date()
    except (TypeError, ValueError):
        return False, "Please enter a valid appointment date."

    if requested_date < date.today():
        return False, "Appointment date cannot be in the past."

    try:
        datetime.strptime(str(start_time), "%H:%M")
    except (TypeError, ValueError):
        return False, "Please enter a valid start time in HH:MM format."

    try:
        duration = int(duration_minutes)
    except (TypeError, ValueError):
        return False, "Appointment duration must be a number."

    if duration < 10 or duration > 240:
        return False, "Duration must be between 10 and 240 minutes."

    if duration % 5 != 0:
        return False, "Duration must be in multiples of 5 minutes."

    return True, None


def check_doctor_availability(
    doctor_id,
    appointment_date,
    start_time,
    duration_minutes,
    db_path=None,
    exclude_appointment_id=None,
):
    doctor = get_doctor_by_id(doctor_id, db_path)

    if not doctor:
        return False, "Doctor not found.", None

    try:
        start_minutes = time_to_minutes(start_time)
        duration = int(duration_minutes)
    except (TypeError, ValueError):
        return False, "Invalid appointment time or duration.", None

    end_minutes = start_minutes + duration

    if start_minutes < 0 or start_minutes >= 24 * 60:
        return False, "Invalid appointment start time.", None

    if end_minutes > 24 * 60:
        return False, "Appointment cannot extend past midnight.", None

    end_time = minutes_to_time(end_minutes)

    try:
        working_start = time_to_minutes(doctor["working_hours_start"])
        working_end = time_to_minutes(doctor["working_hours_end"])
    except (KeyError, TypeError, ValueError):
        return False, "Doctor working hours are not configured correctly.", None

    if start_minutes < working_start or end_minutes > working_end:
        return (
            False,
            f"Please choose a time within the doctor's working hours "
            f"({doctor['working_hours_start']}–{doctor['working_hours_end']}).",
            None,
        )

    appointments = get_appointments(
        db_path=db_path,
        doctor_id=doctor_id,
        date=appointment_date,
        status="SCHEDULED",
    )

    for appointment in appointments:
        if (
            exclude_appointment_id is not None
            and int(appointment["id"]) == int(exclude_appointment_id)
        ):
            continue

        if check_overlap(
            start_time,
            end_time,
            appointment["start_time"],
            appointment["end_time"],
        ):
            return (
                False,
                "This time slot conflicts with another scheduled appointment.",
                appointment,
            )

    return True, f"{doctor['name']} is available.", None


def find_alternative_slots(
    doctor_id,
    appointment_date,
    requested_start_time,
    duration_minutes,
    db_path=None,
    limit=4,
    exclude_appointment_id=None,
):
    doctor = get_doctor_by_id(doctor_id, db_path)

    if not doctor:
        return []

    try:
        requested_minutes = time_to_minutes(requested_start_time)
        duration = int(duration_minutes)
        working_start = time_to_minutes(doctor["working_hours_start"])
        working_end = time_to_minutes(doctor["working_hours_end"])
    except (KeyError, TypeError, ValueError):
        return []

    appointments = get_appointments(
        db_path=db_path,
        doctor_id=doctor_id,
        date=appointment_date,
        status="SCHEDULED",
    )

    alternatives = []
    candidate = working_start

    while candidate + duration <= working_end:
        candidate_time = minutes_to_time(candidate)
        candidate_end = minutes_to_time(candidate + duration)

        if candidate != requested_minutes:
            available = True

            for appointment in appointments:
                if (
                    exclude_appointment_id is not None
                    and int(appointment["id"]) == int(exclude_appointment_id)
                ):
                    continue

                if check_overlap(
                    candidate_time,
                    candidate_end,
                    appointment["start_time"],
                    appointment["end_time"],
                ):
                    available = False
                    break

            if available:
                alternatives.append({
                    "start_time": candidate_time,
                    "end_time": candidate_end,
                    "appointment_date": str(appointment_date),
                })

        candidate += 15

    alternatives.sort(
        key=lambda slot: abs(
            time_to_minutes(slot["start_time"]) - requested_minutes
        )
    )

    return alternatives[:limit]


def book_appointment(
    patient_name,
    doctor_id,
    appointment_date,
    start_time,
    duration_minutes,
    reason="",
    db_path=None,
    consultation_type="in_person",
    address="",
):
    valid, error = validate_appointment_input(
        patient_name,
        doctor_id,
        appointment_date,
        start_time,
        duration_minutes,
    )

    if not valid:
        return {
            "success": False,
            "error_type": "VALIDATION_ERROR",
            "message": error,
        }

    try:
        doctor_id = int(doctor_id)
        duration_minutes = int(duration_minutes)
    except (TypeError, ValueError):
        return {
            "success": False,
            "error_type": "VALIDATION_ERROR",
            "message": "Invalid doctor or appointment duration.",
        }

    if consultation_type not in CONSULTATION_TYPES:
        return {
            "success": False,
            "error_type": "VALIDATION_ERROR",
            "message": "Please select a valid consultation type.",
        }

    if consultation_type == "home" and not str(address or "").strip():
        return {
            "success": False,
            "error_type": "VALIDATION_ERROR",
            "message": "An address is required for a home visit.",
        }

    available, message, conflict = check_doctor_availability(
        doctor_id,
        appointment_date,
        start_time,
        duration_minutes,
        db_path=db_path,
    )

    if not available:
        alternatives = find_alternative_slots(
            doctor_id,
            appointment_date,
            start_time,
            duration_minutes,
            db_path=db_path,
        )

        return {
            "success": False,
            "error_type": "CONFLICT" if conflict else "UNAVAILABLE",
            "message": message,
            "conflict": conflict,
            "alternatives": alternatives,
        }

    end_time = calculate_end_time(start_time, duration_minutes)
    price = CONSULTATION_TYPES[consultation_type]["price"]

    try:
        appointment_id = insert_appointment(
            patient_name=patient_name.strip(),
            doctor_id=doctor_id,
            appointment_date=str(appointment_date),
            start_time=start_time,
            end_time=end_time,
            duration_minutes=duration_minutes,
            reason=reason,
            db_path=db_path,
            consultation_type=consultation_type,
            price=price,
            address=address or "",
        )
    except Exception:
        return {
            "success": False,
            "error_type": "DATABASE_ERROR",
            "message": "Unable to save the appointment. Please try again.",
        }

    appointment = get_appointment_by_id(appointment_id, db_path)

    return {
        "success": True,
        "message": "Appointment booked successfully.",
        "appointment": appointment,
    }


def cancel_appointment(appointment_id, db_path=None):
    try:
        appointment_id = int(appointment_id)
    except (TypeError, ValueError):
        return {
            "success": False,
            "message": "Invalid appointment ID.",
        }

    appointment = get_appointment_by_id(appointment_id, db_path)

    if not appointment:
        return {
            "success": False,
            "message": "Appointment not found.",
        }

    if appointment["status"] == "CANCELLED":
        return {
            "success": False,
            "message": "This appointment is already cancelled.",
        }

    if appointment["status"] != "SCHEDULED":
        return {
            "success": False,
            "message": "Only scheduled appointments can be cancelled.",
        }

    success = update_appointment_status(
        appointment_id,
        "CANCELLED",
        db_path,
    )

    if not success:
        return {
            "success": False,
            "message": "Unable to cancel the appointment. Please try again.",
        }

    return {
        "success": True,
        "message": "Appointment cancelled successfully.",
    }


def reschedule_appointment(
    appointment_id,
    appointment_date,
    start_time,
    duration_minutes,
    db_path=None,
):
    """Reschedule an existing appointment without creating a duplicate."""

    try:
        appointment_id = int(appointment_id)
    except (TypeError, ValueError):
        return {
            "success": False,
            "error_type": "VALIDATION_ERROR",
            "message": "Invalid appointment ID.",
        }

    appointment = get_appointment_by_id(appointment_id, db_path)

    if not appointment:
        return {
            "success": False,
            "error_type": "NOT_FOUND",
            "message": "Appointment not found.",
        }

    if appointment["status"] != "SCHEDULED":
        return {
            "success": False,
            "error_type": "INVALID_STATUS",
            "message": "Only scheduled appointments can be rescheduled.",
        }

    valid, error = validate_appointment_input(
        appointment["patient_name"],
        appointment["doctor_id"],
        appointment_date,
        start_time,
        duration_minutes,
    )

    if not valid:
        return {
            "success": False,
            "error_type": "VALIDATION_ERROR",
            "message": error,
        }

    try:
        duration_minutes = int(duration_minutes)
    except (TypeError, ValueError):
        return {
            "success": False,
            "error_type": "VALIDATION_ERROR",
            "message": "Invalid appointment duration.",
        }

    available, message, conflict = check_doctor_availability(
        doctor_id=appointment["doctor_id"],
        appointment_date=str(appointment_date),
        start_time=start_time,
        duration_minutes=duration_minutes,
        db_path=db_path,
        exclude_appointment_id=appointment_id,
    )

    if not available:
        alternatives = find_alternative_slots(
            doctor_id=appointment["doctor_id"],
            appointment_date=str(appointment_date),
            requested_start_time=start_time,
            duration_minutes=duration_minutes,
            db_path=db_path,
            exclude_appointment_id=appointment_id,
        )

        return {
            "success": False,
            "error_type": "CONFLICT" if conflict else "UNAVAILABLE",
            "message": message,
            "conflict": conflict,
            "alternatives": alternatives,
        }

    end_time = calculate_end_time(start_time, duration_minutes)

    updated, update_message = update_appointment_schedule(
        appointment_id=appointment_id,
        appointment_date=str(appointment_date),
        start_time=start_time,
        end_time=end_time,
        duration_minutes=duration_minutes,
        db_path=db_path,
    )

    if not updated:
        return {
            "success": False,
            "error_type": "UPDATE_FAILED",
            "message": update_message,
        }

    updated_appointment = get_appointment_by_id(
        appointment_id,
        db_path,
    )

    return {
        "success": True,
        "message": "Appointment rescheduled successfully.",
        "appointment": updated_appointment,
    }
