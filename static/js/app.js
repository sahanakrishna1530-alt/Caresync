
/**
 * CareSync - Vanilla JavaScript Application Logic
 * Handles legacy homepage booking, availability checks,
 * cancellation, and dashboard filtering.
 */

document.addEventListener("DOMContentLoaded", () => {
    initBookingForm();
    initDoctorSelector();
    initDashboardFilters();
});

/* ------------------------------------------------------------------
   1. Legacy Homepage Booking & Availability
   ------------------------------------------------------------------ */

function initDoctorSelector() {
    const doctorSelect = document.getElementById("doctor-select");
    const hint = document.getElementById("doctor-schedule-hint");

    if (!doctorSelect || !hint) return;

    doctorSelect.addEventListener("change", () => {
        const option = doctorSelect.options[doctorSelect.selectedIndex];

        if (!option.value) {
            hint.classList.add("hidden");
            hint.textContent = "";
            return;
        }

        const start = option.getAttribute("data-start") || "—";
        const end = option.getAttribute("data-end") || "—";
        const room = option.getAttribute("data-room") || "—";
        const specialty = option.getAttribute("data-specialty") || "";

        hint.textContent =
            `Shift Hours: ${start} – ${end} | Location: ${room} | ${specialty}`;

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
    const patientInput = document.getElementById("patient-name");
    const doctorInput = document.getElementById("doctor-select");
    const dateInput = document.getElementById("appointment-date");
    const timeInput = document.getElementById("start-time");
    const durationInput = document.getElementById("duration-select");
    const reasonInput = document.getElementById("visit-reason");

    if (!patientInput || !doctorInput || !dateInput ||
        !timeInput || !durationInput || !reasonInput) {
        showFeedback("The booking form is incomplete.", "danger");
        return;
    }

    const patientName = patientInput.value.trim();
    const doctorId = doctorInput.value;
    const appointmentDate = dateInput.value;
    const startTime = timeInput.value;
    const duration = durationInput.value;
    const reason = reasonInput.value.trim();

    if (!patientName) {
        showFeedback("Please enter the patient's full name.", "danger");
        return;
    }

    if (!doctorId || !appointmentDate || !startTime) {
        showFeedback("Please select a doctor, date, and start time.", "danger");
        return;
    }

    setLoadingState(true);

    try {
        const response = await fetch("/api/appointments", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                patient_name: patientName,
                doctor_id: Number(doctorId),
                appointment_date: appointmentDate,
                start_time: startTime,
                duration_minutes: Number(duration),
                reason: reason,
                consultation_type: "in_person",
                address: ""
            })
        });

        const data = await response.json();

        if (response.ok && data.success) {
            showFeedback(
                `${data.message || "Appointment booked."} Reference #${String(data.appointment.id).padStart(4, "0")}`,
                "success"
            );

            hideAlternatives();
            form.reset();

            addAppointmentToFeedIfToday(data.appointment);
        } else {
            showFeedback(
                data.message || data.error || "Unable to schedule appointment.",
                "danger"
            );

            if (data.alternatives?.length) {
                displayAlternatives(data.alternatives);
            } else {
                hideAlternatives();
            }
        }
    } catch (error) {
        console.error("Booking error:", error);
        showFeedback("Unable to connect to the scheduling service.", "danger");
    } finally {
        setLoadingState(false);
    }
}

async function handleCheckAvailability() {
    const doctorInput = document.getElementById("doctor-select");
    const dateInput = document.getElementById("appointment-date");
    const timeInput = document.getElementById("start-time");
    const durationInput = document.getElementById("duration-select");

    if (!doctorInput || !dateInput || !timeInput || !durationInput) return;

    const doctorId = doctorInput.value;
    const date = dateInput.value;
    const time = timeInput.value;
    const duration = durationInput.value;

    if (!doctorId || !date || !time) {
        showFeedback("Please choose a doctor, date, and time.", "warning");
        return;
    }

    try {
        const params = new URLSearchParams({
            doctor_id: doctorId,
            date,
            time,
            duration
        });

        const response = await fetch(`/api/check-availability?${params}`);
        const data = await response.json();

        if (response.ok && data.available) {
            showFeedback(data.message || "This time is available.", "success");
            hideAlternatives();
        } else {
            showFeedback(
                data.message || "This time is not available.",
                "danger"
            );

            if (data.alternatives?.length) {
                displayAlternatives(data.alternatives);
            } else {
                hideAlternatives();
            }
        }
    } catch (error) {
        console.error("Availability error:", error);
        showFeedback("Unable to check availability. Please try again.", "danger");
    }
}

