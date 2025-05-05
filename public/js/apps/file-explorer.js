// public/js/apps/file-explorer.js
$(function() {
  const connectorUrl = '/storage/connector';
  const baseUrl      = '/assets/vendor/elfinder/';

  // Build elFinder options
  const options = {
    url           : connectorUrl,
    customData    : { dev: $('#deviceSelect').val() },
    baseUrl       : baseUrl,
    cssAutoLoad   : false,
    debug         : true,
    commands      : [
      'open','reload','home','up','back','forward',
      'mkdir','upload','download','quicklook'
    ],
    uiOptions: {
      toolbar: [
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
      init: function(e, fm) {
        // re-bind device selector on every init
        $('#deviceSelect')
          .off('change')
          .on('change', function() {
            fm.options.customData.dev = this.value;
            fm.exec('reload');
          });
      },
      request: function(e, data) {
        console.log('elFinder request:', data.cmd, data);
        console.log('Raw response:', data.xhr.responseText);
      }
    }
  };

  try {
    $('#fileExplorer').elfinder(options);
  } catch (err) {
    console.error('elFinder init error:', err);
  }
});
