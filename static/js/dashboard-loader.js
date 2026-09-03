(() => {
    const loader = document.querySelector('.dashboard-login-loader');
    if (!loader) return;

    window.setTimeout(() => {
        loader.classList.add('is-leaving');
        window.setTimeout(() => loader.remove(), 240);
    }, 900);
})();
