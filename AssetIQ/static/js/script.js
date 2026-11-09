
// --------------------------------------------------
// ASSETIQ FRONTEND APPLICATION
// --------------------------------------------------

let assetsData = [];
let employeesData = [];
let maintenanceData = [];

let conversationHistory = [];


// --------------------------------------------------
// PAGE NAVIGATION
// --------------------------------------------------

const pageNames = {
    overview: "Overview",
    assets: "Asset Inventory",
    employees: "Employees",
    maintenance: "Maintenance",
    assistant: "AI Assistant"
};


function showPage(pageName) {

    document.querySelectorAll(".page-section").forEach(page => {
        page.classList.remove("active");
    });

    document.querySelectorAll(".nav-item").forEach(button => {
        button.classList.remove("active");
    });

    const selectedPage = document.getElementById(pageName + "Page");

    if (selectedPage) {
        selectedPage.classList.add("active");
    }

    const selectedButton = document.querySelector(
        `.nav-item[data-page="${pageName}"]`
    );

    if (selectedButton) {
        selectedButton.classList.add("active");
    }

    document.getElementById("pageTitle").textContent = pageNames[pageName];
    document.getElementById("pageBreadcrumb").textContent = pageNames[pageName];

    document.getElementById("sidebar").classList.remove("open");
}


document.querySelectorAll(".nav-item").forEach(button => {
    button.addEventListener("click", () => {
        showPage(button.dataset.page);
    });
});


document.getElementById("mobileMenu").addEventListener("click", () => {
    document.getElementById("sidebar").classList.toggle("open");
});


// --------------------------------------------------
// HELPER FUNCTIONS
// --------------------------------------------------

function escapeHTML(value) {

    return String(value ?? "").replace(/[&<>"']/g, character => ({
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#039;"
    })[character]);

}


function statusBadge(status) {

    const classes = {
        "Assigned": "status-assigned",
        "Available": "status-available",
        "Maintenance": "status-maintenance",
        "Under Maintenance": "status-maintenance",
        "In Progress": "status-progress",
        "Open": "status-progress",
        "Resolved": "status-available",
        "Retired": ""
    };

    const className = classes[status] || "";

    return `<span class="status-pill ${className}">${escapeHTML(status)}</span>`;
}


async function fetchJSON(url) {

    const response = await fetch(url);

    if (!response.ok) {
        throw new Error(`Unable to load ${url}: HTTP ${response.status}`);
    }

    return response.json();
}


// --------------------------------------------------
// DASHBOARD
// --------------------------------------------------

async function loadDashboard() {

    const data = await fetchJSON("/api/dashboard");

    document.getElementById("totalAssets").textContent = data.total_assets;
    document.getElementById("assignedAssets").textContent = data.assigned;
    document.getElementById("availableAssets").textContent = data.available;
    document.getElementById("maintenanceAssets").textContent = data.maintenance;

    // Asset category chart
    const chart = document.getElementById("categoryChart");

    chart.innerHTML = "";

    const categories = Object.entries(data.categories || {});
    const maximum = Math.max(...categories.map(item => item[1]), 1);

    categories.forEach(([name, count]) => {

        const percentage = (count / maximum) * 100;

        chart.innerHTML += `
            <div class="category-row">
                <span>${escapeHTML(name)}</span>

                <div class="category-track">
                    <div class="category-fill"
                         style="width: ${percentage}%"></div>
                </div>

                <span class="category-value">${count}</span>
            </div>
        `;

    });

    // Recent assets table
    const recentBody = document.getElementById("recentAssetsBody");

    recentBody.innerHTML = (data.recent_assets || []).map(asset => {

        return `
            <tr>
                <td class="asset-id">${escapeHTML(asset.id)}</td>
                <td class="asset-name">${escapeHTML(asset.name)}</td>
                <td>${escapeHTML(asset.category)}</td>
                <td>${escapeHTML(asset.employee || "Unassigned")}</td>
                <td>${statusBadge(asset.status)}</td>
            </tr>
        `;

    }).join("");

}


// --------------------------------------------------
// ASSET INVENTORY
// --------------------------------------------------

