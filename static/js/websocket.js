const presenceSocket = new WebSocket(`ws://${window.location.host}/ws/${ currentUserId }`); 

function setOnline(userId) {
    const statusElement = document.getElementById(
        `online-status-${userId}`
    );

    const indicatorElement = document.getElementById(
        `online-indicator-${userId}`
    );

    if (!indicatorElement) {
        return;
    }

    if (statusElement) {
        statusElement.textContent = "в сети";
    }

    indicatorElement.classList.remove("bg-secondary");
    indicatorElement.classList.add("bg-success");
}

function setOffline(userId) {
    const statusElement = document.getElementById(
        `online-status-${userId}`
    );

    const indicatorElement = document.getElementById(
        `online-indicator-${userId}`
    );

    if (!indicatorElement) {
        return;
    }

    if (statusElement) {
        statusElement.textContent = "не в сети";
    }

    indicatorElement.classList.remove("bg-success");
    indicatorElement.classList.add("bg-secondary");
}


const messageInput = document.getElementById("message-input");

let typingTimeout;


if (messageInput && typeof conversationId !== "undefined") {
    messageInput.addEventListener("input", function () {

        if (presenceSocket.readyState !== WebSocket.OPEN) {
            return;
        }
        
        presenceSocket.send(JSON.stringify({
            type: "typing",
            conversation_id: conversationId,
            is_typing: true,
        }));

        clearTimeout(typingTimeout);

        typingTimeout = setTimeout(() => {      

            presenceSocket.send(JSON.stringify({
                type: "typing",
                conversation_id: conversationId,
                is_typing: false,
            }));

        }, 1000);
    });
}

function markMessagesAsRead() {
    if (typeof conversationId === "undefined") {
        return;
    }

    if (presenceSocket.readyState !== WebSocket.OPEN) {
        return;
    }

    const messages = document.querySelectorAll(".message-wrapper");

    messages.forEach(message => {

        const senderId = Number(
            message.dataset.senderId
        );

        if (senderId === currentUserId) {
            return;
        }

        const messageId =
            message.dataset.messageId;

        presenceSocket.send(JSON.stringify({
            type: "message_read",
            conversation_id: conversationId,
            message_id: Number(messageId),
        }));

    });
}

presenceSocket.onopen = function () {

    console.log("Presence WebSocket подключен");

    markMessagesAsRead();
};

presenceSocket.onmessage = function (event) {
    const data = JSON.parse(event.data);

    console.log("Presence event:", data);

    if (data.type === "online_users") {
        data.user_ids.forEach(userId => {
            setOnline(userId);
        });

        return;
    }

    if (data.type === "user_status") {
        if (data.status === "online") {
            setOnline(data.user_id);
        }

        if (data.status === "offline") {
            setOffline(data.user_id);
        }
    }

    if (data.type === "typing") {

        if (
            data.conversation_id !== conversationId
        ) {
            return;
        }
    
        const typingIndicator =
            document.getElementById(
                "typing-indicator"
            );
    
        if (!typingIndicator) {
            return;
        }
    
        typingIndicator.style.display =
            data.is_typing
                ? "block"
                : "none";
    }

    if (data.type === "message_read") {

        const statusElement =
            document.querySelector(
                `.message-read-status[data-message-id="${data.message_id}"]`
            );
    
        if (!statusElement) {
            return;
        }
    
        statusElement.textContent = "✓✓";
    }
};


presenceSocket.onclose = function () {
    console.log("Presence WebSocket отключен");
};


presenceSocket.onerror = function (error) {
    console.error(
        "Presence WebSocket ошибка:",
        error
    );
};