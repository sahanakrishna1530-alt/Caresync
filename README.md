# CareSync 🏥

**CareSync** is a beginner-friendly, smart hospital appointment scheduling application built for healthcare hackathons. It prevents scheduling conflicts in real-time, respects physician working hours, provides intelligent alternative time slot suggestions when a requested slot is occupied, and offers an intuitive hospital dashboard for appointment management and cancellations.

---

## 🌟 Key Features

1. **Clean, Responsive Healthcare Interface**: Intuitive booking portal and hospital management dashboard built with modern CSS and vanilla JavaScript.
2. **Conflict Prevention & Overlap Detection**: Mathematical interval overlap verification guarantees no doctor is double-booked (`max(startA, startB) < min(endA, endB)`).
3. **Doctor Shift & Working Hours Enforcement**: Validates that all appointments fit within the selected physician's shift hours.
4. **Smart Alternative Slot Suggestions**: If a slot is booked or unavailable, the system automatically suggests the closest available slots on that date. Clicking a suggestion auto-fills the booking form.
5. **Real-time Availability Checking**: "Check Availability" button enables pre-submission slot checks without submitting the form.
6. **Appointment Cancellation**: Cancel appointments with one click. Freeing up a cancelled slot makes it immediately bookable again for other patients.
7. **Hospital Management Dashboard**: Real-time metrics (Total, Scheduled, Today's Visits, Cancelled, Doctors on duty) and interactive table filtering by Doctor, Date, and Status.
8. **Persistent SQLite Database**: Zero-configuration, local file storage with parameterized queries to prevent SQL injection.
9. **Automated Conflict Test Suite**: Comprehensive unit tests covering overlap prevention, back-to-back bookings, multi-doctor concurrency, shifts, and cancellations.

---

## 🛠️ Technology Stack

- **Backend**: Python 3, Flask
- **Frontend**: Semantic HTML5, Custom CSS3 (Inter typography, responsive grid), Vanilla JavaScript (ES6+ Fetch API)
- **Database**: SQLite3 (`caresync.db`)
- **Testing**: Python `unittest` & `pytest`

---

## 📁 Project Structure

```text
caresync/
├── app.py                  # Flask web application & REST API routes
├── database.py             # SQLite connection, schema setup & CRUD queries
├── scheduler.py            # Conflict detection, working hours, and slot recommender
├── requirements.txt        # Python package dependencies
├── README.md               # Project documentation & run guide
├── templates/
│   ├── index.html          # Patient booking portal & live today glance
│   └── dashboard.html      # Hospital management dashboard & metrics
├── static/
│   ├── css/
│   │   └── style.css       # Responsive healthcare styling
│   └── js/
│       └── app.js          # Interactive booking, slot chips, and live updates
└── tests/
    └── test_scheduler.py   # Automated tests for conflict detection & cancellations
```

---

## 🚀 Quickstart Guide

### 1. Prerequisites
- Python 3.10 or higher installed. Verify with:
  ```bash
  python --version
  ```

### 2. Install Dependencies
Install Flask and pytest using `requirements.txt`:
```bash
python -m pip install -r requirements.txt
```

### 3. Run the Web Application
Start the Flask development server:
```bash
python app.py
```
Open your browser and navigate to:
```
http://127.0.0.1:5000
```
- **Booking Portal**: `http://127.0.0.1:5000/`
- **Hospital Dashboard**: `http://127.0.0.1:5000/dashboard`

---

## 🧪 Running Automated Tests

Run the automated test suite using standard Python `unittest`:
```bash
python -m unittest tests/test_scheduler.py
```

Or run with `pytest`:
```bash
python -m pytest tests/test_scheduler.py -v
```

All 10 test cases verify:
- Accurate time conversions and end time calculations.
- Overlap detection (exact, internal, and partial overlaps).
- Shift boundaries (preventing bookings outside working hours).
- Back-to-back non-overlapping appointments.
- Multi-doctor simultaneous scheduling.
- Generation of non-overlapping alternative slots when a slot is occupied.
- Slot re-usability after cancellation.
- Strict input validation.

---

## 🔌 REST API Reference

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/doctors` | List all doctors, specialties, and shift hours |
| `GET` | `/api/appointments` | Get appointments (supports `?doctor_id=`, `?date=`, `?status=`) |
| `POST` | `/api/appointments` | Book appointment (`patient_name`, `doctor_id`, `appointment_date`, `start_time`, `duration_minutes`, `reason`) |
| `POST` | `/api/appointments/<id>/cancel` | Cancel an existing appointment |
| `GET` | `/api/check-availability` | Check slot availability and retrieve alternative slots (`?doctor_id=&date=&time=&duration=`) |
| `GET` | `/api/stats` | Summary statistics for hospital operations |

---

## 💡 Hackathon Demo Walkthrough

1. **Book a standard appointment**:
   - Go to `http://127.0.0.1:5000/`
   - Select **Dr. Sarah Jenkins (Cardiology)**.
   - Choose a date and enter time `10:00` (duration: 30m).
   - Enter patient name `Johnathan Doe` and click **Confirm & Book Appointment**.
   - Notice the green confirmation message with reference number.

2. **Demonstrate Conflict Detection & Alternative Suggestions**:
   - Try booking another appointment for **Dr. Sarah Jenkins** on the same date at `10:00` or `10:15`.
   - Click **Confirm & Book Appointment**.
   - Notice the red conflict alert explaining that Dr. Jenkins is already booked from 10:00 to 10:30.
   - Look at the **"Alternative Available Slots"** card underneath.
   - Click any suggested slot chip (e.g. `10:30 - 11:00`). The form automatically updates its start time!
   - Click **Confirm & Book Appointment** to book the alternative slot instantly.

3. **Manage & Cancel in Dashboard**:
   - Navigate to `/dashboard` to view live hospital metrics and the appointment table.
   - Click **Cancel** on any scheduled appointment.
   - Notice the status badge dynamically changes to **Cancelled** and metrics update without reloading.
   - Returning to the booking portal, that previously booked slot is now available to be booked again.
4. **Demonstrate Emergency Appointment Handling**:
   - Open the appointment booking portal.
   - Select the emergency option, if available.
   - Enter the required patient and appointment details.
   - Click **Confirm & Book Appointment**.
   - Verify that the application applies its implemented emergency-handling rules and displays the appropriate result.

5. **Reschedule an Existing Appointment**:
   - Navigate to `/dashboard`.
   - Find an existing scheduled appointment.
   - Click **Reschedule**.
   - Select a new available date or time, as supported by the application.
   - Confirm the rescheduling request.
   - Verify that the appointment details update correctly and that scheduling conflicts are prevented.
## Live Website

**Try CareSync here:** [Open CareSync](https://breakfast-identical-file-additional.trycloudflare.com)

