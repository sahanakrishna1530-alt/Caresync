
"use strict";

/* =========================================================
   CareSync - Dashboard, Booking, Filters and Cancellation
   ========================================================= */

let activeDashboardFilter = "ALL";

document.addEventListener("DOMContentLoaded", () => {
    initBookingForm();
    initDoctorSelector();
    initDashboard();
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

    box.className = `alert alert-${type}`;
    messageElement.textContent = message;
    box.classList.remove("hidden");
}

/* -------------------- Dashboard summary cards -------------------- */

function initDashboard() {
    const tableBody = document.getElementById("appointments-tbody");

    // Do not initialize dashboard features on other pages.
    if (!tableBody) return;

    document.querySelectorAll("[data-dashboard-filter]").forEach(card => {
        card.addEventListener("click", () => {
            const filter = card.dataset.dashboardFilter || "ALL";

            activeDashboardFilter = filter;

            const doctor = document.getElementById("filter-doctor");
            const date = document.getElementById("filter-date");
            const status = document.getElementById("filter-status");

            // Summary cards start a new view rather than retaining
            // unrelated filters from a previous selection.
            if (doctor) doctor.value = "";
            if (date) date.value = "";
            if (status) status.value = "ALL";

            if (filter === "SCHEDULED" && status) {
                status.value = "SCHEDULED";
            } else if (filter === "CANCELLED" && status) {
                status.value = "CANCELLED";
            } else if (filter === "TODAY" && date) {
                date.value = getLocalDate();
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

    // Make the first card the initial dashboard view.
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
    const date = document.getElementById("filter-date")?.value || "";
    const status = document.getElementById("filter-status")?.value || "ALL";

    const params = new URLSearchParams();

    if (doctorId) params.set("doctor_id", doctorId);
    if (date) params.set("date", date);
    if (status !== "ALL") params.set("status", status);

    tbody.innerHTML = `
        <tr>
            <td colspan="12" class="text-center">Loading appointments...</td>
        </tr>`;

    try {
        const response = await fetch(`/api/appointments?${params.toString()}`);
        const data = await readResponse(response);

        // Accept either a raw JSON array or an object containing appointments.
        let appointments = Array.isArray(data)
            ? data
            : (data.appointments || data.records || []);

        if (!Array.isArray(appointments)) {
            throw new Error("Unexpected appointment data returned by the server.");
        }

        // Apply the Today card's date filter even if the API ignores date.
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

        showDashboardAlert(error.message, "alert-error");
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

        const price = appointment.price !== null &&
                      appointment.price !== undefined &&
                      appointment.price !== ""
            ? `₹${escapeHtml(appointment.price)}`
            : "—";

        const address = isHomeVisit
            ? escapeHtml(appointment.address || "Not provided")
            : "—";

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

                <td>${escapeHtml(appointment.appointment_date || "—")}</td>

                <td>
                    <span class="time-range-badge">
                        ${escapeHtml(appointment.start_time || "—")}
                        &ndash;
                        ${escapeHtml(appointment.end_time || "—")}
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

                <td>
                    ${isScheduled
                        ? `<button type="button"
                                   class="btn-cancel-small"
                                   data-cancel-id="${id}">Cancel</button>`
                        : '<span class="text-muted text-sm">—</span>'}
                </td>
            </tr>`;
    }).join("");

    // Event delegation also works after the table is redrawn.
    tbody.querySelectorAll("[data-cancel-id]").forEach(button => {
        button.addEventListener("click", () => {
            cancelAppointmentAction(button.dataset.cancelId);
        });
    });
}

/* -------------------- Cancel an appointment -------------------- */

async function cancelAppointmentAction(appointmentId) {
    const id = Number(appointmentId);

    if (!Number.isInteger(id) || id < 1) {
        showDashboardAlert("Invalid appointment ID.", "alert-error");
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
            "alert-success"
        );

        // Refresh the records and statistics from the server so that
        // filters and counts do not become inconsistent.
        await loadAppointments();
        await refreshDashboardMetrics();
    } catch (error) {
        console.error("Cancellation failed:", error);
        showDashboardAlert(error.message || "Cancellation failed.", "alert-error");
    }
}

/* -------------------- Refresh dashboard statistics -------------------- */

async function refreshDashboardMetrics() {
    try {
        const response = await fetch("/api/stats");
        const data = await readResponse(response);

        // Support stats returned directly or inside a stats object.
        const stats = data.stats || data;

        const mappings = {
            "metric-total": stats.total,
            "metric-scheduled": stats.scheduled,
            "metric-today": stats.today,
            "metric-cancelled": stats.cancelled,
            "metric-doctors": stats.doctors_count
        };

        Object.entries(mappings).forEach(([elementId, value]) => {
            const element = document.getElementById(elementId);

            if (element && value !== undefined) {
                element.textContent = String(value);
            }
        });
    } catch (error) {
        // Statistics refresh should not undo a successful cancellation.
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

    const patientName = document.getElementById("patient-name")?.value.trim();
    const doctorId = document.getElementById("doctor-select")?.value;
    const date = document.getElementById("appointment-date")?.value;
    const time = document.getElementById("start-time")?.value;
    const duration = document.getElementById("duration-select")?.value;
    const reason = document.getElementById("visit-reason")?.value.trim() || "";

    if (!patientName || !doctorId || !date || !time || !duration) {
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
                appointment_date: date,
                start_time: time,
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
    const doctorId = document.getElementById("doctor-select")?.value;
    const date = document.getElementById("appointment-date")?.value;
    const time = document.getElementById("start-time")?.value;
    const duration = document.getElementById("duration-select")?.value;

    if (!doctorId || !date || !time || !duration) {
        showFeedback("Please select a doctor, date, time, and duration.", "warning");
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
    const feed = document.getElementById("today-appointments-list");
    if (!feed || !appointment) return;

    if (String(appointment.appointment_date || "").slice(0, 10) !== getLocalDate()) {
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
