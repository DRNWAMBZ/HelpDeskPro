const hiddenElements = document.querySelectorAll(".hidden");

const scrollRevealObserver = new IntersectionObserver((entries) => {

    entries.forEach((entry) => {

        if(entry.isIntersecting){

    entry.target.classList.add("show");

    }else{

    entry.target.classList.remove("show");

}

    });

});

hiddenElements.forEach((element) => {

    scrollRevealObserver.observe(element);

});
function animateCounter(elementId, target, suffix, speed){

    const counterElement = document.getElementById(elementId);
    console.log(elementId, counterElement);

    let count = 0;

    const counter = setInterval(() => {

        count++;

        counterElement.textContent = count;

        if(count >= target){

            clearInterval(counter);

            counterElement.textContent = target + suffix;

        }

    },speed);

}
function startCounters(){
animateCounter("ticket-counter",350,"+",8);

animateCounter("satisfaction-counter",98,"%",20);

animateCounter("support-counter",24,"/7",50);

animateCounter("response-counter",5," min",250);
}
const statsSection = document.getElementById("stats");

const statsObserver = new IntersectionObserver((entries, observer) => {

    entries.forEach(entry => {

        if(entry.isIntersecting){

            startCounters();

            observer.unobserve(entry.target);

        }

    });

});

statsObserver.observe(statsSection);
const navbar = document.querySelector(".navbar");

window.addEventListener("scroll", () => {

    if(window.scrollY > 50){

        navbar.classList.add("scrolled");

    }else{

        navbar.classList.remove("scrolled");

    }

});
/* ===========================
   Scroll Progress Bar
=========================== */

const progressBar = document.querySelector(".progress-bar");

window.addEventListener("scroll", () => {

    const scrollTop = window.scrollY;

    const pageHeight =
        document.documentElement.scrollHeight - window.innerHeight;

    const progress = (scrollTop / pageHeight) * 100;

    progressBar.style.width = progress + "%";

});
const footer = document.querySelector("footer");
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
window.addEventListener("load", () => {

    const loader = document.getElementById("loader");

    setTimeout(() => {

        loader.style.opacity = "0";

        loader.style.visibility = "hidden";

    },800);

});