function renderAssets(search = "") {

    const filtered = assetsData.filter(asset => {

        const content = [
            asset.id,
            asset.name,
            asset.category,
            asset.department,
            asset.status,
            asset.employee
        ].join(" ").toLowerCase();

        return content.includes(search.toLowerCase());

    });

    document.getElementById("assetCount").textContent =
        `${filtered.length} assets`;

    const body = document.getElementById("assetsTableBody");

    body.innerHTML = filtered.map(asset => {

        return `
            <tr>
                <td class="asset-id">${escapeHTML(asset.id)}</td>
                <td class="asset-name">${escapeHTML(asset.name)}</td>
                <td>${escapeHTML(asset.category)}</td>
                <td>${escapeHTML(asset.department || "—")}</td>
                <td>${escapeHTML(asset.employee || "Unassigned")}</td>
                <td>${statusBadge(asset.status)}</td>
            </tr>
        `;

    }).join("");

}


document.getElementById("assetSearch").addEventListener("input", event => {
    renderAssets(event.target.value);
});


// --------------------------------------------------
// EMPLOYEE DIRECTORY
// --------------------------------------------------

function renderEmployees(search = "") {

    const filtered = employeesData.filter(employee => {

        const content = [
            employee.id,
            employee.name,
            employee.department,
            employee.email
        ].join(" ").toLowerCase();

        return content.includes(search.toLowerCase());

    });

    document.getElementById("employeeCount").textContent =
        `${filtered.length} employees`;

    const body = document.getElementById("employeesTableBody");

    body.innerHTML = filtered.map(employee => {

        const assignedCount = assetsData.filter(
            asset => asset.employee_id === employee.id
        ).length;

        return `
            <tr>
                <td class="asset-id">${escapeHTML(employee.id)}</td>
                <td class="asset-name">${escapeHTML(employee.name)}</td>
                <td>${escapeHTML(employee.department || "—")}</td>
                <td>${escapeHTML(employee.email || "—")}</td>
                <td>${assignedCount}</td>
            </tr>
        `;

    }).join("");

}


document.getElementById("employeeSearch").addEventListener("input", event => {
    renderEmployees(event.target.value);
});


// --------------------------------------------------
// MAINTENANCE TABLE
// --------------------------------------------------

function renderMaintenance() {

    const body = document.getElementById("maintenanceTableBody");

    body.innerHTML = maintenanceData.map(record => {

        return `
            <tr>
                <td class="asset-id">${escapeHTML(record.id)}</td>
                <td>${escapeHTML(record.asset)}</td>
                <td>${escapeHTML(record.issue)}</td>
                <td>${escapeHTML(record.date)}</td>
                <td>${statusBadge(record.status)}</td>
            </tr>
        `;

    }).join("");

}


// --------------------------------------------------
// DATABASE CONNECTION INDICATOR
// --------------------------------------------------

async function checkDatabaseStatus() {

    const assistantStatus = document.querySelector(
        ".chat-heading .status-dot"
    );

    const assistantDescription = document.querySelector(
        ".chat-heading p"
    );

    try {

        const response = await fetch("/health");
        const data = await response.json();

        if (response.ok && data.database === "connected") {

            if (assistantStatus) {
                assistantStatus.style.background = "#22c55e";
            }

            if (assistantDescription) {
                assistantDescription.textContent = "MySQL database connected";
            }

        } else {

            if (assistantStatus) {
                assistantStatus.style.background = "#ef4444";
            }

            if (assistantDescription) {
                assistantDescription.textContent = "MySQL database disconnected";
            }

        }

    } catch (error) {

        console.error("Database status error:", error);

        if (assistantDescription) {
            assistantDescription.textContent = "Database connection unavailable";
        }

    }

}


// --------------------------------------------------
// LOAD ALL APPLICATION DATA
// --------------------------------------------------

async function initializeApplication() {

    try {

        const [assets, employees, maintenance] = await Promise.all([
            fetchJSON("/api/assets"),
            fetchJSON("/api/employees"),
            fetchJSON("/api/maintenance")
        ]);

        assetsData = assets;
        employeesData = employees;
        maintenanceData = maintenance;

        await loadDashboard();

        renderAssets();
        renderEmployees();
        renderMaintenance();

        await checkDatabaseStatus();

    } catch (error) {

        console.error("Application initialization error:", error);

        alert(
            "Unable to load AssetIQ database records. " +
            "Please check your MySQL connection and refresh the page."
        );

    }

}


// --------------------------------------------------
// CHAT MESSAGE DISPLAY
// --------------------------------------------------

const chatMessages = document.getElementById("chatMessages");
const chatInput = document.getElementById("chatInput");
const sendButton = document.getElementById("sendButton");


