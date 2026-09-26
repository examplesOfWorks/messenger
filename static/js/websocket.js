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

presenceSocket.onopen = function () {
    console.log("Presence WebSocket подключен");
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