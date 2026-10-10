
"use strict";

/* =========================================================
   CareSync - Dashboard, Booking, Filters, Cancellation
   and Appointment Rescheduling
   ========================================================= */

let activeDashboardFilter = "ALL";
let activeRescheduleAppointment = null;

document.addEventListener("DOMContentLoaded", () => {
    initBookingForm();
    initDoctorSelector();
    initDashboard();
    initRescheduling();
});

/* -------------------- Common helpers -------------------- */

function escapeHtml(value) {
    return String(value ?? "").replace(/[&<>"']/g, character => ({
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#39;"
    })[character]);
}

function getLocalDate() {
    const now = new Date();
    const year = now.getFullYear();
    const month = String(now.getMonth() + 1).padStart(2, "0");
    const day = String(now.getDate()).padStart(2, "0");

    return `${year}-${month}-${day}`;
}

async function readResponse(response) {
    const data = await response.json();

    if (!response.ok || data.success === false) {
        throw new Error(
            data.message || data.error || "The request could not be completed."
        );
    }

    return data;
}

function showDashboardAlert(message, type = "success") {
    const box = document.getElementById("dashboard-alert");
    const messageElement = document.getElementById("dashboard-alert-msg");

    if (!box || !messageElement) {
        window.alert(message);
        return;
    }

    // Accept either "error" or "alert-error".
    const normalizedType = String(type).replace(/^alert-/, "");

    box.className = `alert alert-${normalizedType}`;
    messageElement.textContent = message;
    box.classList.remove("hidden");
}

function showRescheduleFeedback(message, type = "") {
    const feedback = document.getElementById("reschedule-feedback");

    if (!feedback) return;

    feedback.className = `reschedule-feedback ${type}`.trim();
    feedback.textContent = message;
}

function clearRescheduleFeedback() {
    const feedback = document.getElementById("reschedule-feedback");

    if (!feedback) return;

    feedback.className = "reschedule-feedback";
    feedback.replaceChildren();
}

/* -------------------- Dashboard summary cards -------------------- */

function initDashboard() {
    const tableBody = document.getElementById("appointments-tbody");

    // Dashboard features are only initialized on the dashboard page.
    if (!tableBody) return;

    document.querySelectorAll("[data-dashboard-filter]").forEach(card => {
        card.addEventListener("click", () => {
            const filter = card.dataset.dashboardFilter || "ALL";

            activeDashboardFilter = filter;

            const doctor = document.getElementById("filter-doctor");
            const date = document.getElementById("filter-date");
            const status = document.getElementById("filter-status");

            // Summary cards start a fresh view.
            if (doctor) doctor.value = "";
            if (date) date.value = "";
            if (status) status.value = "ALL";

            if (filter === "SCHEDULED" && status) {
                status.value = "SCHEDULED";
            } else if (filter === "CANCELLED" && status) {
                status.value = "CANCELLED";
            } else if (filter === "TODAY" && date) {
                date.value = getLocalDate();
                if (status) status.value = "SCHEDULED";
            }

            updateActiveCard(filter);
            loadAppointments();
        });
    });

    document.getElementById("apply-filters-btn")
        ?.addEventListener("click", () => {
            activeDashboardFilter = "CUSTOM";
            updateActiveCard(null);
            loadAppointments();
        });

    document.getElementById("reset-filters-btn")
        ?.addEventListener("click", () => {
            const doctor = document.getElementById("filter-doctor");
            const date = document.getElementById("filter-date");
            const status = document.getElementById("filter-status");

            if (doctor) doctor.value = "";
            if (date) date.value = "";
            if (status) status.value = "ALL";

            activeDashboardFilter = "ALL";
            updateActiveCard("ALL");
            loadAppointments();
        });

    updateActiveCard("ALL");
}

function updateActiveCard(filter) {
    document.querySelectorAll("[data-dashboard-filter]").forEach(card => {
        const selected =
            filter !== null &&
            card.dataset.dashboardFilter === filter;

        card.classList.toggle("active", selected);
        card.setAttribute("aria-pressed", String(selected));
    });
}

/* -------------------- Load and filter appointments -------------------- */

