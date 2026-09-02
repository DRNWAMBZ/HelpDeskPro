document.addEventListener("DOMContentLoaded", () => {

    const chatPage = document.querySelector("[data-chat-page]");
    const composerForm = document.querySelector(".chat-composer");
    const composer = composerForm?.querySelector("textarea");
    const takenNotice = document.querySelector("[data-chat-taken-notice]");
    const refreshUrl = chatPage?.dataset.chatRefreshUrl;
    const conversationId = chatPage?.dataset.chatConversationId;
    const draftStorageKey = conversationId
        ? `helpdeskpro-chat-draft-${conversationId}`
        : null;
    let chatTaken = false;
    let lastSignature = null;
    let updateCheckInFlight = false;

    if (!chatPage) {
        return;
    }

    const saveDraft = () => {
        if (!composer || !draftStorageKey) {
            return;
        }

        if (composer.value.trim()) {
            window.sessionStorage.setItem(draftStorageKey, composer.value);
        } else {
            window.sessionStorage.removeItem(draftStorageKey);
        }
    };

    if (composer && draftStorageKey) {
        const savedDraft = window.sessionStorage.getItem(draftStorageKey);

        if (savedDraft) {
            composer.value = savedDraft;
        }

        composer.addEventListener("input", saveDraft);
        composerForm.addEventListener("submit", () => {
            window.sessionStorage.removeItem(draftStorageKey);
        });
        window.addEventListener("beforeunload", saveDraft);
    }

    const showTakenNotice = () => {

        chatTaken = true;
        composerForm?.remove();

        if (takenNotice) {
            takenNotice.hidden = false;
        }
    };

    const checkForChatUpdates = async () => {

        if (!refreshUrl || chatTaken || updateCheckInFlight) {
            return;
        }

        updateCheckInFlight = true;

        try {
            const endpoint = new URL(refreshUrl, window.location.origin);

            if (conversationId) {
                endpoint.searchParams.set("conversation", conversationId);
            }

            const response = await fetch(endpoint, {
                credentials: "same-origin",
            });

            if (!response.ok) {
                return;
            }

            const updateState = await response.json();

            if (updateState.active_state === "taken") {
                showTakenNotice();
                return;
            }

            const currentSignature = JSON.stringify(updateState.signature);

            if (lastSignature === null) {
                lastSignature = currentSignature;
                return;
            }

            if (currentSignature !== lastSignature) {
                const hasUnsavedDraft = composer && composer.value.trim().length > 0;

                if (hasUnsavedDraft) {
                    return;
                }

                window.location.reload();
            }
        } catch (_) {
            // A manual browser refresh remains available if the update check fails.
        } finally {
            updateCheckInFlight = false;
        }
    };

    checkForChatUpdates();

    window.setInterval(() => {

        if (document.visibilityState === "visible") {
            checkForChatUpdates();
        }

    }, 5000);

});
