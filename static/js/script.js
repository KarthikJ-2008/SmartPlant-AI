document.addEventListener("DOMContentLoaded", () => {
    // Theme toggle
    const themeToggle = document.getElementById("themeToggle");
    const themeIcon = document.getElementById("themeIcon");
    const themeLabel = document.getElementById("themeLabel");

    function applyTheme(theme) {
        document.documentElement.dataset.theme = theme;
        const isDark = theme === "dark";
        if (themeIcon) themeIcon.textContent = isDark ? "☀️" : "🌙";
        if (themeLabel) themeLabel.textContent = isDark ? "Switch to light mode" : "Switch to dark mode";
        localStorage.setItem("plantcare-theme", theme);
    }

    if (themeToggle) {
        themeToggle.addEventListener("click", () => {
            const nextTheme = document.documentElement.dataset.theme === "dark" ? "light" : "dark";
            applyTheme(nextTheme);
        });
    }

  // Sidebar Toggle: Handles both mobile drawer and desktop collapse
const app = document.querySelector(".app");
const sidebarToggle = document.getElementById("sidebarToggle");
const sidebar = document.querySelector(".sidebar");

if (sidebarToggle && app) {
    sidebarToggle.addEventListener("click", (e) => {
        e.stopPropagation();
        if (window.innerWidth <= 768) {
            app.classList.toggle("sidebar-open");
        } else {
            app.classList.toggle("sidebar-collapsed");
        }
    });

    // Close mobile drawer when clicking workspace outside
    document.addEventListener("click", (e) => {
        if (window.innerWidth <= 768 && app.classList.contains("sidebar-open")) {
            if (!sidebar.contains(e.target) && !sidebarToggle.contains(e.target)) {
                app.classList.remove("sidebar-open");
            }
        }
    });
}

    // File Preview & Drag and Drop
    const fileInput = document.getElementById("image");
    const dropZone = document.getElementById("dropZone");
    const previewWrap = document.getElementById("previewWrap");
    const previewImage = document.getElementById("previewImage");
    const fileName = document.getElementById("fileName");
    const removeFile = document.getElementById("removeFile");
    const predictButton = document.getElementById("predictButton");
    const predictionForm = document.getElementById("predictionForm");

    function updatePreview(file) {
        if (!file || !file.type.startsWith("image/")) return;
        previewImage.src = URL.createObjectURL(file);
        fileName.textContent = file.name;
        previewWrap.classList.add("visible");
    }

    if (fileInput) {
        fileInput.addEventListener("change", (e) => {
            if (e.target.files.length) updatePreview(e.target.files[0]);
        });
    }

    if (removeFile) {
        removeFile.addEventListener("click", () => {
            fileInput.value = "";
            previewWrap.classList.remove("visible");
        });
    }

    if (dropZone) {
        ["dragenter", "dragover"].forEach(evt => {
            dropZone.addEventListener(evt, (e) => { e.preventDefault(); dropZone.classList.add("dragging"); });
        });
        ["dragleave", "drop"].forEach(evt => {
            dropZone.addEventListener(evt, (e) => { e.preventDefault(); dropZone.classList.remove("dragging"); });
        });
        dropZone.addEventListener("drop", (e) => {
            if (e.dataTransfer.files.length) {
                fileInput.files = e.dataTransfer.files;
                updatePreview(e.dataTransfer.files[0]);
            }
        });
    }

    if (predictionForm) {
        predictionForm.addEventListener("submit", () => {
            predictButton.disabled = true;
            predictButton.innerHTML = "<span>⏳</span> Analyzing leaf...";
        });
    }

    const newChatBtn = document.getElementById("newChat");
    if (newChatBtn) {
        newChatBtn.addEventListener("click", () => {
            window.location.href = "/";
        });
    }
});