function displayAlternatives(alternatives) {
    const box = document.getElementById("alternatives-box");
    const list = document.getElementById("alternatives-list");

    if (!box || !list) return;

    list.replaceChildren();

    alternatives.forEach(slot => {
        const button = document.createElement("button");
        button.type = "button";
        button.className = "slot-chip";
        button.textContent = `🕒 ${slot.display || slot.start_time || "Available slot"}`;

        button.addEventListener("click", () => {
            const timeInput = document.getElementById("start-time");

            if (timeInput && slot.start_time) {
                timeInput.value = slot.start_time;
                showFeedback(
                    `Selected suggested time: ${slot.start_time}. Confirm the booking to continue.`,
                    "warning"
                );
            }
        });

        list.appendChild(button);
    });

    box.classList.remove("hidden");
}

function hideAlternatives() {
    document.getElementById("alternatives-box")?.classList.add("hidden");
}

function showFeedback(message, type = "info") {
    const container = document.getElementById("feedback-container");
    const alertBox = document.getElementById("feedback-alert");
    const messageElement = document.getElementById("feedback-message");

    if (!container || !alertBox || !messageElement) return;

    container.classList.remove("hidden");
    alertBox.className = `alert alert-${type}`;
    messageElement.textContent = message;
    container.scrollIntoView({ behavior: "smooth", block: "nearest" });
}

function setLoadingState(isLoading) {
    const button = document.getElementById("book-btn");
    if (!button) return;

    button.disabled = isLoading;

    const spinner = button.querySelector(".btn-spinner");
    const text = button.querySelector(".btn-text");

    spinner?.classList.toggle("hidden", !isLoading);

    if (text) {
        text.textContent = isLoading
            ? "Scheduling..."
            : "Confirm & Book Appointment";
    }
}

function addAppointmentToFeedIfToday(appointment) {
    if (!appointment) return;

    const feed = document.getElementById("today-appointments-list");
    if (!feed) return;

    const today = new Date().toLocaleDateString("en-CA");
    if (appointment.appointment_date !== today) return;

    document.getElementById("feed-empty-state")?.remove();

    const item = document.createElement("div");
    item.className = "feed-item";
    item.id = `feed-item-${appointment.id}`;

    const time = document.createElement("div");
    time.className = "feed-time";

    const start = document.createElement("span");
    start.className = "time-main";
    start.textContent = appointment.start_time || "";

    const end = document.createElement("span");
    end.className = "time-end";
    end.textContent = `to ${appointment.end_time || ""}`;

    time.append(start, end);

    const details = document.createElement("div");
    details.className = "feed-details";

    const patient = document.createElement("div");
    patient.className = "feed-patient";
    patient.textContent = appointment.patient_name || "";

    const doctor = document.createElement("div");
    doctor.className = "feed-doctor";
    doctor.textContent =
        `${appointment.doctor_name || ""} • ${appointment.doctor_room || ""}`;

    details.append(patient, doctor);

    const action = document.createElement("div");
    action.className = "feed-action";

    const cancelButton = document.createElement("button");
    cancelButton.type = "button";
    cancelButton.className = "btn-cancel-small";
    cancelButton.textContent = "Cancel";
    cancelButton.addEventListener("click", () => {
        cancelAppointmentAction(appointment.id);
    });

    action.appendChild(cancelButton);
    item.append(time, details, action);
    feed.prepend(item);
}

/* ------------------------------------------------------------------
   2. Appointment Cancellation
   ------------------------------------------------------------------ */

