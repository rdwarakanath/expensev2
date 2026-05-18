/* ============================================================
   notify.js — Shared inline error & toast utilities
   Include this in every page that needs error feedback.
   ============================================================ */

// ── Toast container (created once on first use) ──────────────
function _getToastContainer() {
  let el = document.getElementById('toast-container');
  if (!el) {
    el = document.createElement('div');
    el.id = 'toast-container';
    document.body.appendChild(el);
  }
  return el;
}

/**
 * showToast(message, type)
 * type: 'error' | 'success' | 'info'
 * Auto-dismisses after 4s. Has manual ✕ close.
 */
function showToast(message, type = 'error') {
  const icons = { error: '⚠', success: '✓', info: 'ℹ' };
  const container = _getToastContainer();

  const toast = document.createElement('div');
  toast.className = `toast toast-${type}`;
  toast.innerHTML = `
    <span class="toast-icon">${icons[type] || '⚠'}</span>
    <span class="toast-msg">${message}</span>
    <button class="toast-close" aria-label="Close">✕</button>
  `;

  container.appendChild(toast);

  // Close button
  toast.querySelector('.toast-close').addEventListener('click', () => dismissToast(toast));

  // Auto-dismiss after 4s
  const timer = setTimeout(() => dismissToast(toast), 4000);
  toast._timer = timer;
}

function dismissToast(toast) {
  clearTimeout(toast._timer);
  toast.classList.add('toast-hiding');
  setTimeout(() => toast.remove(), 200);
}

/**
 * showFieldError(inputEl, message)
 * Shows a red error message below the input field.
 * Automatically clears when user types again.
 */
function showFieldError(inputEl, message) {
  // Find or create error element right after input
  let errEl = inputEl.nextElementSibling;
  if (!errEl || !errEl.classList.contains('field-error-msg')) {
    errEl = document.createElement('p');
    errEl.className = 'field-error-msg';
    inputEl.parentNode.insertBefore(errEl, inputEl.nextSibling);
  }
  errEl.textContent = message;
  errEl.classList.add('visible');
  inputEl.classList.add('field-has-error');

  // Clear on next input
  function clearErr() {
    errEl.classList.remove('visible');
    inputEl.classList.remove('field-has-error');
    inputEl.removeEventListener('input', clearErr);
  }
  inputEl.addEventListener('input', clearErr);
  inputEl.focus();
}

/**
 * showModalError(bannerEl, message)
 * Shows a red banner inside a modal.
 * Pass the banner div element and the message.
 */
function showModalError(bannerEl, message) {
  bannerEl.textContent = message;
  bannerEl.classList.add('visible');
}

function hideModalError(bannerEl) {
  bannerEl.classList.remove('visible');
  bannerEl.textContent = '';
}
