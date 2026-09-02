/* Tap a product photo to see it full size.

   The thumbnail on the product screen is 84px — enough to recognise, not
   enough to read a label or check it is the right packet. The stored image is
   up to 800px on its long edge, so opening it larger costs no extra download
   and needs no new file: it is the same photo the thumbnail already loaded,
   shown at its own size.

   Deliberately not a `:target`/hash overlay, which would push a history entry
   and scroll a long detail page to the top when it closed. A class toggled in
   JavaScript opens and closes it in place. Tap anywhere on the overlay, or
   press Escape, to close.

   Enhancement only. Without JavaScript the thumbnail is just an image — no
   worse than before this existed. */

(function () {
  'use strict';

  var thumbs = document.querySelectorAll('[data-lightbox]');
  if (!thumbs.length) return;

  var overlay = null;
  var image = null;

  function build() {
    overlay = document.createElement('div');
    overlay.className = 'lightbox';
    overlay.hidden = true;
    image = document.createElement('img');
    overlay.appendChild(image);
    overlay.addEventListener('click', close);
    document.body.appendChild(overlay);
  }

  function open(src, alt) {
    if (!overlay) build();
    image.src = src;
    image.alt = alt || '';
    overlay.hidden = false;
  }

  function close() {
    if (overlay) overlay.hidden = true;
  }

  Array.prototype.forEach.call(thumbs, function (thumb) {
    /* A pointer cursor and a real button role so it reads as tappable. */
    thumb.style.cursor = 'zoom-in';
    thumb.setAttribute('tabindex', '0');
    thumb.addEventListener('click', function () {
      open(thumb.getAttribute('src'), thumb.getAttribute('alt'));
    });
    /* Enter or Space on the focused thumbnail opens it too. */
    thumb.addEventListener('keydown', function (event) {
      if (event.key === 'Enter' || event.key === ' ') {
        event.preventDefault();
        open(thumb.getAttribute('src'), thumb.getAttribute('alt'));
      }
    });
  });

  document.addEventListener('keydown', function (event) {
    if (event.key === 'Escape') close();
  });
})();
