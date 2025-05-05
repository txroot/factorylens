/* global $, bootstrap */

$(function () {
  const connectorUrl = '/storage/connector';
  const baseUrl      = '/assets/vendor/elfinder/';
  let   fmInstance   = null;     // holds current elFinder instance

  // the pill‑bar buttons all carry data‑dev="ID"
  $('#deviceTabs').on('shown.bs.tab', 'button[data-bs-toggle="pill"]', function () {
    const devId = this.dataset.dev;
    initElfinderFor(devId);
  });

  // kick‑off on the first (already active) tab
  const firstActive = $('#deviceTabs .nav-link.active').data('dev');
  if (firstActive) initElfinderFor(firstActive);

  // ───────────────────────────────────────────────────────────
  function initElfinderFor (devId) {
    // destroy previous instance cleanly
    if (fmInstance) {
      try { fmInstance.destroy(); } catch (e) {}
      $('#fileExplorer').empty();
    }

    const opts = {
      url        : connectorUrl,
      customData : { dev: devId },
      baseUrl    : baseUrl,
      cssAutoLoad: false,
      debug      : true,

      commands   : [
        'open','reload','home','up','back','forward',
        'select','copy','cut','paste','rm',
        'mkdir','upload','download','quicklook'
      ],
      uiOptions  : {
        cwd : { multiSelect: true, multiDrag: true },
        toolbar : [
          ['copy','cut','paste','rm'],
          ['mkdir','upload','download','quicklook'],
          ['back','forward','up','reload']
        ]
      },
      commandsOptions : {
        quicklook : {
          autoLoad        : true,
          previewMimeRegex: /^(image|text)\//
        }
      },

      handlers : {
        init : () => console.log('elFinder started on dev', devId),
        request : (e, data) => {
          console.log('request', data.cmd, data);
        }
      }
    };

    fmInstance = $('#fileExplorer').elfinder(opts).elfinder('instance');
  }
});
