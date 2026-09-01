document.addEventListener("DOMContentLoaded", () => {

    const chatPage = document.querySelector("[data-chat-page]");
    const composerForm = document.querySelector(".chat-composer");
    const composer = composerForm?.querySelector("textarea");
    const takenNotice = document.querySelector("[data-chat-taken-notice]");
    const availabilityUrl = chatPage?.dataset.chatAvailabilityUrl;
    let chatTaken = false;

    if (!chatPage) {
        return;
    }

    const showTakenNotice = () => {

        chatTaken = true;
        composerForm?.remove();

        if (takenNotice) {
            takenNotice.hidden = false;
        }
    };

    const checkChatAvailability = async () => {

        if (!availabilityUrl || chatTaken) {
            return;
        }

        try {
            const response = await fetch(availabilityUrl, {
                credentials: "same-origin",
            });

            if (!response.ok) {
                return;
            }

            const availability = await response.json();

            if (availability.state === "taken") {
                showTakenNotice();
            }
        } catch (_) {
            // The regular page refresh remains the fallback if polling fails.
        }
    };

    checkChatAvailability();

    window.setInterval(() => {

        checkChatAvailability();

        if (
            document.visibilityState === "visible"
            && !chatTaken
            && document.activeElement !== composer
        ) {
            window.location.reload();
        }

    }, 5000);

});
