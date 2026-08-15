/**
 * Delegated handlers for the Jinja admin pages (SEC-CSP-01).
 *
 * Inline on*= attributes cannot run under a Content-Security-Policy without
 * 'unsafe-inline', and a nonce does NOT authorise them - only <script> blocks.
 * So every inline handler in the admin templates was replaced by a data-act
 * attribute, and this one listener runs them.
 *
 * An EXTERNAL file is deliberate: it needs neither a nonce nor unsafe-inline,
 * so it keeps working whichever way the policy is tightened.
 */
(function () {
  'use strict';

  /** Tick or untick every checkbox matching a selector. */
  function setAll(selector, checked) {
    document.querySelectorAll(selector).forEach(function (box) {
      box.checked = checked;
    });
  }

  document.addEventListener('click', function (ev) {
    var el = ev.target.closest('[data-act]');
    if (!el) return;

    var act = el.getAttribute('data-act');
    var on = el.getAttribute('data-checked') === '1';

    // Tick/untick a named checkbox group, e.g. data-group="users".
    if (act === 'checkgroup') {
      var group = el.getAttribute('data-group');
      setAll('input[name="' + group + '"]', on);
      return;
    }

    // Tick/untick by class, e.g. data-selector=".proc-cb".
    if (act === 'check-selector') {
      setAll(el.getAttribute('data-selector'), on);
      return;
    }

    // Confirm before a destructive click; cancelling stops the default action.
    if (act === 'confirm-submit' && !window.confirm(el.getAttribute('data-confirm'))) {
      ev.preventDefault();
    }
  });

  // Hide an image that fails to load. Registered in the CAPTURE phase because
  // error events on <img> do not bubble, so a delegated listener on document
  // never sees them otherwise.
  document.addEventListener(
    'error',
    function (ev) {
      var el = ev.target;
      if (el instanceof HTMLImageElement && el.getAttribute('data-act') === 'hide-on-error') {
        el.style.display = 'none';
      }
    },
    true
  );

  // Confirm before a destructive form submit. Kept separate from the click
  // handler because a form can be submitted by keyboard, not only by clicking.
  document.addEventListener('submit', function (ev) {
    var form = ev.target.closest('form[data-confirm]');
    if (form && !window.confirm(form.getAttribute('data-confirm'))) {
      ev.preventDefault();
    }
  });

  // A filter control that applies itself the moment it changes, e.g. the audit
  // log's time range. Inline onchange="this.form.submit()" would need
  // 'unsafe-inline', which is exactly what SEC-CSP-01 is burning down.
  document.addEventListener('change', function (ev) {
    var el = ev.target.closest('[data-act="submit-on-change"]');
    if (el && el.form) {
      el.form.submit();
    }
  });
})();
