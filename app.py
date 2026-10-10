```html
<script>
(() => {
    const form = document.getElementById("booking-form");
    const typeSelect = document.getElementById("consultation-type");
    const addressField = document.getElementById("address-field");
    const addressInput = document.getElementById("home-address");
    const emergencyInput = document.getElementById("is-emergency");
    const priceLabel = document.getElementById("consultation-price");
    const consultationName = document.getElementById("consultation-name");
    const message = document.getElementById("booking-message");
    const submitButton = document.getElementById("submit-button");
    const availabilityButton = document.getElementById("check-availability");

    const prices = {{ consultation_prices | tojson }};
    const names = {{ {
        "video": "Video Visit",
        "phone": "Phone Call",
        "in_person": "In Person",
        "home": "Home Visit"
    } | tojson }};

    let busy = false;

    function showMessage(text, type = "info") {
        message.textContent = text;
        message.style.color =
            type === "error" ? "#b42318" :
            type === "success" ? "#087f8c" :
            "#20323a";
    }

    async function readResponse(response) {
        const text = await response.text();
        if (!text) return {};

        try {
            return JSON.parse(text);
        } catch {
            throw new Error(
                "Invalid server response. Check the Flask terminal."
            );
        }
    }

    function updateConsultation() {
        const type = typeSelect.value;
        const homeVisit = type === "home";

        addressField.hidden = !homeVisit;
        addressInput.required = homeVisit;

        if (!homeVisit) addressInput.value = "";

        if (Object.prototype.hasOwnProperty.call(prices, type)) {
            priceLabel.textContent = "Consultation fee: ₹" + prices[type];
            consultationName.textContent = names[type];
        } else {
            priceLabel.textContent = "Price unavailable";
            consultationName.textContent = "Select a consultation";
        }
    }

    function getBookingData() {
        return {
            patient_name: document.getElementById("patient-name").value.trim(),
            doctor_id: document.getElementById("doctor-id").value,
            appointment_date: document.getElementById("appointment-date").value,
            start_time: document.getElementById("start-time").value,
            duration_minutes: Number(document.getElementById("duration").value),
            reason: document.getElementById("reason").value.trim(),
            consultation_type: typeSelect.value,
            address: typeSelect.value === "home"
                ? addressInput.value.trim()
                : "",
            is_emergency: emergencyInput.checked
        };
    }

    function validateSlot(data) {
        const fields = [
            ["doctor-id", "Please select a doctor."],
            ["appointment-date", "Please select an appointment date."],
            ["start-time", "Please select a start time."],
            ["duration", "Please select a duration."]
        ];

        for (const [id, errorText] of fields) {
            const field = document.getElementById(id);

            if (!field.value || !field.checkValidity()) {
                showMessage(errorText, "error");
                field.focus();
                return false;
            }
        }

        if (!Number.isInteger(data.duration_minutes) ||
            data.duration_minutes <= 0) {
            showMessage("Please select a valid duration.", "error");
            return false;
        }

        return true;
    }

    function formatAlternative(slot) {
        if (typeof slot === "string") return slot;
        if (!slot || typeof slot !== "object") return "Alternative slot";
        if (slot.display) return slot.display;

        const date = slot.appointment_date || "";
        const start = slot.start_time || "";
        const end = slot.end_time || "";

        if (date && start && end) return `${date}, ${start}–${end}`;
        if (date && start) return `${date}, ${start}`;
        if (start && end) return `${start}–${end}`;

        return start || date || "Alternative slot";
    }

    typeSelect.addEventListener("change", updateConsultation);
    updateConsultation();

    // CHECK AVAILABILITY
    availabilityButton.addEventListener("click", async () => {
        if (busy) return;

        const data = getBookingData();
        if (!validateSlot(data)) return;

        busy = true;
        availabilityButton.disabled = true;
        submitButton.disabled = true;
        showMessage("Checking availability...");

        try {
            const params = new URLSearchParams({
                doctor_id: data.doctor_id,
                date: data.appointment_date,
                time: data.start_time,
                duration: String(data.duration_minutes)
            });

            const response = await fetch(
                "/api/check-availability?" + params.toString(),
                { headers: { "Accept": "application/json" } }
            );

            const result = await readResponse(response);

            if (!response.ok || result.success !== true) {
                showMessage(
                    result.message || result.error ||
                    `Availability check failed (HTTP ${response.status}).`,
                    "error"
                );
                return;
            }

            if (typeof result.available !== "boolean") {
                showMessage(
                    "The server did not return an availability status.",
                    "error"
                );
                return;
            }

            if (result.available) {
                showMessage(
                    result.message || "This time is available.",
                    "success"
                );
            } else {
                let text = result.message || "This time is unavailable.";

                if (Array.isArray(result.alternatives) &&
                    result.alternatives.length) {
                    text += "\nSuggested alternatives: " +
                        result.alternatives.map(formatAlternative).join("; ");
                }

                showMessage(text, "error");
            }
        } catch (error) {
            console.error("Availability error:", error);
            showMessage(error.message || "Unable to check availability.", "error");
        } finally {
            busy = false;
            availabilityButton.disabled = false;
            submitButton.disabled = false;
        }
    });

    // CONFIRM APPOINTMENT
    form.addEventListener("submit", async (event) => {
        event.preventDefault();

        if (busy || !form.reportValidity()) return;

        const data = getBookingData();

        if (data.patient_name.length < 2) {
            showMessage("Please enter the patient's name.", "error");
            document.getElementById("patient-name").focus();
            return;
        }

        if (!validateSlot(data)) return;

        if (data.consultation_type === "home" && !data.address) {
            showMessage("Please enter the home visit address.", "error");
            addressInput.focus();
            return;
        }

        busy = true;
        submitButton.disabled = true;
        availabilityButton.disabled = true;
        showMessage("Submitting appointment...");

        try {
            const response = await fetch("/api/appointments", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "Accept": "application/json"
                },
                body: JSON.stringify(data)
            });

            const result = await readResponse(response);

            if (!response.ok || result.success !== true) {
                showMessage(
                    result.message || result.error ||
                    `Booking failed (HTTP ${response.status}).`,
                    "error"
                );
                return;
            }

            showMessage("Appointment booked successfully. Opening dashboard...", "success");
            window.location.assign("/dashboard");
        } catch (error) {
            console.error("Booking error:", error);
            showMessage(
                error.message || "Could not contact the server. Check that CareSync is running.",
                "error"
            );
        } finally {
            busy = false;
            submitButton.disabled = false;
            availabilityButton.disabled = false;
        }
    });
})();
</script>
```
