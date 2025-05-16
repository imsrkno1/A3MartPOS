// app/static/js/main.js

// Global Notification Function
function showAppNotification(message, type = 'info') { // type can be 'success', 'danger', 'warning', 'info'
    const notificationArea = document.getElementById('notification-area');
    if (!notificationArea) {
        console.warn('Notification area #notification-area not found in base.html. Falling back to alert.');
        alert(message); // Fallback to alert if the area isn't on the page
        return;
    }

    const notifDiv = document.createElement('div');
    const iconSpan = document.createElement('span');
    iconSpan.classList.add('notification-icon', 'mr-3'); // Added mr-3 for spacing

    let iconSvg = '';
    // Using simple SVGs for icons
    if (type === 'success') {
        iconSvg = '<svg class="h-5 w-5" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clip-rule="evenodd" /></svg>';
        notifDiv.classList.add('notification-success');
    } else if (type === 'danger') {
        iconSvg = '<svg class="h-5 w-5" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clip-rule="evenodd" /></svg>';
        notifDiv.classList.add('notification-danger');
    } else if (type === 'warning') {
        iconSvg = '<svg class="h-5 w-5" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 3.001-1.742 3.001H4.42c-1.53 0-2.493-1.667-1.743-3.001l5.58-9.92zM10 12a1 1 0 110-2 1 1 0 010 2zm0-4a1 1 0 011 1v2a1 1 0 11-2 0V9a1 1 0 011-1z" clip-rule="evenodd" /></svg>';
        notifDiv.classList.add('notification-warning');
    } else { // info
        iconSvg = '<svg class="h-5 w-5" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clip-rule="evenodd" /></svg>';
        notifDiv.classList.add('notification-info');
    }
    iconSpan.innerHTML = iconSvg;
    notifDiv.appendChild(iconSpan);

    const messageSpan = document.createElement('span');
    messageSpan.textContent = message;
    notifDiv.appendChild(messageSpan);

    notifDiv.classList.add('notification'); // Base class for padding, border-radius, shadow, text color, initial transition state
    notificationArea.appendChild(notifDiv);

    // Trigger fade in (slight delay to allow CSS to apply initial state for transition)
    setTimeout(() => {
        notifDiv.classList.add('show'); // Add class to trigger slide-in and fade-in
    }, 10);


    // Auto-hide after a few seconds
    setTimeout(() => {
        notifDiv.classList.remove('show'); // Remove 'show' to trigger slide-out and fade-out
        // Remove the element after the transition completes
        notifDiv.addEventListener('transitionend', () => {
            notifDiv.remove();
        });
    }, 4000); // Display for 4 seconds
}


// Existing or other general JS functions can go here
document.addEventListener('DOMContentLoaded', function() {
    // Popup Link Handler - Keep this if used, or integrate specific link handling elsewhere
    function openPopup(event) {
        event.preventDefault();
        const url = event.currentTarget.href;
        window.open(url, 'formPopup', 'width=800,height=600,scrollbars=yes,resizable=yes');
    }
    const popupPaths = ["{{ url_for('customers.add_customer') }}", "{{ url_for('inventory.add_product') }}"]; // These Jinja parts won't work in a static JS file.
    // We need to target links differently if this popup logic is in main.js
    // For now, assume popups are handled by inline scripts in base.html or specific templates.
    // Or, use classes like 'open-popup' and target them.

    document.querySelectorAll('a.open-as-popup').forEach(link => { // Example: target a specific class
        link.addEventListener('click', openPopup);
    });


    // Mobile menu toggle
    const mobileMenuButton = document.getElementById('mobile-menu-button');
    const mobileMenu = document.getElementById('mobile-menu');
    if (mobileMenuButton && mobileMenu) {
        mobileMenuButton.addEventListener('click', () => {
            mobileMenu.classList.toggle('hidden');
            mobileMenuButton.querySelectorAll('svg').forEach(icon => icon.classList.toggle('hidden'));
        });
    }
});