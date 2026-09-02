/* Filter the products list as you type.

   Without this the search is a form: type, then press Search, then read the
   page that comes back. That is one round trip per attempt, and staff hunting
   for a half-remembered name make several. This fetches the results a beat
   after each keystroke and drops them straight into the page, so the list
   narrows under your fingers.

   It reuses the ordinary /products query with `partial=1`, which returns just
   the list — the same rows the full page renders, from the same template. So
   the scoring that lets "cool ridge" surface C/RIDGE WATER 1L, the 100-row cap
   and its "show all" link, the duplicate-free ordering: all of it is the
   server's, unchanged, and there is no second search to keep in step.

   Enhancement only, three times over. If the script does not load, the form
   still submits and the Search button still works. If a fetch fails, the last
   good list stays on screen and the button is still there to fall back on. And
   the address bar is kept in step with what is shown, so a reload or a tap
   back into the list lands on the same results rather than an empty page. */

(function () {
  'use strict';

  var form = document.getElementById('product-search');
  var input = document.getElementById('product-q');
  var results = document.getElementById('product-results');
  if (!form || !input || !results) return;
  if (!window.fetch || !window.history || !history.replaceState) return;

  /* The category filter rides along as a hidden field when one is active, so
     typing narrows within the chosen category rather than jumping out of it. */
  var categoryField = form.querySelector('input[name="category"]');

  var timer = null;
  /* Every request carries a sequence number; a response is only used if it is
     the newest asked for. Otherwise a slow lookup for "mi" could land after
     "milk" and overwrite the right list with a staler one. */
  var latest = 0;

  function url(query, forFetch) {
    var parts = [];
    if (query) parts.push('q=' + encodeURIComponent(query));
    if (categoryField && categoryField.value) {
      parts.push('category=' + encodeURIComponent(categoryField.value));
    }
    if (forFetch) parts.push('partial=1');
    return '/products' + (parts.length ? '?' + parts.join('&') : '');
  }

  function run() {
    var query = input.value.trim();
    var mine = ++latest;

    fetch(url(query, true), { headers: { 'X-Requested-With': 'fetch' } })
      .then(function (response) {
        if (!response.ok) throw new Error('search failed');
        return response.text();
      })
      .then(function (html) {
        if (mine !== latest) return;        // a newer keystroke already won
        results.innerHTML = html;
        /* Keep the address bar honest without adding a history entry per
           keystroke — replaceState, not pushState. A reload or a return to
           this list then shows the same results. */
        history.replaceState(null, '', url(query, false));
      })
      .catch(function () {
        /* Leave the current list untouched. The Search button still works. */
      });
  }

  input.addEventListener('input', function () {
    if (timer) clearTimeout(timer);
    /* A short pause so a fast typist fires one request, not one per letter. */
    timer = setTimeout(run, 200);
  });

  /* Enter would otherwise reload the whole page — the live list is already
     there, so just run it now and stay put. */
  form.addEventListener('submit', function (event) {
    event.preventDefault();
    if (timer) clearTimeout(timer);
    run();
  });
})();
