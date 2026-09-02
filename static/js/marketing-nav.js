(() => {
    const header = document.querySelector('.marketing-header');
    const toggle = document.querySelector('.marketing-mobile-toggle');

    if (!header || !toggle) return;

    const icon = toggle.querySelector('i');
    const label = toggle.querySelector('[data-marketing-menu-label]');

    const setMenuState = (isOpen) => {
        header.classList.toggle('is-mobile-open', isOpen);
        toggle.setAttribute('aria-expanded', String(isOpen));
        if (icon) icon.className = isOpen ? 'fa-solid fa-xmark' : 'fa-solid fa-bars';
        if (label) label.textContent = isOpen ? 'Close' : 'Menu';
    };

    toggle.addEventListener('click', () => setMenuState(!header.classList.contains('is-mobile-open')));
    header.querySelectorAll('.marketing-nav a').forEach((link) => link.addEventListener('click', () => setMenuState(false)));
    window.addEventListener('resize', () => {
        if (window.innerWidth > 600) setMenuState(false);
    });
})();
