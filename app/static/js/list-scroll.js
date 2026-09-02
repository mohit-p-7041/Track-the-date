/* Return to the same place in a long list.

   Tapping a product opens its detail screen; coming back — whether by the
   browser's back button, the redirect after an edit, or the Products link in
   the nav — used to land at the top of the list every time. On a 100-row list
   that is a scroll back down to wherever you were, on every single item.

   The browser restores scroll for a plain back navigation on its own, but not
   for the redirect after saving an edit and not for a fresh click on the
   Products link, and those are exactly the two ways staff come back. So the
   position is remembered here, keyed by the full list URL, and put back when
   the same list is shown again.

   Keyed by pathname + search so a *different* list — a new search, a category
   filter, "show all" — starts at the top as it should; only returning to the
   identical list restores where you were. sessionStorage, so it is per tab and
   clears itself when the tab closes.

   Enhancement only. Without JavaScript the list simply behaves as it did
   before — the top of the page. */

(function () {
  'use strict';

  var list = document.querySelector('.items');
  if (!list || !window.sessionStorage) return;

  var key = 'list-scroll:' + location.pathname + location.search;

  function save() {
    try {
      sessionStorage.setItem(key, String(window.scrollY));
    } catch (e) {
      /* Private mode or a full store — losing the position is not worth a
         thrown error on top of it. */
    }
  }

  /* Restore before the first paint where we can, so there is no visible jump
     from the top down to the saved spot. */
  try {
    var saved = sessionStorage.getItem(key);
    if (saved !== null) {
      /* scrollRestoration 'manual' stops the browser fighting us with its own
         restore on a back navigation; ours is the one that also covers the
         redirect and the nav link. */
      if ('scrollRestoration' in history) history.scrollRestoration = 'manual';
      window.scrollTo(0, parseInt(saved, 10) || 0);
    }
  } catch (e) { /* nothing stored, or no access */ }

  /* Save on the way out. pagehide fires for a normal navigation and for the
     bfcache path; a click on a row is a navigation, so it is covered too. */
  window.addEventListener('pagehide', save);
})();
