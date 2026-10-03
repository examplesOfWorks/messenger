const messagesContainer =
    document.getElementById("messages-container");

const messageForm =
    document.getElementById("message-form");

// Отправка сообщения
if (messageForm) {
    messageForm.addEventListener("submit", (event) => {
        event.preventDefault();
        
        const text = messageInput.value.trim();
        
        if (!text) {
            return;
        }
        
        if (presenceSocket.readyState !== WebSocket.OPEN) {
            return;
        }
        
        presenceSocket.send(
            JSON.stringify({
                type: "send_message",
                conversation_id: conversationId,
                text: text,
            })
        );
        
        messageInput.value = "";
    });
}

// Получение сообщений
presenceSocket.addEventListener("message", (event) => {
    const data = JSON.parse(event.data);

    if (data.type === "new_message") {
        const message = data.message;

        const isOwnMessage =
            Number(message.sender_id) === currentUserId;

        const isCurrentConversation =
            typeof conversationId !== "undefined" &&
            message.conversation_id === String(conversationId);

        if (!isOwnMessage && !isCurrentConversation) {
            updateUnreadCount(
                message.conversation_id,
                1
            );
        }

        addMessage(message);

        if (!isOwnMessage && isCurrentConversation) {
            markMessageAsRead(message);
        }
    }
});

function markMessageAsRead(message) {
    if (presenceSocket.readyState !== WebSocket.OPEN) {
        return;
    }

    presenceSocket.send(
        JSON.stringify({
            type: "message_read",
            conversation_id: message.conversation_id,
            message_id: Number(message.id),
        })
    );
}

// Добавление сообщения
function addMessage(message) {
    if (
        message.conversation_id !==
        String(conversationId)
    ) {
        return;
    }

    // Не добавляем сообщение повторно
    if (
        messagesContainer.querySelector(
            `[data-message-id="${message.id}"]`
        )
    ) {
        return;
    }

    
    // Удаляем надпись "Сообщений пока нет"
     const emptyMessages = messagesContainer.querySelector(
        ".empty-messages"
    );

    if (emptyMessages) {
        emptyMessages.remove();
    }


    const isOwnMessage =
        Number(message.sender_id) === currentUserId;

    const templateId = isOwnMessage
        ? "own-message-template"
        : "other-message-template";

    const template =
        document.getElementById(templateId);

    if (!template) {
        return;
    }

    const element =
        template.content.cloneNode(true);

    const wrapper =
        element.querySelector(".message-wrapper");

    wrapper.dataset.messageId =
        message.id;

    wrapper.dataset.messageTime =
        message.created_at;

    wrapper.dataset.senderId =
        message.sender_id;

    element.querySelector(
        ".message-text"
    ).textContent = message.text;

    const time =
        new Date(
            message.created_at
        ).toLocaleTimeString(
            undefined,
            {
                hour: "2-digit",
                minute: "2-digit",
            }
        );

    element.querySelector(".message-time").textContent = time;

    const readStatus = element.querySelector(
        ".message-read-status"
    );
    
    if (readStatus) {
        readStatus.dataset.messageId = message.id;
    
        if (
            pendingReadMessages.has(String(message.id))
        ) {
            readStatus.textContent = "✓✓";
            pendingReadMessages.delete(String(message.id));
        }
    }

    messagesContainer.appendChild(element);

    messagesContainer.scrollTop =
        messagesContainer.scrollHeight;
}

function updateUnreadCount(conversationId, increment = 1) {
    const badge = document.querySelector(
        `.unread-count[data-conversation-id="${conversationId}"]`
    );

    if (!badge) {
        return;
    }

    const currentCount = Number(badge.textContent) || 0;
    const newCount = currentCount + increment;

    badge.textContent = newCount;
    badge.style.display = newCount > 0 ? "inline-block" : "none";
}

function clearUnreadCount(conversationId) {
    const badge = document.querySelector(
        `.unread-count[data-conversation-id="${conversationId}"]`
    );

    if (!badge) {
        return;
    }

    badge.textContent = "0";
    badge.style.display = "none";
}

// Добавление дат
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

if (typeof conversationId !== "undefined") {
    clearUnreadCount(conversationId);
}

requestAnimationFrame(() => {

    const messagesContainer = document.getElementById("messages-container");

        if (messagesContainer) {
            messagesContainer.scrollTop = messagesContainer.scrollHeight;
        }
});