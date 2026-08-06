/* =====================================
   Scroll Reveal Animations
===================================== */

const hiddenElements = document.querySelectorAll(".hidden");

const scrollRevealObserver = new IntersectionObserver((entries) => {

    entries.forEach((entry) => {

        if (entry.isIntersecting) {

            entry.target.classList.add("show");

        } else {

            entry.target.classList.remove("show");

        }

    });

});

hiddenElements.forEach((element) => {

    scrollRevealObserver.observe(element);

});


/* =====================================
   Statistics Counter
===================================== */

function animateCounter(elementId, target, suffix, speed) {

    const counterElement = document.getElementById(elementId);

    let count = 0;

    const counter = setInterval(() => {

        count++;

        counterElement.textContent = count;

        if (count >= target) {

            clearInterval(counter);

            counterElement.textContent = target + suffix;

        }

    }, speed);

}

function startCounters() {

    animateCounter("ticket-counter", 350, "+", 8);

    animateCounter("satisfaction-counter", 98, "%", 20);

    animateCounter("support-counter", 24, "/7", 50);

    animateCounter("response-counter", 5, " min", 250);

}

const statsSection = document.getElementById("stats");

const statsObserver = new IntersectionObserver((entries, observer) => {

    entries.forEach((entry) => {

        if (entry.isIntersecting) {

            startCounters();

            observer.unobserve(entry.target);

        }

    });

});

statsObserver.observe(statsSection);


/* =====================================
   Sticky Navigation Bar
===================================== */

const navbar = document.querySelector(".navbar");

window.addEventListener("scroll", () => {

    if (window.scrollY > 50) {

        navbar.classList.add("scrolled");

    } else {

        navbar.classList.remove("scrolled");

    }

});


/* =====================================
   Scroll Progress Bar
===================================== */

const progressBar = document.querySelector(".progress-bar");

window.addEventListener("scroll", () => {

    const scrollTop = window.scrollY;

    const pageHeight =
        document.documentElement.scrollHeight - window.innerHeight;

    const progress = (scrollTop / pageHeight) * 100;

    progressBar.style.width = progress + "%";

});


/* =====================================
   Back To Top Button
===================================== */

const backToTop = document.getElementById("backToTop");

if (backToTop) {

    window.addEventListener("scroll", () => {

        if (window.scrollY > 400) {

            backToTop.classList.add("show");

        } else {

            backToTop.classList.remove("show");

        }

    });

    backToTop.addEventListener("click", () => {

        window.scrollTo({

            top: 0,

            behavior: "smooth"

        });

    });

}

/* =====================================
   Mobile Navigation
===================================== */

const hamburger = document.querySelector(".hamburger");
const mobileMenu = document.getElementById("mobileMenu");

if (hamburger && mobileMenu) {

    // Open / Close menu
    hamburger.addEventListener("click", () => {

        mobileMenu.classList.toggle("active");

        if (mobileMenu.classList.contains("active")) {

            hamburger.innerHTML = "✕";

        } else {

            hamburger.innerHTML = "☰";

        }

    });
}
    // Close menu after clicking a link
    const mobileLinks = mobileMenu.querySelectorAll("a");

    mobileLinks.forEach((link) => {

        link.addEventListener("click", () => {

            mobileMenu.classList.remove("active");

            hamburger.innerHTML = "☰";

        });

    });

    // Close menu when clicking outside
    document.addEventListener("click", (e) => {

        if (
            !mobileMenu.contains(e.target) &&
            !hamburger.contains(e.target)
        ) {

            mobileMenu.classList.remove("active");

            hamburger.innerHTML = "☰";

        }

    });
 // Close menu when resizing to desktop
    window.addEventListener("resize", () => {

        if (window.innerWidth > 768) {

            mobileMenu.classList.remove("active");

            hamburger.innerHTML = "☰";

    }

});

/* =====================================
   Page Loader
===================================== */

window.addEventListener("load", () => {

    const loader = document.getElementById("loader");

    setTimeout(() => {

        loader.style.opacity = "0";

        loader.style.visibility = "hidden";

    }, 800);

});
/* =====================================
   Close Mobile Menu on Resize
===================================== */
window.addEventListener("resize", () => {

    if (window.innerWidth > 768) {

        navLinks.classList.remove("active");
        hamburger.classList.remove("active");

    }
});