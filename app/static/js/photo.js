/* Shrink a photo in the browser before it is uploaded.

   An iPad photo is around 4 MB. Over shop WiFi that is a visible wait for
   something the server is only going to reduce to under 80 KB anyway, so the
   canvas does the bulk of it first and sends roughly a tenth of the bytes.

   Enhancement only. Without JavaScript the form posts the original file and
   Pillow still produces exactly the same stored image — the browser side is
   about the wire, not the result. */

(function () {
  var form = document.getElementById('photo-form');
  if (!form) return;

  var input = document.getElementById('photo');
  var button = form.querySelector('button');
  var canUse = window.FileReader && window.URL &&
               HTMLCanvasElement.prototype.toBlob;
  if (!input || !canUse) return;

  /* Bigger than the 800px the server keeps, so the server still decides the
     final size and a slightly-off browser cannot degrade the stored photo. */
  var MAX_PX = 1400;
  var QUALITY = 0.82;

  function shrink(file) {
    return new Promise(function (resolve, reject) {
      var image = new Image();
      var url = URL.createObjectURL(file);
      image.onload = function () {
        URL.revokeObjectURL(url);
        var scale = Math.min(1, MAX_PX / Math.max(image.width, image.height));
        var canvas = document.createElement('canvas');
        canvas.width = Math.round(image.width * scale);
        canvas.height = Math.round(image.height * scale);
        canvas.getContext('2d').drawImage(image, 0, 0, canvas.width, canvas.height);
        canvas.toBlob(function (blob) {
          resolve(blob || file);
        }, 'image/jpeg', QUALITY);
      };
      image.onerror = function () {
        URL.revokeObjectURL(url);
        reject();
      };
      image.src = url;
    });
  }

  function upload(blob) {
    button.disabled = true;
    button.textContent = 'Saving…';
    var data = new FormData();
    data.append('photo', blob, 'photo.jpg');
    return fetch(form.action, { method: 'POST', body: data, credentials: 'same-origin' })
      .then(function () { window.location.href = form.dataset.done; });
  }

  form.addEventListener('submit', function (event) {
    var file = input.files && input.files[0];
    if (!file) return;                       // nothing chosen; let it post
    event.preventDefault();

    shrink(file).then(upload).catch(function () {
      /* Anything unexpected: fall back to the ordinary upload rather than
         leaving someone staring at a disabled button. */
      button.disabled = false;
      form.submit();
    });
  });

  /* ---- the laptop webcam, and the iPad camera once HTTPS is in ----------

     getUserMedia only exists in a secure context, which localhost counts as
     and a plain http:// network address does not. So this button appears on
     the counter laptop today and on the iPads after the mkcert step, and is
     simply absent where it could not work. The file input covers everything
     else, including Take Photo on iOS. */

  var camera = document.getElementById('camera');
  var panel = document.getElementById('camera-panel');
  var view = document.getElementById('camera-view');
  if (!camera || !panel || !view) return;
  if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) return;

  var stream = null;

  function stop() {
    if (stream) stream.getTracks().forEach(function (t) { t.stop(); });
    stream = null;
    panel.hidden = true;
  }

  camera.hidden = false;

  camera.addEventListener('click', function () {
    navigator.mediaDevices.getUserMedia({
      video: { facingMode: 'environment', width: { ideal: 1600 } }
    }).then(function (media) {
      stream = media;
      view.srcObject = media;
      panel.hidden = false;
      return view.play();
    }).catch(function () {
      camera.textContent = 'No camera';
      camera.disabled = true;
    });
  });

  document.getElementById('camera-cancel').addEventListener('click', stop);

  document.getElementById('camera-take').addEventListener('click', function () {
    if (!stream) return;
    var scale = Math.min(1, MAX_PX / Math.max(view.videoWidth, view.videoHeight));
    var canvas = document.createElement('canvas');
    canvas.width = Math.round(view.videoWidth * scale);
    canvas.height = Math.round(view.videoHeight * scale);
    canvas.getContext('2d').drawImage(view, 0, 0, canvas.width, canvas.height);
    stop();
    canvas.toBlob(function (blob) {
      if (blob) upload(blob);
    }, 'image/jpeg', QUALITY);
  });

  window.addEventListener('pagehide', stop);
})();
