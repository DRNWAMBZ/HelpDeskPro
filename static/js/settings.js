/* =========================================================
   SETTINGS PASSWORD VISIBILITY
   ========================================================= */

document.addEventListener("DOMContentLoaded", () => {

    const passwordToggles = document.querySelectorAll(
        ".settings-password-toggle",
    );

    passwordToggles.forEach((toggle) => {

        const passwordInput = document.getElementById(
            toggle.getAttribute("aria-controls"),
        );

        const icon = toggle.querySelector("i");

        if (!passwordInput || !icon) {
            return;
        }

        toggle.addEventListener("click", () => {

            const passwordIsHidden = passwordInput.type === "password";

            passwordInput.type = passwordIsHidden ? "text" : "password";

            icon.classList.toggle("fa-eye", !passwordIsHidden);
            icon.classList.toggle("fa-eye-slash", passwordIsHidden);

            toggle.setAttribute("aria-pressed", String(passwordIsHidden));

            const passwordLabel = toggle.dataset.passwordLabel || "password";

            toggle.setAttribute(
                "aria-label",
                `${passwordIsHidden ? "Hide" : "Show"} ${passwordLabel}`,
            );

        });

    });

});
