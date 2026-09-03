(() => {
    const sidebar = document.querySelector('.sidebar');
    const toggle = document.querySelector('.sidebar-mobile-toggle');
    const searchToggle = document.querySelector('.sidebar-mobile-search');
    const moreToggle = document.querySelector('.mobile-tabbar-more');
    const searchInput = document.querySelector('#mobile-help-search-input');

    if (!sidebar || !toggle) return;

    const icon = toggle.querySelector('i');
    const label = toggle.querySelector('[data-mobile-menu-label]');

    const setMenuState = (isOpen) => {
        sidebar.classList.toggle('is-mobile-open', isOpen);
        toggle.setAttribute('aria-expanded', String(isOpen));

        if (icon) icon.className = isOpen ? 'fa-solid fa-xmark' : 'fa-solid fa-bars';
        if (label) label.textContent = isOpen ? 'Close' : 'Menu';
    };

    const setSearchState = (isOpen) => {
        sidebar.classList.toggle('is-mobile-search-open', isOpen);
        if (searchToggle) searchToggle.setAttribute('aria-expanded', String(isOpen));
        if (isOpen && searchInput) window.setTimeout(() => searchInput.focus(), 0);
    };

    toggle.addEventListener('click', () => {
        const willOpen = !sidebar.classList.contains('is-mobile-open');
        setSearchState(false);
        setMenuState(willOpen);
    });

    if (searchToggle) {
        searchToggle.addEventListener('click', () => {
            const willOpen = !sidebar.classList.contains('is-mobile-search-open');
            setMenuState(false);
            setSearchState(willOpen);
        });
    }

    if (moreToggle) {
        moreToggle.addEventListener('click', () => {
            setSearchState(false);
            setMenuState(!sidebar.classList.contains('is-mobile-open'));
        });
    }

    sidebar.querySelectorAll('.sidebar-nav-link').forEach((link) => {
        link.addEventListener('click', () => setMenuState(false));
    });

    document.addEventListener('keydown', (event) => {
        if (event.key !== 'Escape') return;
        setMenuState(false);
        setSearchState(false);
    });

    window.addEventListener('resize', () => {
        if (window.innerWidth > 700) {
            setMenuState(false);
            setSearchState(false);
        }
    });

    window.addEventListener('pageshow', () => {
        setMenuState(false);
        setSearchState(false);
    });
})();
