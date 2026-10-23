(() => {
  const toggle = document.querySelector('.menu-toggle');
  const nav = document.querySelector('#navigation');
  if (!toggle || !nav) return;
  toggle.hidden = false;
  const mobile = window.matchMedia('(max-width: 700px)');
  function setOpen(open) {
    toggle.setAttribute('aria-expanded', String(open));
    nav.dataset.collapsed = String(mobile.matches && !open);
  }
  setOpen(false);
  toggle.addEventListener('click', () => setOpen(toggle.getAttribute('aria-expanded') !== 'true'));
  mobile.addEventListener('change', () => setOpen(false));
  document.addEventListener('keydown', event => {
    if (event.key === 'Escape' && mobile.matches && toggle.getAttribute('aria-expanded') === 'true') {
      setOpen(false);
      toggle.focus();
    }
  });
})();
