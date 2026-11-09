// The page shown inside the WebView of the in-app PDF viewer (FR-809).
// It loads with the API as its base URL, so pdf.js (served by our backend, no third-party script
// sees the token) and the file are same-origin. Messages go back to the app as JSON:
// { type: 'page', page, total } | { type: 'auth' } | { type: 'error', message }

// Safe inside a <script>: a value can't close the tag. JSON reads this escape back as a plain <.
const LT_ESCAPE = String.fromCharCode(92) + 'u003c'
const toScript = (value) => JSON.stringify(value).replaceAll('<', LT_ESCAPE)

export function buildPdfViewerHtml({ base, fileUrl, token, page }) {
  const config = toScript({ fileUrl: `${base}${fileUrl}`, token, page, workerSrc: `${base}/static/pdfjs/pdf.worker.min.js` })
  return `<!doctype html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=5">
<style>
  html, body { margin: 0; background: #525659; }
  .page { position: relative; margin: 0 auto 8px; background: #fff; }
  canvas { display: block; width: 100%; height: 100%; }
</style>
</head>
<body>
<div id="pages"></div>
<script>
  var config = ${config};
  function post(message) { window.ReactNativeWebView.postMessage(JSON.stringify(message)); }
  function fail(message) { post({ type: 'error', message: message }); }
</script>
<script src="${base}/static/pdfjs/pdf.min.js" onerror="fail('The PDF viewer could not load.')"></script>
<script>
(function () {
  if (!window.pdfjsLib) return;
  pdfjsLib.GlobalWorkerOptions.workerSrc = config.workerSrc;
  var container = document.getElementById('pages');
  var width = document.documentElement.clientWidth;
  var scaleLimit = Math.min(window.devicePixelRatio || 1, 2);

  pdfjsLib.getDocument({
    url: config.fileUrl,
    httpHeaders: { Authorization: 'Bearer ' + config.token },
    isEvalSupported: false
  }).promise.then(function (doc) {
    var numbers = [];
    for (var n = 1; n <= doc.numPages; n++) numbers.push(n);
    return Promise.all(numbers.map(function (n) { return doc.getPage(n); })).then(function (pages) {
      show(doc, pages);
    });
  }).catch(function (err) {
    if (err && err.status === 401) post({ type: 'auth' });
    else fail(err && err.status === 403 ? 'You are not enrolled in this course.' : 'This PDF could not be opened.');
  });

  function show(doc, pages) {
    var boxes = pages.map(function (page) {
      var size = page.getViewport({ scale: 1 });
      var box = document.createElement('div');
      box.className = 'page';
      box.style.width = width + 'px';
      box.style.height = Math.round(width * size.height / size.width) + 'px';
      box.pdfPage = page;
      container.appendChild(box);
      return box;
    });

    // Draw only pages near the screen, and free the rest, so long files don't run out of memory
    var observer = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        var box = entry.target;
        if (entry.isIntersecting && !box.firstChild) draw(box);
        if (!entry.isIntersecting && box.firstChild) {
          if (box.task) box.task.cancel();
          box.removeChild(box.firstChild);
        }
      });
    }, { rootMargin: '150% 0px' });
    boxes.forEach(function (box) { observer.observe(box); });

    var target = Math.min(Math.max(config.page || 1, 1), doc.numPages);
    boxes[target - 1].scrollIntoView();

    var current = 0;
    function report() {
      var middle = window.scrollY + window.innerHeight / 2;
      var page = 1;
      boxes.forEach(function (box, i) { if (box.offsetTop <= middle) page = i + 1; });
      if (page !== current) {
        current = page;
        post({ type: 'page', page: page, total: doc.numPages });
      }
    }
    window.addEventListener('scroll', report, { passive: true });
    post({ type: 'page', page: target, total: doc.numPages });
    current = target;
  }

  function draw(box) {
    var size = box.pdfPage.getViewport({ scale: 1 });
    var viewport = box.pdfPage.getViewport({ scale: scaleLimit * width / size.width });
    var canvas = document.createElement('canvas');
    canvas.width = viewport.width;
    canvas.height = viewport.height;
    box.appendChild(canvas);
    box.task = box.pdfPage.render({ canvasContext: canvas.getContext('2d'), viewport: viewport });
    box.task.promise.catch(function () { /* cancelled when scrolled away */ });
  }
})();
</script>
</body>
</html>`
}
