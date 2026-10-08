document.addEventListener('DOMContentLoaded', function() {
    document.querySelectorAll('.theme-toggle, #light-toggle').forEach(function(mode_toggle) {
        mode_toggle.addEventListener("click", function() {
            toggleTheme(localStorage.getItem("theme"));
        });
    });
});

