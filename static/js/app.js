/**
 * CareSync - Vanilla JavaScript Application Logic
 * Handles interactive booking, availability checks, alternative slot selections,
 * cancellation flows, and dashboard filtering.
 */

document.addEventListener("DOMContentLoaded", () => {
    initBookingForm();
    initDoctorSelector();
    initDashboardFilters();
});

/* -------------------------------------------------------------------------
   1. Booking & Availability Logic
   ------------------------------------------------------------------------- */

function initDoctorSelector() {
    const doctorSelect = document.getElementById("doctor-select");
    const hint = document.getElementById("doctor-schedule-hint");

    if (!doctorSelect || !hint) return;

    doctorSelect.addEventListener("change", () => {
        const selectedOption = doctorSelect.options[doctorSelect.selectedIndex];
        if (!selectedOption.value) {
            hint.classList.add("hidden");
            hint.textContent = "";
            return;
        }

        const start = selectedOption.getAttribute("data-start");
        const end = selectedOption.getAttribute("data-end");
        const room = selectedOption.getAttribute("data-room");
        const specialty = selectedOption.getAttribute("data-specialty");

        hint.innerHTML = `<strong>Shift Hours:</strong> ${start} &ndash; ${end} &bull; <strong>Location:</strong> ${room} &bull; <em>${specialty}</em>`;
        hint.classList.remove("hidden");
    });
}

function initBookingForm() {
    const form = document.getElementById("appointment-form");
    const checkBtn = document.getElementById("check-btn");

    if (form) {
        form.addEventListener("submit", handleBookingSubmit);
    }

    if (checkBtn) {
        checkBtn.addEventListener("click", handleCheckAvailability);
    }
}

async function handleBookingSubmit(event) {
    event.preventDefault();

    const form = event.target;
    const patientName = document.getElementById("patient-name").value.trim();
    const doctorId = document.getElementById("doctor-select").value;
    const appointmentDate = document.getElementById("appointment-date").value;
    const startTime = document.getElementById("start-time").value;
    const duration = document.getElementById("duration-select").value;
    const reason = document.getElementById("visit-reason").value.trim();

    // Client-side quick validation
    if (!patientName) {
        showFeedback("Please enter the patient's full name.", "danger");
        return;
    }
    if (!doctorId) {
        showFeedback("Please select an attending physician.", "danger");
        return;
    }
    if (!appointmentDate) {
        showFeedback("Please select an appointment date.", "danger");
        return;
    }
    if (!startTime) {
        showFeedback("Please specify a preferred start time.", "danger");
        return;
    }

    setLoadingState(true);

    try {
        const response = await fetch("/api/appointments", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                patient_name: patientName,
                doctor_id: parseInt(doctorId, 10),
                appointment_date: appointmentDate,
                start_time: startTime,
                duration_minutes: parseInt(duration, 10),
                reason: reason
            })
        });

        const data = await response.json();

        if (response.ok && data.success) {
            // Success
            showFeedback(`✓ ${data.message} (Reference #${String(data.appointment.id).padStart(4, "0")})`, "success");
            hideAlternatives();
            form.reset();

            // Reset default date and time
            const dateInput = document.getElementById("appointment-date");
            if (dateInput) {
                const today = new Date().toISOString().split("T")[0];
                dateInput.value = today;
            }
            const timeInput = document.getElementById("start-time");
            if (timeInput) timeInput.value = "10:00";

            // If appointment is today, append to live feed on index page
            addAppointmentToFeedIfToday(data.appointment);
        } else {
            // Conflict or validation error
            showFeedback(data.message || "Unable to schedule appointment.", "danger");

            if (data.alternatives && data.alternatives.length > 0) {
                displayAlternatives(data.alternatives);
            } else {
                hideAlternatives();
            }
        }
    } catch (err) {
        console.error("Booking error:", err);
        showFeedback("Network error connecting to scheduling service. Please try again.", "danger");
    } finally {
        setLoadingState(false);
    }
}

async function handleCheckAvailability() {
    const doctorId = document.getElementById("doctor-select").value;
    const appointmentDate = document.getElementById("appointment-date").value;
    const startTime = document.getElementById("start-time").value;
    const duration = document.getElementById("duration-select").value;

    if (!doctorId || !appointmentDate || !startTime) {
        showFeedback("Please choose a doctor, date, and start time to check availability.", "warning");
        return;
    }

    try {
        const url = `/api/check-availability?doctor_id=${doctorId}&date=${encodeURIComponent(appointmentDate)}&time=${encodeURIComponent(startTime)}&duration=${duration}`;
        const response = await fetch(url);
        const data = await response.json();

        if (data.available) {
            showFeedback(`✓ Slot is available! ${data.message}`, "success");
            hideAlternatives();
        } else {
            showFeedback(data.message, "danger");
            if (data.alternatives && data.alternatives.length > 0) {
                displayAlternatives(data.alternatives);
            } else {
                hideAlternatives();
            }
        }
    } catch (err) {
        console.error("Check availability error:", err);
        showFeedback("Error checking availability. Please try again.", "danger");
    }
}

