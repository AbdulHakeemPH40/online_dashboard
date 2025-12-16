// Dropdown functionality
function toggleDropdown(event, dropdownId) {
    event.preventDefault();
    event.stopPropagation();

    // Close all other dropdowns first
    var allDropdowns = document.querySelectorAll('.dropdown-content');
    allDropdowns.forEach(function (dropdown) {
        if (dropdown.id !== dropdownId) {
            dropdown.style.display = 'none';
        }
    });

    var dropdown = document.getElementById(dropdownId);
    var isVisible = dropdown.style.display === "block";

    if (isVisible) {
        dropdown.style.display = "none";
    } else {
        dropdown.style.display = "block";

        // Ensure dropdown is visible on mobile
        if (window.innerWidth <= 768) {
            // Add a small delay to ensure proper positioning
            setTimeout(function () {
                var rect = dropdown.getBoundingClientRect();
                var sidebar = document.querySelector('nav .sidebar');
                var sidebarRect = sidebar.getBoundingClientRect();

                // Check if dropdown extends beyond sidebar width
                if (rect.right > sidebarRect.right) {
                    dropdown.style.marginLeft = '0.5rem';
                    dropdown.style.marginRight = '0.5rem';
                }
            }, 10);
        }
    }
}

// Loading overlay
function showLoading() {
    const overlay = document.createElement('div');
    overlay.className = 'fixed inset-0 flex items-center justify-center z-50';
    overlay.style.backgroundColor = 'rgba(0, 0, 0, 0.2)';

    const loadingBox = document.createElement('div');
    loadingBox.style.backgroundColor = '#FFFFFF';
    loadingBox.style.border = '1px solid #C5C5C5';
    loadingBox.style.boxShadow = '0 2px 4px rgba(0, 0, 0, 0.15)';
    loadingBox.style.padding = '15px 20px';
    loadingBox.style.borderRadius = '3px';
    loadingBox.style.display = 'flex';
    loadingBox.style.flexDirection = 'column';
    loadingBox.style.alignItems = 'center';
    loadingBox.style.justifyContent = 'center';

    const loadingText = document.createElement('div');
    loadingText.textContent = 'Processing...';
    loadingText.style.fontFamily = 'Arial, sans-serif';
    loadingText.style.fontSize = '14px';
    loadingText.style.color = '#333333';
    loadingText.style.marginBottom = '10px';

    const loadingDots = document.createElement('div');
    loadingDots.style.display = 'flex';
    loadingDots.style.gap = '6px';

    for (let i = 0; i < 3; i++) {
        const dot = document.createElement('div');
        dot.style.width = '8px';
        dot.style.height = '8px';
        dot.style.backgroundColor = '#5B9BD5';
        dot.style.borderRadius = '50%';
        dot.style.animation = 'loadingPulse 1.4s infinite ease-in-out';
        dot.style.animationDelay = `${i * 0.2}s`;
        loadingDots.appendChild(dot);
    }

    loadingBox.appendChild(loadingText);
    loadingBox.appendChild(loadingDots);
    overlay.appendChild(loadingBox);

    document.body.appendChild(overlay);
}

function hideLoading() {
    const overlay = document.querySelector('.fixed.inset-0');
    if (overlay) overlay.remove();
}

// Alert handling
function showAlert(message, type = 'info') {
    const alertDiv = document.createElement('div');

    // Set styles based on alert type
    let bgColor, borderColor, textColor, iconContent;

    if (type === 'error') {
        bgColor = '#FFFFFF';
        borderColor = '#F44336';
        textColor = '#333333';
        iconContent = '⚠️';
    } else if (type === 'success') {
        bgColor = '#FFFFFF';
        borderColor = '#4CAF50';
        textColor = '#333333';
        iconContent = '✓';
    } else { // info
        bgColor = '#FFFFFF';
        borderColor = '#5B9BD5';
        textColor = '#333333';
        iconContent = 'i';
    }

    // Style the alert container
    alertDiv.style.display = 'flex';
    alertDiv.style.alignItems = 'center';
    alertDiv.style.backgroundColor = bgColor;
    alertDiv.style.border = `1px solid ${borderColor}`;
    alertDiv.style.borderLeft = `4px solid ${borderColor}`;
    alertDiv.style.boxShadow = '0 2px 4px rgba(0, 0, 0, 0.08)';
    alertDiv.style.borderRadius = '3px';
    alertDiv.style.padding = '10px 15px';
    alertDiv.style.marginBottom = '15px';
    alertDiv.style.fontFamily = 'Arial, sans-serif';

    // Create alert content
    alertDiv.innerHTML = `
        <div style="display: flex; align-items: center; width: 100%;">
            <div style="margin-right: 10px; font-weight: bold; color: ${borderColor};">${iconContent}</div>
            <div style="flex-grow: 1; color: ${textColor};">${message}</div>
            <button style="background: none; border: none; color: #999999; font-size: 16px; cursor: pointer;">×</button>
        </div>
    `;

    const windowContent = document.querySelector('div[style*="padding: 16px"]') || document.body;
    windowContent.insertBefore(alertDiv, windowContent.firstChild);

    alertDiv.querySelector('button').addEventListener('click', () => alertDiv.remove());

    // Auto-remove after 5 seconds
    setTimeout(() => {
        if (alertDiv.parentNode) {
            alertDiv.remove();
        }
    }, 5000);
}

// Mobile sidebar toggle functionality (legacy - disabled)
function toggleSidebarLegacy() {
    // Disabled to prevent errors with new sidebar structure
    console.log('Legacy sidebar toggle function called but disabled');
}

