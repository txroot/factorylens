$(function () {
  const $select = $('#deviceSelect');

  $('#fileExplorer').elfinder({
    baseUrl     : '/public/vendor/elfinder/',   // where css/img live in the browser
    cssAutoLoad : false,                        // we already linked the css manually
    url         : '/storage/connector',
    customData  : { dev: $select.val() },

    handlers : {
      // reload on device change
      load : function (e, fm) {
        $select.on('change', function () {
          fm.options.customData.dev = this.value;
          fm.exec('reload');
        });
      }
    }
  });
});
