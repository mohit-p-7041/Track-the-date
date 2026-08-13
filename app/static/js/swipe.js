/* Swipe to act on a batch, on the Due screen.
 *
 *   right -> left   delete
 *   left  -> right  mark discounted
 *
 * This is a shortcut, not a mechanism. Every row already carries the two forms
 * and the buttons that submit them, so the laptop (no touchscreen) and a browser
 * with JS off both work exactly the same way. All this does is decide that a
 * finger movement meant one of those buttons.
 *
 * No transitions, by decision — the row follows the finger while it is down,
 * which is direct manipulation rather than animation, and snaps back instantly
 * when it is lifted. Nothing here animates on its own.
 *
 * Deleting a batch that is still good and still full price asks first. The
 * question comes from data-confirm, which the server puts there only for those
 * rows (see needs_confirmation in app/catalogue.py) — the rule lives in one
 * place and this file does not re-derive it from dates.
 */
(function () {
  'use strict';

  // Far enough that scrolling a long list never trips it, short enough to do
  // one-handed while holding stock. Tuned on an iPad, not calculated.
  var THRESHOLD = 64;

  // Past this much vertical travel it is a scroll, whatever the horizontal was.
  var VERTICAL_LIMIT = 24;

  function submit(row, which) {
    var form = row.querySelector('form[data-action="' + which + '"]');
    if (form) {
      form.submit();
    }
  }

  /* Reveal the question inside the row. Never window.confirm(): it blocks the
     page, it cannot be styled, and on an iPad it reads like a browser error. */
  function ask(row, question) {
    var panel = row.querySelector('.swipe-confirm');
    if (!panel || !panel.hidden) {
      return;
    }

    panel.textContent = '';

    var text = document.createElement('span');
    text.textContent = question + ' ';
    panel.appendChild(text);

    var yes = document.createElement('button');
    yes.type = 'button';
    yes.className = 'btn btn-small';
    yes.textContent = 'Yes, delete';
    yes.addEventListener('click', function () {
      submit(row, 'delete');
    });
    panel.appendChild(yes);

    var no = document.createElement('button');
    no.type = 'button';
    no.className = 'btn btn-quiet btn-small';
    no.textContent = 'Keep';
    no.addEventListener('click', function () {
      panel.hidden = true;
      panel.textContent = '';
    });
    panel.appendChild(no);

    panel.hidden = false;
  }

  function requestDelete(row) {
    var question = row.getAttribute('data-confirm');
    if (question) {
      ask(row, question);
    } else {
      submit(row, 'delete');
    }
  }

  function bind(row) {
    var startX = 0;
    var startY = 0;
    var dx = 0;
    var tracking = false;

    function offset(value) {
      row.style.transform = value ? 'translateX(' + value + 'px)' : '';
    }

    row.addEventListener('touchstart', function (event) {
      if (event.touches.length !== 1) {
        return;
      }
      startX = event.touches[0].clientX;
      startY = event.touches[0].clientY;
      dx = 0;
      tracking = true;
    }, { passive: true });

    row.addEventListener('touchmove', function (event) {
      if (!tracking) {
        return;
      }
      var touch = event.touches[0];
      var moveY = Math.abs(touch.clientY - startY);
      if (moveY > VERTICAL_LIMIT) {
        // They are scrolling the list. Let go of the row and stay out of it.
        tracking = false;
        dx = 0;
        offset(0);
        return;
      }
      dx = touch.clientX - startX;
      offset(dx);
    }, { passive: true });

    row.addEventListener('touchend', function () {
      if (!tracking) {
        return;
      }
      tracking = false;
      offset(0);

      if (dx <= -THRESHOLD) {
        requestDelete(row);
      } else if (dx >= THRESHOLD) {
        submit(row, 'discount');
      }
      // Anything shorter was not a swipe. The row is already back in place.
    });

    row.addEventListener('touchcancel', function () {
      tracking = false;
      dx = 0;
      offset(0);
    });

    /* A swipe that starts on the product link would otherwise navigate on the
       way up. Swallow that one click, and only that one. */
    var link = row.querySelector('.item-body');
    if (link) {
      link.addEventListener('click', function (event) {
        if (Math.abs(dx) >= THRESHOLD) {
          event.preventDefault();
        }
      });
    }
  }

  /* The Delete button asks the same question as the gesture, so a row that
     needs confirming behaves the same however it was reached. Without this the
     button would delete outright while the swipe asked — the mouse path being
     the less careful one, which is backwards. */
  function guardDeleteButtons(row) {
    var form = row.querySelector('form[data-action="delete"]');
    if (!form || !row.getAttribute('data-confirm')) {
      return;
    }
    form.addEventListener('submit', function (event) {
      event.preventDefault();
      ask(row, row.getAttribute('data-confirm'));
    });
  }

  var rows = document.querySelectorAll('.item.swipe');
  for (var i = 0; i < rows.length; i += 1) {
    guardDeleteButtons(rows[i]);
    if ('ontouchstart' in window) {
      bind(rows[i]);
    }
  }
})();