// DOM Content Loaded Event Listeners
document.addEventListener('DOMContentLoaded', function () {
    console.log('DOM fully loaded');

    // Close dropdowns when clicking outside
    document.addEventListener('click', function (event) {
        var dropdowns = document.querySelectorAll('.dropdown-content');
        var clickedInsideDropdown = false;

        // Check if click was inside any dropdown or dropdown trigger
        dropdowns.forEach(function (dropdown) {
            var dropdownParent = dropdown.closest('.list');
            if (dropdownParent && dropdownParent.contains(event.target)) {
                clickedInsideDropdown = true;
            }
        });

        // Close all dropdowns if click was outside
        if (!clickedInsideDropdown) {
            dropdowns.forEach(function (dropdown) {
                dropdown.style.display = 'none';
            });
        }
    });

    // Close dropdowns on window resize
    window.addEventListener('resize', function () {
        var dropdowns = document.querySelectorAll('.dropdown-content');
        dropdowns.forEach(function (dropdown) {
            dropdown.style.display = 'none';
        });

        // Close sidebar on larger screens
        var navBar = document.querySelector('nav');
        if (window.innerWidth > 768 && navBar && navBar.classList.contains('open')) {
            navBar.classList.remove('open');
            document.body.style.overflow = '';
        }
    });

    // Mobile navbar optimization - ensure smooth scrolling for nav links
    var navLinks = document.querySelectorAll('.dark-navbar nav a');
    navLinks.forEach(function(link) {
        link.addEventListener('click', function() {
            // Add active state management if needed
            navLinks.forEach(function(l) { l.classList.remove('active'); });
            this.classList.add('active');
        });
    });
    
    // Prevent navbar from interfering with page scroll on mobile
    if (window.innerWidth <= 768) {
        var navbar = document.querySelector('.dark-navbar');
        if (navbar) {
            navbar.style.position = 'fixed';
            navbar.style.top = '0';
            navbar.style.left = '0';
            navbar.style.right = '0';
            navbar.style.zIndex = '1100';
        }
    }

    // Improve touch interactions on mobile
    if ('ontouchstart' in window) {
        var touchDropdownTriggers = document.querySelectorAll('.list .nav-link');
        touchDropdownTriggers.forEach(function (trigger) {
            trigger.addEventListener('touchstart', function (e) {
                // Add a slight delay to improve touch responsiveness
                e.preventDefault();
                setTimeout(function () {
                    trigger.click();
                }, 50);
            });
        });
    }

    // Sidebar Toggle Functionality
    const sidebar = document.querySelector('.left-sidebar');
    const sidebarToggle = document.getElementById('sidebarToggle');
    const mobileToggle = document.querySelector('.mobile-sidebar-toggle');
    const sidebarOverlay = document.getElementById('sidebarOverlay');

    // Desktop sidebar collapse/expand
    function toggleSidebar() {
        if (sidebar) {
            sidebar.classList.toggle('collapsed');
            document.body.classList.toggle('sidebar-collapsed');
            
            const toggleIcon = sidebarToggle?.querySelector('i');
            if (toggleIcon) {
                toggleIcon.className = sidebar.classList.contains('collapsed') ? 
                    'bx bx-chevron-right' : 'bx bx-chevron-left';
            }
            
            // On mobile, also close the sidebar when collapsing
            if (window.innerWidth <= 768 && sidebar.classList.contains('collapsed')) {
                sidebar.classList.remove('active', 'mobile-open');
                sidebarOverlay?.classList.remove('active');
                document.body.style.overflow = 'auto';
            }
        }
    }

    // Mobile sidebar toggle
    function toggleMobileSidebar() {
        if (sidebar) {
            sidebar.classList.toggle('mobile-open');
            sidebar.classList.toggle('active');
            if (sidebarOverlay) {
                sidebarOverlay.classList.toggle('active');
            }
            document.body.style.overflow = sidebar.classList.contains('active') ? 'hidden' : 'auto';
        }
    }

    // Event listeners
    sidebarToggle?.addEventListener('click', toggleSidebar);
    mobileToggle?.addEventListener('click', toggleMobileSidebar);
    sidebarOverlay?.addEventListener('click', toggleMobileSidebar);

    // Close mobile sidebar on resize
    window.addEventListener('resize', function() {
        if (window.innerWidth > 768 && sidebar) {
            sidebar.classList.remove('active');
            sidebarOverlay?.classList.remove('active');
            document.body.style.overflow = 'auto';
        }
    });

    // Enhanced dropdown functionality
    const dropdownTriggers = document.querySelectorAll('.has-dropdown .nav-link');
    dropdownTriggers.forEach(trigger => {
        trigger.addEventListener('click', function(e) {
            e.preventDefault();
            const dropdown = this.nextElementSibling;
            const isVisible = dropdown.style.display === 'block';
            
            // Close all other dropdowns
            document.querySelectorAll('.dropdown-menu').forEach(menu => {
                if (menu !== dropdown) {
                    menu.style.display = 'none';
                }
            });
            
            // Toggle current dropdown
            dropdown.style.display = isVisible ? 'none' : 'block';
            
            // Rotate arrow
            const arrow = this.querySelector('.dropdown-arrow');
            if (arrow) {
                arrow.style.transform = isVisible ? 'rotate(0deg)' : 'rotate(180deg)';
            }
        });
    });

    // Close dropdowns when clicking outside
    document.addEventListener('click', function(e) {
        if (!e.target.closest('.has-dropdown')) {
            document.querySelectorAll('.dropdown-menu').forEach(menu => {
                menu.style.display = 'none';
            });
            document.querySelectorAll('.dropdown-arrow').forEach(arrow => {
                arrow.style.transform = 'rotate(0deg)';
            });
        }
    });
});