async function loadAppointments() {
    const tbody = document.getElementById("appointments-tbody");

    if (!tbody) return;

    const doctorId = document.getElementById("filter-doctor")?.value || "";
    const selectedDate = document.getElementById("filter-date")?.value || "";
    const status = document.getElementById("filter-status")?.value || "ALL";

    const params = new URLSearchParams();

    if (doctorId) params.set("doctor_id", doctorId);
    if (selectedDate) params.set("date", selectedDate);
    if (status !== "ALL") params.set("status", status);

    tbody.innerHTML = `
        <tr>
            <td colspan="12" class="text-center">Loading appointments...</td>
        </tr>`;

    try {
        const response = await fetch(`/api/appointments?${params.toString()}`);
        const data = await readResponse(response);

        let appointments = Array.isArray(data)
            ? data
            : (data.appointments || data.records || []);

        if (!Array.isArray(appointments)) {
            throw new Error("Unexpected appointment data returned by the server.");
        }

        if (activeDashboardFilter === "TODAY") {
            const today = getLocalDate();

            appointments = appointments.filter(appointment =>
                String(appointment.appointment_date || "").slice(0, 10) === today
            );
        }

        renderAppointmentsTable(appointments);
    } catch (error) {
        console.error("Loading appointments failed:", error);

        tbody.innerHTML = `
            <tr>
                <td colspan="12" class="text-center">
                    Unable to load appointments. Please try again.
                </td>
            </tr>`;

        showDashboardAlert(error.message, "error");
    }
}

/* -------------------- Render the 12-column table -------------------- */

function renderAppointmentsTable(appointments) {
    const tbody = document.getElementById("appointments-tbody");
    const count = document.getElementById("records-count-num");

    if (!tbody) return;

    if (count) count.textContent = String(appointments.length);

    if (appointments.length === 0) {
        tbody.innerHTML = `
            <tr id="no-records-row">
                <td colspan="12" class="text-center py-8">
                    <div class="empty-state">
                        <div class="empty-icon">No records</div>
                        <p class="empty-text">
                            No appointments match the selected filters.
                        </p>
                        <a href="/book" class="btn btn-secondary mt-2">
                            Book an Appointment
                        </a>
                    </div>
                </td>
            </tr>`;
        return;
    }

    const consultationNames = {
        video: "Video Visit",
        phone: "Phone Call",
        in_person: "In Person",
        home: "Home Visit"
    };

    tbody.innerHTML = appointments.map(appointment => {
        const id = Number(appointment.id);

        if (!Number.isInteger(id) || id < 1) return "";

        const status = String(appointment.status || "").toUpperCase();
        const isScheduled = status === "SCHEDULED";
        const isHomeVisit = appointment.consultation_type === "home";
        const consultation = consultationNames[appointment.consultation_type];

        const price =
            appointment.price !== null &&
            appointment.price !== undefined &&
            appointment.price !== ""
                ? `₹${escapeHtml(appointment.price)}`
                : "—";

        const address = isHomeVisit
            ? escapeHtml(appointment.address || "Not provided")
            : "—";

        const dateValue = String(appointment.appointment_date || "").slice(0, 10);
        const startTime = String(appointment.start_time || "").slice(0, 5);
        const duration = Number(appointment.duration_minutes) || 30;

        const actionButtons = isScheduled
            ? `
                <div class="appointment-actions">
                    <button type="button"
                            class="btn-reschedule-small"
                            data-reschedule-id="${id}"
                            data-reschedule-date="${escapeHtml(dateValue)}"
                            data-reschedule-time="${escapeHtml(startTime)}"
                            data-reschedule-duration="${duration}"
                            data-patient-name="${escapeHtml(appointment.patient_name || "")}">
                        Reschedule
                    </button>
                    <button type="button"
                            class="btn-cancel-small"
                            data-cancel-id="${id}">
                        Cancel
                    </button>
                </div>`
            : '<span class="text-muted text-sm">—</span>';

        return `
            <tr id="row-${id}" class="${isScheduled ? "" : "row-cancelled"}">
                <td class="font-mono">#${String(id).padStart(4, "0")}</td>

                <td>
                    <div class="patient-name-cell">
                        ${escapeHtml(appointment.patient_name || "—")}
                    </div>
                    ${appointment.reason
                        ? `<div class="patient-reason-sub">${escapeHtml(appointment.reason)}</div>`
                        : ""}
                </td>

                <td>
                    <div class="doctor-name-cell">
                        ${escapeHtml(appointment.doctor_name || "—")}
                    </div>
                    <div class="doctor-spec-sub">
                        ${escapeHtml(appointment.doctor_specialty || "")}
                    </div>
                </td>

                <td>${escapeHtml(dateValue || "—")}</td>

                <td>
                    <span class="time-range-badge">
                        ${escapeHtml(startTime || "—")}
                        &ndash;
                        ${escapeHtml(String(appointment.end_time || "").slice(0, 5) || "—")}
                    </span>
                </td>

                <td>${escapeHtml(appointment.duration_minutes ?? "—")} min</td>

                <td class="consultation-cell">
                    ${consultation
                        ? `<span class="consultation-type">${escapeHtml(consultation)}</span>`
                        : "—"}
                </td>

                <td><div class="consultation-price">${price}</div></td>

                <td><div class="visit-address">${address}</div></td>

                <td>
                    <span class="badge badge-light">
                        ${escapeHtml(appointment.doctor_room || "—")}
                    </span>
                </td>

                <td>
                    <span class="badge ${isScheduled ? "badge-success" : "badge-danger"}">
                        ${isScheduled ? "Scheduled" : "Cancelled"}
                    </span>
                </td>

                <td>${actionButtons}</td>
            </tr>`;
    }).join("");

    // Event delegation handles buttons after every table redraw.
    tbody.querySelectorAll("[data-cancel-id]").forEach(button => {
        button.addEventListener("click", () => {
            cancelAppointmentAction(button.dataset.cancelId);
        });
    });

    tbody.querySelectorAll("[data-reschedule-id]").forEach(button => {
        button.addEventListener("click", () => {
            openRescheduleForm(button);
        });
    });
}