function addMessage(role, content) {

    const welcome = chatMessages.querySelector(".welcome-message");

    if (welcome) {
        welcome.remove();
    }

    const row = document.createElement("div");

    row.className = `message-row ${role === "user" ? "user" : "assistant"}`;

    const avatar = document.createElement("div");
    avatar.className = "message-avatar";
    avatar.textContent = role === "user" ? "AD" : "✦";

    const messageContent = document.createElement("div");
    messageContent.className = "message-content";

    const name = document.createElement("div");
    name.className = "message-name";
    name.textContent = role === "user" ? "You" : "AssetIQ";

    const bubble = document.createElement("div");
    bubble.className = "message-bubble";

    // Preserve line breaks while keeping output safe.
    bubble.textContent = content;

    messageContent.appendChild(name);
    messageContent.appendChild(bubble);

    if (role === "user") {
        row.appendChild(messageContent);
        row.appendChild(avatar);
    } else {
        row.appendChild(avatar);
        row.appendChild(messageContent);
    }

    chatMessages.appendChild(row);

    chatMessages.scrollTop = chatMessages.scrollHeight;

}


function showTyping() {

    const typing = document.createElement("div");

    typing.id = "typingIndicator";
    typing.className = "typing-indicator";
    typing.textContent = "AssetIQ is retrieving database records...";

    chatMessages.appendChild(typing);

    chatMessages.scrollTop = chatMessages.scrollHeight;

}


function removeTyping() {

    const typing = document.getElementById("typingIndicator");

    if (typing) {
        typing.remove();
    }

}


// --------------------------------------------------
// SEND MESSAGE TO MYSQL CHATBOT
// --------------------------------------------------

async function sendMessage() {

    const message = chatInput.value.trim();

    if (!message || sendButton.disabled) {
        return;
    }

    addMessage("user", message);

    chatInput.value = "";
    chatInput.style.height = "auto";

    sendButton.disabled = true;

    showTyping();

    try {

        const response = await fetch("/api/chat", {

            method: "POST",

            headers: {
                "Content-Type": "application/json"
            },

            body: JSON.stringify({
                message: message
            })

        });

        const data = await response.json();

        removeTyping();

        if (!response.ok) {

            addMessage(
                "assistant",
                data.error || "Unable to process your question."
            );

            return;
        }

        addMessage("assistant", data.reply);

    } catch (error) {

        removeTyping();

        addMessage(
            "assistant",
            "Unable to reach the AssetIQ server. Please check your connection and try again."
        );

        console.error("Chat error:", error);

    } finally {

        sendButton.disabled = false;
        chatInput.focus();

    }

}


sendButton.addEventListener("click", sendMessage);


chatInput.addEventListener("keydown", event => {

    if (event.key === "Enter" && !event.shiftKey) {

        event.preventDefault();
        sendMessage();

    }

});


chatInput.addEventListener("input", () => {

    chatInput.style.height = "auto";

    chatInput.style.height =
        Math.min(chatInput.scrollHeight, 110) + "px";

});


// --------------------------------------------------
// SUGGESTED QUESTIONS
// --------------------------------------------------

function connectSuggestionButtons() {

    document.querySelectorAll(".suggestion").forEach(button => {

        button.addEventListener("click", () => {

            chatInput.value = button.dataset.question;

            sendMessage();

        });

    });

}

connectSuggestionButtons();


// --------------------------------------------------
// CLEAR CONVERSATION
// --------------------------------------------------

document.getElementById("clearChat").addEventListener("click", () => {

    chatMessages.innerHTML = `
        <div class="welcome-message">

            <div class="welcome-star">✦</div>

            <span class="ai-label">YOUR INTELLIGENT ASSET PARTNER</span>

            <h2>How can I help you<br>manage your assets?</h2>

            <p>Ask me about employees, asset assignments, inventory availability or maintenance records.</p>

            <div class="suggestion-grid">

                <button class="suggestion" data-question="Which employee currently has LAP-102?">
                    <span>♙</span>
                    <strong>Find an asset owner</strong>
                    <small>Who currently has LAP-102?</small>
                </button>

                <button class="suggestion" data-question="Show me all available laptops.">
                    <span>▣</span>
                    <strong>Check availability</strong>
                    <small>Find unassigned laptops</small>
                </button>

                <button class="suggestion" data-question="Which assets are under maintenance?">
                    <span>⚙</span>
                    <strong>Maintenance overview</strong>
                    <small>Check repair status</small>
                </button>

                <button class="suggestion" data-question="Which assets are assigned to EMP-105?">
                    <span>⌕</span>
                    <strong>Employee assets</strong>
                    <small>View an employee's equipment</small>
                </button>

            </div>

        </div>
    `;

    connectSuggestionButtons();

});


// --------------------------------------------------
// START APPLICATION
// --------------------------------------------------

initializeApplication();