function displayAlternatives(alternatives) {
    const altBox = document.getElementById("alternatives-box");
    const altList = document.getElementById("alternatives-list");
    if (!altBox || !altList) return;

    altList.innerHTML = "";

    alternatives.forEach(slot => {
        const btn = document.createElement("button");
        btn.type = "button";
        btn.className = "slot-chip";
        btn.innerHTML = `<span>🕒</span> ${slot.display}`;
        btn.title = `Click to choose ${slot.start_time}`;

        btn.addEventListener("click", () => {
            const timeInput = document.getElementById("start-time");
            if (timeInput) {
                timeInput.value = slot.start_time;
                // Highlight input briefly
                timeInput.style.borderColor = "#0d9488";
                timeInput.style.boxShadow = "0 0 0 4px rgba(13, 148, 136, 0.25)";
                setTimeout(() => {
                    timeInput.style.borderColor = "";
                    timeInput.style.boxShadow = "";
                }, 1200);

                showFeedback(`Selected suggested time: ${slot.start_time}. Click "Confirm & Book Appointment" to finalize.`, "warning");
            }
        });

        altList.appendChild(btn);
    });

    altBox.classList.remove("hidden");
}

function hideAlternatives() {
    const altBox = document.getElementById("alternatives-box");
    if (altBox) {
        altBox.classList.add("hidden");
    }
}

function showFeedback(message, type = "info") {
    const container = document.getElementById("feedback-container");
    const alert = document.getElementById("feedback-alert");
    const msgEl = document.getElementById("feedback-message");

    if (!container || !alert || !msgEl) return;

    container.classList.remove("hidden");
    alert.className = `alert alert-${type}`;
    msgEl.textContent = message;

    // Smooth scroll if needed
    container.scrollIntoView({ behavior: "smooth", block: "nearest" });
}

function setLoadingState(isLoading) {
    const bookBtn = document.getElementById("book-btn");
    if (!bookBtn) return;

    const spinner = bookBtn.querySelector(".btn-spinner");
    const text = bookBtn.querySelector(".btn-text");

    if (isLoading) {
        bookBtn.disabled = true;
        if (spinner) spinner.classList.remove("hidden");
        if (text) text.textContent = "Scheduling...";
    } else {
        bookBtn.disabled = false;
        if (spinner) spinner.classList.add("hidden");
        if (text) text.textContent = "Confirm & Book Appointment";
    }
}

function addAppointmentToFeedIfToday(appointment) {
    const today = new Date().toISOString().split("T")[0];
    if (appointment.appointment_date !== today) return;

    const feedList = document.getElementById("today-appointments-list");
    const emptyState = document.getElementById("feed-empty-state");
    if (!feedList) return;

    if (emptyState) {
        emptyState.remove();
    }

    const item = document.createElement("div");
    item.className = "feed-item";
    item.id = `feed-item-${appointment.id}`;
    item.innerHTML = `
        <div class="feed-time">
            <span class="time-main">${appointment.start_time}</span>
            <span class="time-end">to ${appointment.end_time}</span>
        </div>
        <div class="feed-details">
            <div class="feed-patient">${appointment.patient_name}</div>
            <div class="feed-doctor">
                ${appointment.doctor_name} &bull; <span class="badge badge-light">${appointment.doctor_room}</span>
            </div>
        </div>
        <div class="feed-action">
            <button class="btn-cancel-small" onclick="cancelAppointmentAction(${appointment.id})" title="Cancel Appointment">
                Cancel
            </button>
        </div>
    `;

    feedList.prepend(item);
}

/* -------------------------------------------------------------------------
   2. Appointment Cancellation Action
   ------------------------------------------------------------------------- */

async function cancelAppointmentAction(appointmentId) {
    const confirmed = confirm(`Are you sure you want to cancel appointment #${String(appointmentId).padStart(4, "0")}?`);
    if (!confirmed) return;

    try {
        const response = await fetch(`/api/appointments/${appointmentId}/cancel`, {
            method: "POST"
        });
        const data = await response.json();

        if (response.ok && data.success) {
            // Update Dashboard Table Row if present
            const row = document.getElementById(`row-${appointmentId}`);
            if (row) {
                row.classList.add("row-cancelled");
                const statusCell = row.cells[7];
                const actionCell = row.cells[8];
                if (statusCell) {
                    statusCell.innerHTML = '<span class="badge badge-danger">Cancelled</span>';
                }
                if (actionCell) {
                    actionCell.innerHTML = '<span class="text-muted text-sm">&mdash;</span>';
                }
                updateDashboardMetricsAfterCancel();
            }

            // Update Index Feed Item if present
            const feedItem = document.getElementById(`feed-item-${appointmentId}`);
            if (feedItem) {
                feedItem.style.opacity = "0.4";
                feedItem.style.pointerEvents = "none";
                const actionBtn = feedItem.querySelector(".feed-action");
                if (actionBtn) {
                    actionBtn.innerHTML = '<span class="badge badge-danger">Cancelled</span>';
                }
            }

            // Alert banner on dashboard
            const dashAlert = document.getElementById("dashboard-alert");
            const dashAlertMsg = document.getElementById("dashboard-alert-msg");
            if (dashAlert && dashAlertMsg) {
                dashAlert.className = "alert alert-success";
                dashAlertMsg.textContent = `✓ ${data.message}`;
                dashAlert.classList.remove("hidden");
                window.scrollTo({ top: 0, behavior: "smooth" });
            } else {
                alert(`✓ ${data.message}`);
            }
        } else {
            alert(data.message || "Failed to cancel appointment.");
        }
    } catch (err) {
        console.error("Cancellation error:", err);
        alert("An error occurred while communicating with the server.");
    }
}

