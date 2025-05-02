(() => {
    document.addEventListener('DOMContentLoaded', () => {
      const modalVideo   = document.getElementById('modal-video');
      const videoModalEl = document.getElementById('videoModal');
      const bsModal      = new bootstrap.Modal(videoModalEl);
  
      document.querySelectorAll('.play-btn').forEach(btn => {
        btn.addEventListener('click', async () => {
          const camId   = btn.dataset.camId;
          const spinner = btn.parentElement.querySelector('.spinner-border');
          spinner.classList.remove('d-none');
  
          try {
            // 1) ask backend to start / confirm HLS
            const res  = await fetch(`/apps/video-player/start/${camId}`, {method:'POST'});
            const data = await res.json();
            const hlsUrl = data.hls_url;
            console.log('HLS URL ready:', hlsUrl);
  
            // 2) attach to video element
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
  
      videoModalEl.addEventListener('hidden.bs.modal', () => {
        modalVideo.pause();
        modalVideo.removeAttribute('src');
        modalVideo.load();
      });
  
      function loadHls(src, retry = true) {
        if (Hls.isSupported()) {
          const hls = new Hls();
          hls.loadSource(src);
          hls.attachMedia(modalVideo);
          hls.on(Hls.Events.MANIFEST_PARSED, () => modalVideo.play());
          hls.on(Hls.Events.ERROR, (_, data) => {
            if (retry && data.type === Hls.ErrorTypes.NETWORK_ERROR) {
              console.warn('Manifest not ready, retrying once…');
              setTimeout(() => loadHls(src, false), 1500);
            }
          });
        } else if (modalVideo.canPlayType('application/vnd.apple.mpegurl')) {
          modalVideo.src = src;
          modalVideo.addEventListener('loadedmetadata', () => modalVideo.play(), {once:true});
        } else {
          alert('HLS playback not supported in this browser');
        }
      }
    });
  })();
  