// public/js/apps/file-explorer.js
// Initialize elFinder with proper options and debug logging

$(function() {
  // URLs and paths
  const connectorUrl = '/storage/connector';
  const baseUrl      = '/assets/vendor/elfinder/';
  
  // Debug: log initial context
  console.log('About to init elFinder…', {
    connectorUrl: connectorUrl,
    baseUrl: baseUrl,
    selectedDevice: $('#deviceSelect').val()
  });

  // Build elFinder options
  const options = {
    // Backend connector URL
    url        : connectorUrl,
    // Pass selected device ID to connector
    customData : { dev: $('#deviceSelect').val() },
    // Location of elFinder's CSS, images, etc.
    baseUrl    : baseUrl,
    // We manually included CSS in the template
    cssAutoLoad: false,
    // Handlers for runtime events
    debug      : true,
    handlers   : {
      init: function(e, fm) {
        // log high-level init
        console.log('elFinder init:', e, fm);
      },
      request: function(e, data) {
        // logs every AJAX request and raw response text
        console.log('elFinder request:', data.cmd, data);
        console.log('Raw backend response:', data.xhr.responseText);
      },
      load: function(e, fm) {
        $('#deviceSelect').off('change').on('change', function() {
          fm.options.customData.dev = this.value;
          fm.exec('reload');
        });
      }
    }
  };

  // Debug: show the full options object
  console.log('elFinder options:', options);

  // Initialize elFinder
  try {
    const fmInstance = $('#fileExplorer')
      .elfinder(options)
      .elfinder('instance');
    console.log('elFinder initialized:', fmInstance);
  } catch (err) {
    console.error('elFinder init error:', err);
  }
});
