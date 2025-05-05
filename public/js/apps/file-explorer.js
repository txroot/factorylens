/* global $, bootstrap */

$(function () {
  const connectorUrl = '/storage/connector';
  const baseUrl      = '/assets/vendor/elfinder/';
  let   fmInstance   = null;

  // Initialize elFinder against the given device ID
  function initElfinderFor(devId) {
    // Destroy any existing instance
    if (fmInstance) {
      try { fmInstance.destroy(); } catch (_) {}
      $('#fileExplorer').empty();
    }

    const opts = {
      // connector endpoint
      url         : connectorUrl,
      // always include current device
      customData  : { dev: devId },
      baseUrl     : baseUrl,
      cssAutoLoad : false,
      debug       : true,

      // enable core commands
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

  // When you switch tabs, re-init for the new device
  $('#deviceTabs').on('shown.bs.tab', 'button[data-bs-toggle="pill"]', function () {
    initElfinderFor(this.dataset.dev);
  });

  // Kick things off on the first (active) tab
  const firstDev = $('#deviceTabs .nav-link.active').data('dev');
  if (firstDev) initElfinderFor(firstDev);
});
