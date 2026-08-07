/* ==========================================
   Register Page JavaScript
========================================== */

/* ==========================================
   Password Show / Hide
========================================== */

const passwordInput = document.getElementById("password");
const togglePassword = document.getElementById("togglePassword");

if (passwordInput && togglePassword) {

    togglePassword.addEventListener("click", () => {

        if (passwordInput.type === "password") {

            passwordInput.type = "text";

        } else {

            passwordInput.type = "password";

        }
        togglePassword.classList.toggle("fa-eye");
            togglePassword.classList.toggle("fa-eye-slash");

    });

}


/* ==========================================
   Confirm Password Validation
========================================== */

const confirmPasswordInput = document.getElementById("confirmPassword");
const toggleConfirmPassword = document.getElementById("toggleConfirmPassword");

if (confirmPasswordInput && toggleConfirmPassword) {
         
     console.log("Confirm eye clicked")
     
    toggleConfirmPassword.addEventListener("click", () => {

        if (confirmPasswordInput.type === "password") {

            confirmPasswordInput.type = "text";

        } else {

            confirmPasswordInput.type = "password";

        }

        toggleConfirmPassword.classList.toggle("fa-eye");
        toggleConfirmPassword.classList.toggle("fa-eye-slash");

    });

}