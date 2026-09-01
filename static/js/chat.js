document.addEventListener("DOMContentLoaded", () => {

    const chatPage = document.querySelector("[data-chat-page]");
    const composer = document.querySelector(".chat-composer textarea");

    if (!chatPage) {
        return;
    }

    window.setInterval(() => {

        if (
            document.visibilityState === "visible"
            && document.activeElement !== composer
        ) {
            window.location.reload();
        }

    }, 6000);

});