/* -------------------- Cancel an appointment -------------------- */

async function cancelAppointmentAction(appointmentId) {
    const id = Number(appointmentId);

    if (!Number.isInteger(id) || id < 1) {
        showDashboardAlert("Invalid appointment ID.", "error");
        return;
    }

    if (!window.confirm(
        `Are you sure you want to cancel appointment #${String(id).padStart(4, "0")}?`
    )) {
        return;
    }

    try {
        const response = await fetch(`/api/appointments/${id}/cancel`, {
            method: "POST"
        });

        const data = await readResponse(response);

        showDashboardAlert(
            data.message || "Appointment cancelled successfully.",
            "success"
        );

        await loadAppointments();
        await refreshDashboardMetrics();
    } catch (error) {
        console.error("Cancellation failed:", error);
        showDashboardAlert(error.message || "Cancellation failed.", "error");
    }
}

/* -------------------- Rescheduling form -------------------- */

function initRescheduling() {
    const form = document.getElementById("reschedule-form");
    const closeButton = document.getElementById("reschedule-close");
    const panel = document.getElementById("reschedule-panel");

    if (!form || !panel) return;

    form.addEventListener("submit", handleRescheduleSubmit);

    closeButton?.addEventListener("click", closeRescheduleForm);
}

function openRescheduleForm(button) {
    const panel = document.getElementById("reschedule-panel");
    const form = document.getElementById("reschedule-form");

    if (!panel || !form) return;

    const id = Number(button.dataset.rescheduleId);

    if (!Number.isInteger(id) || id < 1) {
        showDashboardAlert("Invalid appointment ID.", "error");
        return;
    }

    activeRescheduleAppointment = id;

    document.getElementById("reschedule-appointment-id").value = String(id);
    document.getElementById("reschedule-date").value =
        button.dataset.rescheduleDate || "";
    document.getElementById("reschedule-time").value =
        button.dataset.rescheduleTime || "";
    document.getElementById("reschedule-duration").value =
        button.dataset.rescheduleDuration || "30";

    document.getElementById("reschedule-reference").textContent =
        `#${String(id).padStart(4, "0")}`;

    document.getElementById("reschedule-current-details").textContent =
        `Patient: ${button.dataset.patientName || "Patient"} · ` +
        `Current appointment: ${button.dataset.rescheduleDate || "—"} ` +
        `at ${button.dataset.rescheduleTime || "—"}. ` +
        "Choose the new schedule below.";

    const dateInput = document.getElementById("reschedule-date");

    if (dateInput) {
        dateInput.min = getLocalDate();
    }

    clearRescheduleFeedback();

    const submitButton = document.getElementById("reschedule-submit");

    if (submitButton) {
        submitButton.disabled = false;
        submitButton.textContent = "Save New Schedule";
    }

    panel.hidden = false;
    panel.scrollIntoView({ behavior: "smooth", block: "start" });
}

