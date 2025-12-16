// Mobile Navbar Optimization JavaScript

document.addEventListener('DOMContentLoaded', function() {
    
    // Mobile navbar height optimization
    function optimizeMobileNavbar() {
        const navbar = document.querySelector('.dark-navbar');
        const sidebar = document.querySelector('.left-sidebar, .sidebar, aside');
        const overlay = document.querySelector('.sidebar-overlay, .overlay');
        const mainContent = document.querySelector('.main-content');
        
        if (window.innerWidth <= 768) {
            // Ensure navbar is properly positioned on mobile
            if (navbar) {
                navbar.style.position = 'fixed';
                navbar.style.top = '0';
                navbar.style.left = '0';
                navbar.style.right = '0';
                navbar.style.width = '100%';
                navbar.style.zIndex = '1100';
                navbar.style.height = window.innerWidth <= 480 ? '44px' : '56px';
            }
            
            // Adjust sidebar position
            if (sidebar) {
                const navbarHeight = window.innerWidth <= 480 ? '44px' : '56px';
                sidebar.style.top = navbarHeight;
                sidebar.style.height = `calc(100vh - ${navbarHeight})`;
            }
            
            // Adjust overlay position
            if (overlay) {
                const navbarHeight = window.innerWidth <= 480 ? '44px' : '56px';
                overlay.style.top = navbarHeight;
            }
            
            // Adjust main content
            if (mainContent) {
                mainContent.style.marginLeft = '0';
                const navbarHeight = window.innerWidth <= 480 ? '44px' : '56px';
                mainContent.style.paddingTop = '8px';
                document.body.style.paddingTop = navbarHeight;
            }
        } else {
            // Desktop behavior
            if (navbar) {
                navbar.style.position = 'sticky';
                navbar.style.marginLeft = '280px';
                navbar.style.width = 'calc(100% - 280px)';
                navbar.style.height = 'auto';
            }
            
            if (mainContent) {
                mainContent.style.marginLeft = '280px';
                mainContent.style.paddingTop = '20px';
                document.body.style.paddingTop = '0';
            }
            
            if (sidebar) {
                sidebar.style.top = '0';
                sidebar.style.height = '100vh';
            }
            
            if (overlay) {
                overlay.style.top = '0';
            }
        }
    }
    
    // Smooth scrolling for navbar links on mobile
    function setupMobileNavigation() {
        const navLinks = document.querySelectorAll('.dark-navbar nav a');
        
        navLinks.forEach(function(link) {
            link.addEventListener('click', function(e) {
                // Remove active class from all links
                navLinks.forEach(function(l) {
                    l.classList.remove('active');
                });
                
                // Add active class to clicked link
                this.classList.add('active');
                
                // Smooth scroll behavior for mobile
                if (window.innerWidth <= 768) {
                    const navbar = document.querySelector('.dark-navbar nav');
                    if (navbar) {
                        // Center the active link in the navbar
                        const linkRect = this.getBoundingClientRect();
                        const navbarRect = navbar.getBoundingClientRect();
                        const scrollLeft = linkRect.left - navbarRect.left - (navbarRect.width / 2) + (linkRect.width / 2);
                        
                        navbar.scrollTo({
                            left: navbar.scrollLeft + scrollLeft,
                            behavior: 'smooth'
                        });
                    }
                }
            });
        });
    }
    
    // Handle window resize
    function handleResize() {
        optimizeMobileNavbar();
        
        // Close mobile sidebar on desktop
        if (window.innerWidth > 768) {
            const sidebar = document.querySelector('.left-sidebar, .sidebar, aside');
            const overlay = document.querySelector('.sidebar-overlay, .overlay');
            
            if (sidebar) {
                sidebar.classList.remove('mobile-open', 'active');
            }
            
            if (overlay) {
                overlay.classList.remove('active');
            }
            
            document.body.style.overflow = 'auto';
        }
    }
    
    // Prevent horizontal scroll on mobile
    function preventHorizontalScroll() {
        if (window.innerWidth <= 768) {
            document.documentElement.style.overflowX = 'hidden';
            document.body.style.overflowX = 'hidden';
        } else {
            document.documentElement.style.overflowX = 'auto';
            document.body.style.overflowX = 'auto';
        }
    }
    
    // Touch optimization for mobile navbar
    function setupTouchOptimization() {
        const navLinks = document.querySelectorAll('.dark-navbar nav a');
        
        navLinks.forEach(function(link) {
            // Add touch feedback
            link.addEventListener('touchstart', function() {
                this.style.transform = 'scale(0.95)';
            });
            
            link.addEventListener('touchend', function() {
                this.style.transform = 'scale(1)';
            });
            
            link.addEventListener('touchcancel', function() {
                this.style.transform = 'scale(1)';
            });
        });
    }
    
    // Initialize all optimizations
    optimizeMobileNavbar();
    setupMobileNavigation();
    preventHorizontalScroll();
    setupTouchOptimization();
    
    // Event listeners
    window.addEventListener('resize', handleResize);
    window.addEventListener('orientationchange', function() {
        setTimeout(optimizeMobileNavbar, 100);
    });
    
    // Performance optimization - debounce resize
    let resizeTimeout;
    window.addEventListener('resize', function() {
        clearTimeout(resizeTimeout);
        resizeTimeout = setTimeout(handleResize, 150);
    });
});

// Export functions for external use if needed
window.MobileNavbar = {
    optimize: function() {
        const event = new Event('DOMContentLoaded');
        document.dispatchEvent(event);
    }
};