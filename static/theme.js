// Load saved theme
window.onload = function () {
    const theme = localStorage.getItem("theme");
    const btn = document.getElementById("themeBtn");

    if (theme === "light") {
        document.body.classList.add("light-mode");
        if (btn) btn.innerText = "🌙 Dark";
    } else {
        if (btn) btn.innerText = "☀ Light";
    }
};

// Toggle theme
function toggleTheme() {
    document.body.classList.toggle("light-mode");
    const btn = document.getElementById("themeBtn");

    if (document.body.classList.contains("light-mode")) {
        localStorage.setItem("theme", "light");
        if (btn) btn.innerText = "🌙 Dark";
    } else {
        localStorage.setItem("theme", "dark");
        if (btn) btn.innerText = "☀ Light";
    }
}
