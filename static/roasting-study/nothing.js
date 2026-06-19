/* Nothing design — theme toggle (dark default, persisted) */
(function () {
  var KEY = 'nd-theme';
  var root = document.documentElement;
  function apply(t) { root.setAttribute('data-theme', t); }
  var saved = null;
  try { saved = localStorage.getItem(KEY); } catch (e) {}
  apply(saved === 'light' ? 'light' : 'dark');

  function label() { return root.getAttribute('data-theme') === 'light' ? 'LIGHT' : 'DARK'; }

  document.addEventListener('DOMContentLoaded', function () {
    var btn = document.createElement('button');
    btn.id = 'nd-theme';
    btn.setAttribute('aria-label', 'Toggle dark/light theme');
    btn.innerHTML = '<span class="dotind"></span><span class="lbl-txt">' + label() + '</span>';
    btn.addEventListener('click', function () {
      var next = root.getAttribute('data-theme') === 'light' ? 'dark' : 'light';
      apply(next);
      try { localStorage.setItem(KEY, next); } catch (e) {}
      btn.querySelector('.lbl-txt').textContent = label();
    });
    document.body.appendChild(btn);
  });
})();
