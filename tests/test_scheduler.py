"""
test_scheduler.py - Automated tests for CareSync scheduling logic, conflict prevention,
working hours verification, alternative slot suggestions, and cancellations.
"""

import os
import tempfile
import unittest
from datetime import date, timedelta

from database import init_db, get_all_doctors, get_appointments, get_appointment_by_id
from scheduler import (
    time_to_minutes,
    minutes_to_time,
    calculate_end_time,
    check_overlap,
    validate_appointment_input,
    check_doctor_availability,
    find_alternative_slots,
    book_appointment,
    cancel_appointment
)


class TestCareSyncScheduler(unittest.TestCase):
    def setUp(self):
        """Set up an isolated temporary database for each test case."""
        self.db_fd, self.db_path = tempfile.mkstemp(suffix=".db")
        os.close(self.db_fd)
        init_db(self.db_path)

        # Retrieve seeded doctors
        doctors = get_all_doctors(self.db_path)
        self.assertTrue(len(doctors) >= 2, "Seeded doctors should exist in the database.")
        self.doctor1 = doctors[0]  # Dr. David Kim or Dr. Elena Rostova or Dr. Sarah Jenkins
        self.doctor2 = doctors[1]
        self.test_date = "2026-10-15"

    def tearDown(self):
        """Clean up temporary test database."""
        if os.path.exists(self.db_path):
            try:
                os.remove(self.db_path)
            except OSError:
                pass

    def test_time_conversions_and_calculations(self):
        """Test time-to-minute conversions and end time calculations."""
        self.assertEqual(time_to_minutes("09:00"), 540)
        self.assertEqual(time_to_minutes("14:30"), 870)
        self.assertEqual(minutes_to_time(540), "09:00")
        self.assertEqual(minutes_to_time(870), "14:30")
        self.assertEqual(calculate_end_time("09:15", 45), "10:00")
        self.assertEqual(calculate_end_time("11:30", 30), "12:00")

    def test_overlap_detection(self):
        """Test the logic for interval overlaps."""
        # Exact match
        self.assertTrue(check_overlap("10:00", "10:30", "10:00", "10:30"))
        # Partial overlap: B starts during A
        self.assertTrue(check_overlap("10:00", "10:30", "10:15", "10:45"))
        # Partial overlap: B starts before A and ends inside A
        self.assertTrue(check_overlap("10:15", "10:45", "10:00", "10:30"))
        # Enclosure: B is inside A
        self.assertTrue(check_overlap("10:00", "11:00", "10:15", "10:45"))
        # Back-to-back: should NOT overlap
        self.assertFalse(check_overlap("10:00", "10:30", "10:30", "11:00"))
        self.assertFalse(check_overlap("10:30", "11:00", "10:00", "10:30"))
        # Completely disjoint
        self.assertFalse(check_overlap("09:00", "09:30", "14:00", "14:30"))

    def test_input_validation(self):
        """Test backend validation of inputs."""
        # Empty name
        valid, msg = validate_appointment_input("", self.doctor1["id"], "2026-10-15", "10:00", 30)
        self.assertFalse(valid)
        self.assertIn("Patient name", msg)

        # Invalid date
        valid, msg = validate_appointment_input("Alice", self.doctor1["id"], "not-a-date", "10:00", 30)
        self.assertFalse(valid)
        self.assertIn("date format", msg)

        # Invalid time
        valid, msg = validate_appointment_input("Alice", self.doctor1["id"], "2026-10-15", "25:70", 30)
        self.assertFalse(valid)
        self.assertIn("time format", msg)

        # Invalid duration
        valid, msg = validate_appointment_input("Alice", self.doctor1["id"], "2026-10-15", "10:00", 0)
        self.assertFalse(valid)
        self.assertIn("Duration", msg)

        # Valid input
        valid, msg = validate_appointment_input("Alice Walker", self.doctor1["id"], "2026-10-15", "10:00", 30)
        self.assertTrue(valid)
        self.assertIsNone(msg)

    def test_book_valid_appointment(self):
        """Test successfully booking an appointment within doctor's working hours."""
        res = book_appointment(
            patient_name="John Doe",
            doctor_id=self.doctor1["id"],
            appointment_date=self.test_date,
            start_time="10:00",
            duration_minutes=30,
            reason="Routine health checkup",
            db_path=self.db_path
        )
        self.assertTrue(res["success"])
        self.assertIsNotNone(res["appointment"])
        self.assertEqual(res["appointment"]["patient_name"], "John Doe")
        self.assertEqual(res["appointment"]["start_time"], "10:00")
        self.assertEqual(res["appointment"]["end_time"], "10:30")
        self.assertEqual(res["appointment"]["status"], "SCHEDULED")

    def test_prevent_outside_working_hours(self):
        """Test that booking outside a doctor's shift is rejected."""
        # Too early
        res_early = book_appointment(
            patient_name="Early Bird",
            doctor_id=self.doctor1["id"],
            appointment_date=self.test_date,
            start_time="06:00",
            duration_minutes=30,
            db_path=self.db_path
        )
        self.assertFalse(res_early["success"])
        self.assertIn("outside", res_early["message"])

        # Too late
        res_late = book_appointment(
            patient_name="Night Owl",
            doctor_id=self.doctor1["id"],
            appointment_date=self.test_date,
            start_time="20:00",
            duration_minutes=30,
            db_path=self.db_path
        )
        self.assertFalse(res_late["success"])
        self.assertIn("outside", res_late["message"])

    def test_prevent_exact_and_partial_overlapping_appointments(self):
        """Test that overlapping slots for the same doctor are blocked."""
        # First booking: 11:00 to 12:00
        first = book_appointment(
            patient_name="Patient 1",
            doctor_id=self.doctor1["id"],
            appointment_date=self.test_date,
            start_time="11:00",
            duration_minutes=60,
            db_path=self.db_path
        )
        self.assertTrue(first["success"])

        # Second booking: exact same slot (11:00 - 12:00)
        exact_conflict = book_appointment(
            patient_name="Patient 2",
            doctor_id=self.doctor1["id"],
            appointment_date=self.test_date,
            start_time="11:00",
            duration_minutes=60,
            db_path=self.db_path
        )
        self.assertFalse(exact_conflict["success"])
        self.assertEqual(exact_conflict["error_type"], "CONFLICT")
        self.assertIn("already booked", exact_conflict["message"])

        # Third booking: partial overlap inside (11:15 - 11:45)
        inside_conflict = book_appointment(
            patient_name="Patient 3",
            doctor_id=self.doctor1["id"],
            appointment_date=self.test_date,
            start_time="11:15",
            duration_minutes=30,
            db_path=self.db_path
        )
        self.assertFalse(inside_conflict["success"])
        self.assertEqual(inside_conflict["error_type"], "CONFLICT")

        # Fourth booking: partial overlap starting earlier (10:45 - 11:15)
        early_overlap = book_appointment(
            patient_name="Patient 4",
            doctor_id=self.doctor1["id"],
            appointment_date=self.test_date,
            start_time="10:45",
            duration_minutes=30,
            db_path=self.db_path
        )
        self.assertFalse(early_overlap["success"])
        self.assertEqual(early_overlap["error_type"], "CONFLICT")

    def test_allow_back_to_back_appointments(self):
        """Test that adjacent appointments do not conflict with each other."""
        appt1 = book_appointment(
            patient_name="Morning Patient",
            doctor_id=self.doctor1["id"],
            appointment_date=self.test_date,
            start_time="10:00",
            duration_minutes=30,  # 10:00 to 10:30
            db_path=self.db_path
        )
        self.assertTrue(appt1["success"])

        appt2 = book_appointment(
            patient_name="Next Patient",
            doctor_id=self.doctor1["id"],
            appointment_date=self.test_date,
            start_time="10:30",  # 10:30 to 11:00
            duration_minutes=30,
            db_path=self.db_path
        )
        self.assertTrue(appt2["success"])

    def test_allow_simultaneous_appointments_for_different_doctors(self):
        """Test that different doctors can have appointments at the exact same time."""
        appt1 = book_appointment(
            patient_name="Patient A",
            doctor_id=self.doctor1["id"],
            appointment_date=self.test_date,
            start_time="11:00",
            duration_minutes=30,
            db_path=self.db_path
        )
        self.assertTrue(appt1["success"])

        appt2 = book_appointment(
            patient_name="Patient B",
            doctor_id=self.doctor2["id"],
            appointment_date=self.test_date,
            start_time="11:00",
            duration_minutes=30,
            db_path=self.db_path
        )
        self.assertTrue(appt2["success"])

    def test_alternative_slots_suggestion(self):
        """Test that alternative available slots are returned when conflict occurs."""
        # Book a slot
        book_appointment(
            patient_name="Occupant",
            doctor_id=self.doctor1["id"],
            appointment_date=self.test_date,
            start_time="10:00",
            duration_minutes=30,
            db_path=self.db_path
        )

        # Attempt to book same slot
        conflict = book_appointment(
            patient_name="New Applicant",
            doctor_id=self.doctor1["id"],
            appointment_date=self.test_date,
            start_time="10:00",
            duration_minutes=30,
            db_path=self.db_path
        )
        self.assertFalse(conflict["success"])
        alternatives = conflict.get("alternatives", [])
        self.assertGreater(len(alternatives), 0, "Should suggest alternative available slots.")

        # Ensure none of the suggested slots overlap with 10:00-10:30
        for alt in alternatives:
            self.assertFalse(
                check_overlap(alt["start_time"], alt["end_time"], "10:00", "10:30"),
                f"Suggested slot {alt['start_time']}-{alt['end_time']} should not overlap with 10:00-10:30"
            )

    def test_cancel_appointment_and_rebook(self):
        """Test appointment cancellation and verifying slot is available again."""
        booked = book_appointment(
            patient_name="Temporary Booking",
            doctor_id=self.doctor1["id"],
            appointment_date=self.test_date,
            start_time="14:00",
            duration_minutes=30,
            db_path=self.db_path
        )
        self.assertTrue(booked["success"])
        appt_id = booked["appointment"]["id"]

        # Cancel appointment
        cancel_res = cancel_appointment(appt_id, db_path=self.db_path)
        self.assertTrue(cancel_res["success"])

        # Check DB status is CANCELLED
        updated = get_appointment_by_id(appt_id, db_path=self.db_path)
        self.assertEqual(updated["status"], "CANCELLED")

        # Now booking the exact same slot should SUCCEED
        rebooked = book_appointment(
            patient_name="Second Chance Patient",
            doctor_id=self.doctor1["id"],
            appointment_date=self.test_date,
            start_time="14:00",
            duration_minutes=30,
            db_path=self.db_path
        )
        self.assertTrue(rebooked["success"])


if __name__ == "__main__":
    unittest.main()