function closeRescheduleForm() {
    const panel = document.getElementById("reschedule-panel");

    if (panel) panel.hidden = true;

    activeRescheduleAppointment = null;
    clearRescheduleFeedback();
}

/* -------------------- Submit rescheduling request -------------------- */

async function handleRescheduleSubmit(event) {
    event.preventDefault();

    const id = Number(
        document.getElementById("reschedule-appointment-id")?.value
    );

    const appointmentDate =
        document.getElementById("reschedule-date")?.value || "";

    const startTime =
        document.getElementById("reschedule-time")?.value || "";

    const duration =
        Number(document.getElementById("reschedule-duration")?.value);

    if (!Number.isInteger(id) || id < 1) {
        showRescheduleFeedback("Please select a valid appointment.", "error");
        return;
    }

    if (!appointmentDate || !startTime) {
        showRescheduleFeedback(
            "Please choose a new date and start time.",
            "error"
        );
        return;
    }

    if (
        !Number.isInteger(duration) ||
        duration < 10 ||
        duration > 240 ||
        duration % 5 !== 0
    ) {
        showRescheduleFeedback(
            "Duration must be between 10 and 240 minutes, in multiples of 5.",
            "error"
        );
        return;
    }

    const submitButton = document.getElementById("reschedule-submit");

    if (submitButton) {
        submitButton.disabled = true;
        submitButton.textContent = "Checking availability...";
    }

    clearRescheduleFeedback();

    try {
        const response = await fetch(
            `/api/appointments/${id}/reschedule`,
            {
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify({
                    appointment_date: appointmentDate,
                    start_time: startTime,
                    duration_minutes: duration
                })
            }
        );

        // Read the body ourselves so conflict alternatives aren't lost.
        const data = await response.json();

        if (!response.ok || data.success === false) {
            showRescheduleFeedback(
                data.message || "Unable to reschedule this appointment.",
                "error"
            );

            if (Array.isArray(data.alternatives) && data.alternatives.length) {
                displayRescheduleAlternatives(data.alternatives);
            }

            return;
        }

        showDashboardAlert(
            data.message || "Appointment rescheduled successfully.",
            "success"
        );

        showRescheduleFeedback(
            "The appointment has been updated successfully.",
            "success"
        );

        await loadAppointments();
        await refreshDashboardMetrics();

        // Close the form after the successful refresh.
        closeRescheduleForm();
    } catch (error) {
        console.error("Rescheduling failed:", error);

        showRescheduleFeedback(
            error.message || "Unable to contact the server. Please try again.",
            "error"
        );
    } finally {
        if (submitButton) {
            submitButton.disabled = false;
            submitButton.textContent = "Save New Schedule";
        }
    }
}

/* -------------------- Alternative rescheduling slots -------------------- */

function displayRescheduleAlternatives(alternatives) {
    const feedback = document.getElementById("reschedule-feedback");

    if (!feedback || !Array.isArray(alternatives) || !alternatives.length) {
        return;
    }

    const heading = document.createElement("p");
    heading.textContent = "Try one of these available times:";
    feedback.appendChild(heading);

    alternatives.forEach(slot => {
        if (!slot.start_time) return;

        const button = document.createElement("button");
        button.type = "button";

        const slotDate = slot.appointment_date ||
            document.getElementById("reschedule-date")?.value || "";

        button.textContent = slotDate
            ? `${slotDate} · ${slot.start_time}${slot.end_time ? `–${slot.end_time}` : ""}`
            : slot.start_time;

        button.addEventListener("click", () => {
            const dateInput = document.getElementById("reschedule-date");
            const timeInput = document.getElementById("reschedule-time");

            if (dateInput && slotDate) {
                dateInput.value = slotDate;
            }

            if (timeInput) {
                timeInput.value = slot.start_time;
            }

            showRescheduleFeedback(
                `Selected ${slotDate} at ${slot.start_time}. Select Save New Schedule to confirm.`,
                "success"
            );
        });

        feedback.appendChild(button);
    });
}

/* -------------------- Refresh dashboard statistics -------------------- */