async function cancelAppointmentAction(appointmentId) {
    if (!confirm(
        `Are you sure you want to cancel appointment #${String(appointmentId).padStart(4, "0")}?`
    )) {
        return;
    }

    try {
        const response = await fetch(
            `/api/appointments/${encodeURIComponent(appointmentId)}/cancel`,
            { method: "POST" }
        );

        const data = await response.json();

        if (!response.ok || !data.success) {
            alert(data.message || data.error || "Failed to cancel appointment.");
            return;
        }

        const row = document.getElementById(`row-${appointmentId}`);

        if (row) {
            row.classList.add("row-cancelled");

            // Updated dashboard columns:
            // Status is column 11 (index 10); Actions is column 12 (index 11).
            if (row.cells[10]) {
                row.cells[10].innerHTML =
                    '<span class="badge badge-danger">Cancelled</span>';
            }

            if (row.cells[11]) {
                row.cells[11].textContent = "—";
            }

            updateDashboardMetricsAfterCancel();
        }

        const feedItem = document.getElementById(`feed-item-${appointmentId}`);

        if (feedItem) {
            feedItem.style.opacity = "0.55";
            feedItem.style.pointerEvents = "none";

            const action = feedItem.querySelector(".feed-action");
            if (action) {
                action.textContent = "Cancelled";
            }
        }

        const alertBox = document.getElementById("dashboard-alert");
        const alertMessage = document.getElementById("dashboard-alert-msg");

        if (alertBox && alertMessage) {
            alertBox.className = "alert alert-success";
            alertMessage.textContent = data.message || "Appointment cancelled.";
            alertBox.classList.remove("hidden");
            window.scrollTo({ top: 0, behavior: "smooth" });
        } else {
            alert(data.message || "Appointment cancelled.");
        }
    } catch (error) {
        console.error("Cancellation error:", error);
        alert("Unable to communicate with the server. Please try again.");
    }
}

function updateDashboardMetricsAfterCancel() {
    const scheduled = document.getElementById("metric-scheduled");
    const cancelled = document.getElementById("metric-cancelled");

    if (scheduled) {
        const value = Number.parseInt(scheduled.textContent, 10) || 0;
        scheduled.textContent = String(Math.max(0, value - 1));
    }

    if (cancelled) {
        const value = Number.parseInt(cancelled.textContent, 10) || 0;
        cancelled.textContent = String(value + 1);
    }
}

/* ------------------------------------------------------------------
   3. Dashboard Filters
   ------------------------------------------------------------------ */

function initDashboardFilters() {
    const applyButton = document.getElementById("apply-filters-btn");
    const resetButton = document.getElementById("reset-filters-btn");

    applyButton?.addEventListener("click", fetchAndRenderFilteredAppointments);

    resetButton?.addEventListener("click", () => {
        const doctor = document.getElementById("filter-doctor");
        const date = document.getElementById("filter-date");
        const status = document.getElementById("filter-status");

        if (doctor) doctor.value = "";
        if (date) date.value = "";
        if (status) status.value = "ALL";

        fetchAndRenderFilteredAppointments();
    });
}

async function fetchAndRenderFilteredAppointments() {
    const doctorId = document.getElementById("filter-doctor")?.value || "";
    const date = document.getElementById("filter-date")?.value || "";
    const status = document.getElementById("filter-status")?.value || "ALL";

    const params = new URLSearchParams();

    if (doctorId) params.set("doctor_id", doctorId);
    if (date) params.set("date", date);
    if (status && status !== "ALL") params.set("status", status);

    try {
        const response = await fetch(`/api/appointments?${params.toString()}`);
        const data = await response.json();

        if (!response.ok || !data.success) {
            showDashboardAlert(
                data.message || "Unable to load filtered appointments.",
                "danger"
            );
            return;
        }

        renderAppointmentsTable(data.appointments || []);
    } catch (error) {
        console.error("Filtering error:", error);
        showDashboardAlert("Unable to load appointments. Please try again.", "danger");
    }
}

