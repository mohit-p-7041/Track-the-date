/* Barcode scanning with the camera, for the aisles.

   The counter has a USB gun and that path is the one used hundreds of times a
   week. This is the other half: someone walking the shelves with an iPad, who
   has no gun and no keyboard worth typing on.

   Two things this deliberately does not do.

   It does not add a second way to add a batch. A decoded barcode is put into
   the same field the gun types into and the same form is submitted, so the
   lookup, the duplicate check and everything after it are one code path. A
   camera that quietly skipped the duplicate check would be worse than no
   camera.

   It does not load the decoding library up front. ZXing is 336 KB, and the
   gun path must not pay for a feature it never uses — so the script is
   injected on the first tap of the button and not before. Someone scanning at
   the counter downloads nothing extra, ever.

   The button is hidden in the HTML and revealed here, only where getUserMedia
   exists. That means a secure context: the laptop on localhost, and the iPads
   once the mkcert certificates are in (see docs/HTTPS-SETUP.md). Where a
   camera could not be opened the button is simply absent rather than present
   and broken. */

(function () {
  'use strict';

  var VENDOR = '/static/vendor/zxing-0.21.3.min.js';

  var button = document.getElementById('scan-camera');
  var panel = document.getElementById('scan-panel');
  var view = document.getElementById('scan-view');
  var note = document.getElementById('scan-note');
  var cancel = document.getElementById('scan-cancel');
  var field = document.getElementById('barcode');
  var form = document.getElementById('barcode-form');

  if (!button || !panel || !view || !note || !cancel || !field || !form) return;
  if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) return;

  button.hidden = false;

  var reader = null;
  var loading = null;
  var busy = false;

  function loadLibrary() {
    if (window.ZXing) return Promise.resolve();
    if (loading) return loading;
    loading = new Promise(function (resolve, reject) {
      var script = document.createElement('script');
      script.src = VENDOR;
      script.onload = resolve;
      script.onerror = function () {
        loading = null;                  // let a later tap try again
        reject(new Error('the scanner library did not load'));
      };
      document.head.appendChild(script);
    });
    return loading;
  }

  /* Only the barcodes a servo actually stocks. Leaving QR and Data Matrix on
     makes every frame slower to decode and invites a misread off the printing
     on a packet. */
  function newReader() {
    var formats = ZXing.BarcodeFormat;
    var hints = new Map();
    hints.set(ZXing.DecodeHintType.POSSIBLE_FORMATS, [
      formats.EAN_13,
      formats.EAN_8,
      formats.UPC_A,
      formats.UPC_E,
      formats.CODE_128
    ]);
    return new ZXing.BrowserMultiFormatReader(hints);
  }

  function stop() {
    if (reader) {
      reader.reset();                    // releases the camera
      reader = null;
    }
    panel.hidden = true;
    busy = false;
  }

  function found(text) {
    var barcode = String(text).trim();
    if (!barcode) return;
    stop();
    field.value = barcode;
    /* The same GET the gun's own Enter fires. One route, one lookup, one
       duplicate check — a decoded barcode is indistinguishable from a typed
       one by the time it reaches the server. */
    form.submit();
  }

  button.addEventListener('click', function () {
    if (busy) return;
    busy = true;
    panel.hidden = false;
    note.textContent = 'Starting the camera…';

    loadLibrary().then(function () {
      reader = newReader();
      return reader.decodeFromConstraints(
        { video: { facingMode: 'environment' } },
        view,
        function (result) {
          /* Called for every frame. Without a barcode in shot it is handed an
             exception, which is the normal state and not worth reacting to. */
          if (result) found(result.getText());
        }
      );
    }).then(function () {
      note.textContent = 'Hold the barcode in the box.';
    }).catch(function () {
      /* No camera, permission refused, or the library did not load. Say so
         and get out of the way — the field behind this still takes a typed
         barcode, and that has to keep working. */
      note.textContent = 'The camera did not open. Type the barcode instead.';
      if (reader) { reader.reset(); reader = null; }
      busy = false;
      window.setTimeout(function () {
        panel.hidden = true;
        field.focus();
      }, 2500);
    });
  });

  cancel.addEventListener('click', function () {
    stop();
    field.focus();
  });

  /* An iPad going to sleep or the page being swapped out leaves the camera
     light on otherwise. */
  window.addEventListener('pagehide', stop);
})();