async function refreshDashboardMetrics() {
    try {
        const response = await fetch("/api/stats");
        const data = await readResponse(response);
        const stats = data.stats || data;

        const mappings = {
            "metric-total": stats.total,
            "metric-scheduled": stats.scheduled,
            "metric-today": stats.today,
            "metric-cancelled": stats.cancelled,
            "metric-doctors": stats.doctors_count ?? stats.doctors
        };

        Object.entries(mappings).forEach(([elementId, value]) => {
            const element = document.getElementById(elementId);

            if (element && value !== undefined && value !== null) {
                element.textContent = String(value);
            }
        });
    } catch (error) {
        console.error("Statistics refresh failed:", error);
    }
}

/* -------------------- Legacy booking form support -------------------- */

function initBookingForm() {
    const form = document.getElementById("appointment-form");
    const checkButton = document.getElementById("check-btn");

    form?.addEventListener("submit", handleBookingSubmit);
    checkButton?.addEventListener("click", handleCheckAvailability);
}

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

async function handleBookingSubmit(event) {
    event.preventDefault();

    const form = event.currentTarget;

    const patientName =
        document.getElementById("patient-name")?.value.trim();

    const doctorId =
        document.getElementById("doctor-select")?.value;

    const appointmentDate =
        document.getElementById("appointment-date")?.value;

    const startTime =
        document.getElementById("start-time")?.value;

    const duration =
        document.getElementById("duration-select")?.value;

    const reason =
        document.getElementById("visit-reason")?.value.trim() || "";

    if (!patientName || !doctorId || !appointmentDate || !startTime || !duration) {
        showFeedback("Please complete all required booking fields.", "danger");
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
                reason,
                consultation_type: "in_person",
                address: ""
            })
        });

        const data = await readResponse(response);

        showFeedback(
            data.message || "Appointment booked successfully.",
            "success"
        );

        hideAlternatives();
        form.reset();

        if (data.appointment) {
            addAppointmentToFeedIfToday(data.appointment);
        }
    } catch (error) {
        showFeedback(error.message || "Unable to book appointment.", "danger");
    } finally {
        setLoadingState(false);
    }
}

async function handleCheckAvailability() {
    const doctorId =
        document.getElementById("doctor-select")?.value;

    const appointmentDate =
        document.getElementById("appointment-date")?.value;

    const startTime =
        document.getElementById("start-time")?.value;

    const duration =
        document.getElementById("duration-select")?.value;

    if (!doctorId || !appointmentDate || !startTime || !duration) {
        showFeedback(
            "Please select a doctor, date, time, and duration.",
            "warning"
        );
        return;
    }

    try {
        const params = new URLSearchParams({
            doctor_id: doctorId,
            date: appointmentDate,
            time: startTime,
            duration
        });

        const response = await fetch(`/api/check-availability?${params}`);
        const data = await readResponse(response);

        if (data.available) {
            showFeedback(data.message || "This time is available.", "success");
            hideAlternatives();
        } else {
            showFeedback(data.message || "This time is unavailable.", "danger");

            if (data.alternatives?.length) {
                displayAlternatives(data.alternatives);
            } else {
                hideAlternatives();
            }
        }
    } catch (error) {
        showFeedback(error.message || "Unable to check availability.", "danger");
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
        button.textContent = slot.display || slot.start_time || "Available slot";

        button.addEventListener("click", () => {
            const timeInput = document.getElementById("start-time");

            if (timeInput && slot.start_time) {
                timeInput.value = slot.start_time;

                showFeedback(
                    `Selected ${slot.start_time}. Submit the form to book it.`,
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

    if (!container || !alertBox || !messageElement) {
        window.alert(message);
        return;
    }

    container.classList.remove("hidden");
    alertBox.className = `alert alert-${type}`;
    messageElement.textContent = message;

    container.scrollIntoView({
        behavior: "smooth",
        block: "nearest"
    });
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
    const feed = document.getElementById("today-appointments-list");

    if (!feed || !appointment) return;

    if (
        String(appointment.appointment_date || "").slice(0, 10) !==
        getLocalDate()
    ) {
        return;
    }

    document.getElementById("feed-empty-state")?.remove();

    const item = document.createElement("div");
    item.className = "feed-item";
    item.id = `feed-item-${appointment.id}`;

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

    const time = document.createElement("div");
    time.className = "feed-time";
    time.textContent =
        `${appointment.start_time || ""} – ${appointment.end_time || ""}`;

    item.append(time, details);
    feed.prepend(item);
}