function renderAppointmentsTable(appointments) {
    const tbody = document.getElementById("appointments-tbody");
    const count = document.getElementById("records-count-num");

    if (!tbody) return;

    if (count) {
        count.textContent = String(appointments.length);
    }

    if (appointments.length === 0) {
        tbody.innerHTML = `
            <tr id="no-records-row">
                <td colspan="12" class="text-center py-8">
                    <div class="empty-state">
                        <div class="empty-icon">📂</div>
                        <p class="empty-text">No appointment records match your filters.</p>
                        <a href="/book" class="btn btn-secondary mt-2">Book an Appointment</a>
                    </div>
                </td>
            </tr>
        `;
        return;
    }

    tbody.innerHTML = appointments.map(appt => {
        const id = escapeHtml(String(appt.id ?? ""));
        const cancelled = appt.status === "CANCELLED";

        const statusBadge = cancelled
            ? '<span class="badge badge-danger">Cancelled</span>'
            : '<span class="badge badge-success">Scheduled</span>';

        const action = cancelled
            ? '<span class="text-muted text-sm">—</span>'
            : `<button type="button" class="btn-cancel-small" data-cancel-id="${id}">Cancel</button>`;

        const consultationLabels = {
            video: "Video Visit",
            phone: "Phone Call",
            in_person: "In Person",
            home: "Home Visit"
        };

        const consultationType = consultationLabels[appt.consultation_type];
        const consultationHtml = consultationType
            ? `<span class="consultation-type">${escapeHtml(consultationType)}</span>`
            : '<span class="text-muted">—</span>';

        const priceHtml = appt.price !== null &&
                          appt.price !== undefined &&
                          appt.price !== ""
            ? `<div class="consultation-price">₹${escapeHtml(String(appt.price))}</div>`
            : '<span class="text-muted">—</span>';

        const addressHtml = appt.consultation_type === "home"
            ? (appt.address
                ? `<div class="visit-address">${escapeHtml(appt.address)}</div>`
                : '<span class="text-muted">Not provided</span>')
            : '<span class="text-muted">—</span>';

        return `
            <tr id="row-${id}" class="${cancelled ? "row-cancelled" : ""}">
                <td class="font-mono">#${String(appt.id).padStart(4, "0")}</td>
                <td>
                    <div class="patient-name-cell">${escapeHtml(appt.patient_name)}</div>
                    ${appt.reason
                        ? `<div class="patient-reason-sub">${escapeHtml(appt.reason)}</div>`
                        : ""}
                </td>
                <td>
                    <div class="doctor-name-cell">${escapeHtml(appt.doctor_name)}</div>
                    <div class="doctor-spec-sub">${escapeHtml(appt.doctor_specialty)}</div>
                </td>
                <td>${escapeHtml(appt.appointment_date)}</td>
                <td>
                    <span class="time-range-badge">
                        ${escapeHtml(appt.start_time)} &ndash; ${escapeHtml(appt.end_time)}
                    </span>
                </td>
                <td>${escapeHtml(String(appt.duration_minutes ?? ""))} min</td>
                <td class="consultation-cell">${consultationHtml}</td>
                <td>${priceHtml}</td>
                <td>${addressHtml}</td>
                <td><span class="badge badge-light">${escapeHtml(appt.doctor_room || "—")}</span></td>
                <td>${statusBadge}</td>
                <td>${action}</td>
            </tr>
        `;
    }).join("");

    // Attach cancellation handlers to the newly rendered rows.
    tbody.querySelectorAll("[data-cancel-id]").forEach(button => {
        button.addEventListener("click", () => {
            cancelAppointmentAction(button.dataset.cancelId);
        });
    });
}

function showDashboardAlert(message, type = "info") {
    const box = document.getElementById("dashboard-alert");
    const text = document.getElementById("dashboard-alert-msg");

    if (!box || !text) return;

    box.className = `alert alert-${type}`;
    text.textContent = message;
    box.classList.remove("hidden");
}

function escapeHtml(value) {
    if (value === null || value === undefined) return "";

    return String(value)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}
