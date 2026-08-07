// ===========================
// Password Show / Hide
// ===========================

const passwordInput = document.getElementById("password");
const togglePassword = document.getElementById("togglePassword");
const icon = togglePassword.querySelector("i");

if (passwordInput && togglePassword) {

    togglePassword.addEventListener("click", () => {

        if (passwordInput.type === "password") {

            passwordInput.type = "text";
            icon.classList.replace("fa-eye", "fa-eye-slash");

        } else {

            passwordInput.type = "password";
            icon.classList.replace("fa-eye-slash", "fa-eye");

        }

    });

}