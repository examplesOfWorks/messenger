const messages = document.querySelectorAll(".message-wrapper");

let previousDate = null;

messages.forEach(messageElement => {
    const date = new Date(
        messageElement.dataset.messageTime
    );

    const localDate = date.toLocaleDateString(undefined, {
        day: "numeric",
        month: "long",
    });

    const localDateKey = date.toLocaleDateString();

    const time = date.toLocaleTimeString(undefined, {
        hour: "2-digit",
        minute: "2-digit",
    });

    const timeElement = messageElement.querySelector(
        ".message-time"
    );

    if (timeElement) {
        timeElement.textContent = time;
    }

    if (localDateKey !== previousDate) {
        const dateElement = document.createElement("div");

        dateElement.className = "message-date";
        dateElement.textContent = localDate;

        messageElement.before(dateElement);

        previousDate = localDateKey;
    }
});

requestAnimationFrame(() => {

    const messagesContainer = document.getElementById("messages-container");

        if (messagesContainer) {
            messagesContainer.scrollTop = messagesContainer.scrollHeight;
        }
});