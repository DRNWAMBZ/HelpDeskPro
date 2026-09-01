document.addEventListener("DOMContentLoaded", function () {

    // =====================================================
    // PASSWORD VISIBILITY
    // =====================================================

    document
        .querySelectorAll("[data-password-toggle]")
        .forEach(function (button) {

            button.addEventListener("click", function () {

                const inputId =
                    button.getAttribute("data-password-toggle");

                const input =
                    document.getElementById(inputId);

                if (!input) {
                    return;
                }

                const icon =
                    button.querySelector("i");

                const showingPassword =
                    input.type === "text";

                input.type =
                    showingPassword
                        ? "password"
                        : "text";

                button.setAttribute(
                    "aria-pressed",
                    showingPassword
                        ? "false"
                        : "true"
                );

                button.setAttribute(
                    "aria-label",
                    showingPassword
                        ? "Show password"
                        : "Hide password"
                );

                if (icon) {

                    icon.classList.toggle(
                        "fa-eye",
                        showingPassword
                    );

                    icon.classList.toggle(
                        "fa-eye-slash",
                        !showingPassword
                    );
                }
            });
        });


    // =====================================================
    // DELETE USER CONFIRMATION
    // =====================================================

    document
        .querySelectorAll(".admin-delete-user-form")
        .forEach(function (form) {

            form.addEventListener("submit", function (event) {

                const username =
                    form.dataset.username || "this user";

                const confirmed = window.confirm(
                    "Permanently delete " +
                    username +
                    "'s account?\n\n" +
                    "This action cannot be undone."
                );

                if (!confirmed) {
                    event.preventDefault();
                }
            });
        });

});