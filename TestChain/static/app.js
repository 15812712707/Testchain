document.querySelectorAll('form[data-confirm]').forEach((form) => {
  form.addEventListener('submit', (event) => {
    if (!window.confirm(form.dataset.confirm)) event.preventDefault();
  });
});

document.querySelectorAll('nav[aria-label="项目导航"] a').forEach((link) => {
  if (window.location.pathname === new URL(link.href).pathname) {
    link.classList.add('active');
    link.setAttribute('aria-current', 'page');
  }
});

document.querySelectorAll('input[type="file"]').forEach((input) => {
  input.addEventListener('change', () => {
    input.setCustomValidity(input.files[0]?.size > 10 * 1024 * 1024 ? '文件不能超过 10 MB' : '');
    input.reportValidity();
  });
});
