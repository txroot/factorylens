(() => {
  document.addEventListener('DOMContentLoaded', () => {
    console.log("video-player.js loaded"); 

    const modalVideo   = document.getElementById('modal-video');
    const videoModalEl = document.getElementById('videoModal');
    const bsModal      = new bootstrap.Modal(videoModalEl);

    // Play button
    document.querySelectorAll('.play-btn').forEach(btn => {
      btn.addEventListener('click', async () => {
        const camId   = btn.dataset.camId;
        const url     = btn.dataset.streamUrl;
        const spinner = btn.parentElement.querySelector('.spinner-border');

        console.log("Play clicked, camId:", camId, "url:", url);
        spinner.classList.remove('d-none');

        try {
          const res  = await fetch(`/apps/video-player/start/${camId}`, {method:'POST'});
          const data = await res.json();
          const hlsUrl = data.hls_url;
          console.log('HLS URL ready:', hlsUrl);

          loadHls(hlsUrl);
          bsModal.show();
        } catch (err) {
          console.error('Error starting stream:', err);
          alert('Unable to start stream');
        } finally {
          spinner.classList.add('d-none');
        }
      });
    });

    // Check URL button
    document.querySelectorAll('.check-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        const url = btn.dataset.streamUrl;
        console.log("Check URL:", url);
        alert("Stream URL:\n" + url);
      });
    });

    // Cleanup on modal close
    videoModalEl.addEventListener('hidden.bs.modal', () => {
      modalVideo.pause();
      modalVideo.removeAttribute('src');
      modalVideo.load();
    });

    function loadHls(src, retry = true) {
      if (window.Hls && Hls.isSupported()) {
        const hls = new Hls();
        hls.loadSource(src);
        hls.attachMedia(modalVideo);
        hls.on(Hls.Events.MANIFEST_PARSED, () => {
          console.log("Manifest parsed, playing");
          modalVideo.play();
        });
        hls.on(Hls.Events.ERROR, (_, data) => {
          if (retry && data.type === Hls.ErrorTypes.NETWORK_ERROR) {
            console.warn("Network error, retrying in 1.5s");
            setTimeout(() => loadHls(src, false), 1500);
          }
        });
      } else if (modalVideo.canPlayType('application/vnd.apple.mpegurl')) {
        modalVideo.src = src;
        modalVideo.addEventListener('loadedmetadata', () => modalVideo.play(), {once:true});
      } else {
        alert('HLS not supported in this browser');
      }
    }
  });
})();
