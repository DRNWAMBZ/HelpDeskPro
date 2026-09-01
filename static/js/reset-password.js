document.addEventListener("DOMContentLoaded", () => {

    document.querySelectorAll("[data-password-toggle]").forEach((toggle) => {

        const input = document.getElementById(
            toggle.dataset.passwordToggle,
        );
        const icon = toggle.querySelector("i");

        if (!input || !icon) {
            return;
        }

        toggle.addEventListener("click", () => {

            const isHidden = input.type === "password";

            input.type = isHidden ? "text" : "password";
            icon.classList.toggle("fa-eye", !isHidden);
            icon.classList.toggle("fa-eye-slash", isHidden);
            toggle.setAttribute("aria-pressed", String(isHidden));
            toggle.setAttribute(
                "aria-label",
                `${isHidden ? "Hide" : "Show"} ${input.placeholder.toLowerCase()}`,
            );

        });

    });

});
