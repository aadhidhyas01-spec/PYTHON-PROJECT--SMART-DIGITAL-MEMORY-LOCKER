// Initialize Lucide Icons
lucide.createIcons();

document.addEventListener('DOMContentLoaded', () => {
    // --- PIN Login Logic ---
    const MOCK_PIN = "1234"; // In a real app, this would be hashed and checked against backend/localstorage
    let enteredPin = "";
    
    const pinDots = document.querySelectorAll('.pin-dot');
    const keys = document.querySelectorAll('.key');
    const loginScreen = document.getElementById('login-screen');
    const dashboardScreen = document.getElementById('dashboard-screen');
    const logoutBtn = document.getElementById('logout-btn');

    function updatePinDisplay() {
        pinDots.forEach((dot, index) => {
            if (index < enteredPin.length) {
                dot.classList.add('filled');
            } else {
                dot.classList.remove('filled');
            }
        });
    }

    function handleKeyClick(e) {
        const key = e.target.innerText;
        
        if (key === 'C') {
            enteredPin = "";
        } else if (key === 'OK') {
            if (enteredPin === MOCK_PIN) {
                // Success
                loginScreen.classList.remove('active');
                setTimeout(() => {
                    dashboardScreen.classList.add('active');
                }, 500); // Wait for fade out
            } else {
                // Fail
                const display = document.querySelector('.pin-display');
                display.classList.add('error-shake');
                setTimeout(() => display.classList.remove('error-shake'), 500);
                enteredPin = "";
            }
        } else {
            if (enteredPin.length < 4) {
                enteredPin += key;
            }
        }
        updatePinDisplay();
    }

    keys.forEach(key => key.addEventListener('click', handleKeyClick));

    // --- Logout Logic ---
    logoutBtn.addEventListener('click', () => {
        enteredPin = "";
        updatePinDisplay();
        dashboardScreen.classList.remove('active');
        setTimeout(() => {
            loginScreen.classList.add('active');
        }, 500);
    });

    // Add error shake animation dynamically
    const style = document.createElement('style');
    style.textContent = `
        @keyframes shake {
            0%, 100% { transform: translateX(0); }
            25% { transform: translateX(-10px); }
            75% { transform: translateX(10px); }
        }
        .error-shake { animation: shake 0.4s; }
    `;
    document.head.appendChild(style);
});
