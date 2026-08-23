(function () {
  'use strict';

  var helpLink = document.getElementById('contextHelpLink');
  if (!helpLink) return;

  var helpRoot = helpLink.getAttribute('data-help-root') || '/help';
  var mapUrl = helpLink.getAttribute('data-help-map-url');
  var helpMap = null;

  function matches(rule, path) {
    return rule.match === 'exact' ? path === rule.path : path.indexOf(rule.path) === 0;
  }

  function updateLink() {
    if (!helpMap) return;
    var path = window.location.pathname;
    var rules = Array.isArray(helpMap.rules) ? helpMap.rules : [];
    var rule = rules.find(function (candidate) { return matches(candidate, path); }) || helpMap.default || {};
    var target = rule.target || 'getting-started';
    var label = rule.label || 'Open help for this page';
    helpLink.href = helpRoot + '#' + encodeURIComponent(target);
    helpLink.title = label;
    helpLink.setAttribute('aria-label', label);
  }

  // Native title tooltips are a compact complement to accessible names for
  // icon-only actions. The observer also catches controls mounted later by
  // React; visible-text buttons keep their visible explanation.
  var labelledControlSelector = 'button[aria-label], a[aria-label], [role="button"][aria-label]';
  function addHoverDescriptions(root) {
    var controls = [];
    if (root.matches && root.matches(labelledControlSelector)) controls.push(root);
    if (root.querySelectorAll) controls = controls.concat(Array.from(root.querySelectorAll(labelledControlSelector)));
    controls.forEach(function (control) {
      if (!control.getAttribute('title')) control.setAttribute('title', control.getAttribute('aria-label'));
    });
  }
  addHoverDescriptions(document);
  new MutationObserver(function (changes) {
    changes.forEach(function (change) {
      change.addedNodes.forEach(function (node) {
        if (node.nodeType === 1) addHoverDescriptions(node);
      });
    });
  }).observe(document.body, { childList: true, subtree: true });

  if (!mapUrl) return;
  fetch(mapUrl, { headers: { Accept: 'application/json' } })
    .then(function (response) { if (!response.ok) throw new Error('help map unavailable'); return response.json(); })
    .then(function (data) { helpMap = data; updateLink(); })
    .catch(function () { /* The generic Help link remains usable. */ });

  window.addEventListener('popstate', updateLink);
  document.addEventListener('click', function () { window.setTimeout(updateLink, 0); });
})();