function updateDashboardMetricsAfterCancel() {
    const scheduledEl = document.getElementById("metric-scheduled");
    const cancelledEl = document.getElementById("metric-cancelled");

    if (scheduledEl) {
        const currentSched = parseInt(scheduledEl.textContent, 10) || 0;
        scheduledEl.textContent = Math.max(0, currentSched - 1);
    }
    if (cancelledEl) {
        const currentCanc = parseInt(cancelledEl.textContent, 10) || 0;
        cancelledEl.textContent = currentCanc + 1;
    }
}

/* -------------------------------------------------------------------------
   3. Dashboard Filtering Logic
   ------------------------------------------------------------------------- */

function initDashboardFilters() {
    const applyBtn = document.getElementById("apply-filters-btn");
    const resetBtn = document.getElementById("reset-filters-btn");

    if (applyBtn) {
        applyBtn.addEventListener("click", fetchAndRenderFilteredAppointments);
    }

    if (resetBtn) {
        resetBtn.addEventListener("click", () => {
            const docFilter = document.getElementById("filter-doctor");
            const dateFilter = document.getElementById("filter-date");
            const statusFilter = document.getElementById("filter-status");

            if (docFilter) docFilter.value = "";
            if (dateFilter) dateFilter.value = "";
            if (statusFilter) statusFilter.value = "ALL";

            fetchAndRenderFilteredAppointments();
        });
    }
}

async function fetchAndRenderFilteredAppointments() {
    const doctorId = document.getElementById("filter-doctor")?.value || "";
    const date = document.getElementById("filter-date")?.value || "";
    const status = document.getElementById("filter-status")?.value || "ALL";

    const params = new URLSearchParams();
    if (doctorId) params.append("doctor_id", doctorId);
    if (date) params.append("date", date);
    if (status) params.append("status", status);

    try {
        const response = await fetch(`/api/appointments?${params.toString()}`);
        const data = await response.json();

        if (data.success) {
            renderAppointmentsTable(data.appointments);
        }
    } catch (err) {
        console.error("Error filtering appointments:", err);
    }
}

function renderAppointmentsTable(appointments) {
    const tbody = document.getElementById("appointments-tbody");
    const countEl = document.getElementById("records-count-num");

    if (!tbody) return;

    if (countEl) {
        countEl.textContent = appointments.length;
    }

    if (!appointments || appointments.length === 0) {
        tbody.innerHTML = `
            <tr id="no-records-row">
                <td colspan="9" class="text-center py-8">
                    <div class="empty-state">
                        <div class="empty-icon">📂</div>
                        <p class="empty-text">No appointment records match your filters.</p>
                    </div>
                </td>
            </tr>
        `;
        return;
    }

    tbody.innerHTML = appointments.map(appt => {
        const isCancelled = appt.status === "CANCELLED";
        const rowClass = isCancelled ? "row-cancelled" : "";
        const formattedId = "#" + String(appt.id).padStart(4, "0");
        const statusBadge = isCancelled
            ? '<span class="badge badge-danger">Cancelled</span>'
            : '<span class="badge badge-success">Scheduled</span>';
        const actionBtn = isCancelled
            ? '<span class="text-muted text-sm">&mdash;</span>'
            : `<button class="btn-cancel-small" onclick="cancelAppointmentAction(${appt.id})">Cancel</button>`;
        const reasonHtml = appt.reason
            ? `<div class="patient-reason-sub">${escapeHtml(appt.reason)}</div>`
            : "";

        return `
            <tr id="row-${appt.id}" class="${rowClass}">
                <td class="font-mono">${formattedId}</td>
                <td>
                    <div class="patient-name-cell">${escapeHtml(appt.patient_name)}</div>
                    ${reasonHtml}
                </td>
                <td>
                    <div class="doctor-name-cell">${escapeHtml(appt.doctor_name)}</div>
                    <div class="doctor-spec-sub">${escapeHtml(appt.doctor_specialty)}</div>
                </td>
                <td>${appt.appointment_date}</td>
                <td>
                    <span class="time-range-badge">${appt.start_time} &ndash; ${appt.end_time}</span>
                </td>
                <td>${appt.duration_minutes}m</td>
                <td><span class="badge badge-light">${escapeHtml(appt.doctor_room)}</span></td>
                <td>${statusBadge}</td>
                <td>${actionBtn}</td>
            </tr>
        `;
    }).join("");
}

function escapeHtml(str) {
    if (!str) return "";
    return str
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}
