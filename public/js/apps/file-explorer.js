/* global $, bootstrap */

$(function () {
  const connectorUrl = '/storage/connector';
  const baseUrl      = '/assets/vendor/elfinder/';
  let   fmInstance   = null;

  // When a pill is shown, re-init elFinder on that device
  $('#deviceTabs').on('shown.bs.tab', 'button[data-bs-toggle="pill"]', function () {
    initElfinderFor(this.dataset.dev);
  });

  // Kick off on the first (active) pill
  const firstDev = $('#deviceTabs .nav-link.active').data('dev');
  if (firstDev) initElfinderFor(firstDev);

  function initElfinderFor(devId) {
    // destroy previous instance
    if (fmInstance) {
      try { fmInstance.destroy(); } catch (_) {}
      $('#fileExplorer').empty();
    }

    const opts = {
      url         : connectorUrl,
      customData  : () => ({ dev: devId }),  // always send current device
      baseUrl     : baseUrl,
      cssAutoLoad : false,
      debug       : true,

      commands    : [
        'open','reload','home','up','back','forward',
        'select','copy','cut','paste','rm',
        'mkdir','upload','download','quicklook'
      ],

      uiOptions: {
        cwd     : { multiSelect: true, multiDrag: true },
        toolbar : [
          ['copy','cut','paste','rm'],
          ['mkdir','upload','download','quicklook'],
          ['back','forward','up','reload']
        ]
      },

      commandsOptions: {
        quicklook: {
          autoLoad        : true,
          previewMimeRegex: /^(image|text)\//
        }
      },

      handlers: {
        init   : (e, fm)   => console.log('elFinder started on dev', devId),
        request: (e, data) => console.log('elFinder request:', data.cmd, data)
      }
    };

    fmInstance = $('#fileExplorer')
      .elfinder(opts)
      .elfinder('instance');
  }
});
