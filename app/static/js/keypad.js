/* The PIN keypad.
   Enhancement only: without JavaScript the PIN field is a plain input and the
   Sign in button still works. With it, the field goes read-only so an iPad
   never raises its own keyboard over the pad, and four digits submit. */

(function () {
  var field = document.getElementById('pin');
  var keys = document.getElementById('keys');
  var form = document.getElementById('pinform');
  if (!field || !keys || !form) return;

  field.readOnly = true;
  field.value = '';

  function push(digit) {
    if (field.value.length >= 4) return;
    field.value += digit;
    if (field.value.length === 4) form.submit();
  }

  keys.addEventListener('click', function (event) {
    var key = event.target.closest('.key');
    if (!key) return;
    if (key.dataset.digit) push(key.dataset.digit);
    else if (key.dataset.action === 'back') field.value = field.value.slice(0, -1);
    else if (key.dataset.action === 'clear') field.value = '';
  });

  /* The counter laptop has a real keyboard and the scanner gun is plugged
     into it. Typing digits should work there without reaching for the mouse. */
  document.addEventListener('keydown', function (event) {
    if (event.metaKey || event.ctrlKey || event.altKey) return;
    if (event.key >= '0' && event.key <= '9') {
      push(event.key);
      event.preventDefault();
    } else if (event.key === 'Backspace') {
      field.value = field.value.slice(0, -1);
      event.preventDefault();
    }
  });
})();
