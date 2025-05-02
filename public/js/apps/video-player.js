// public/js/apps/video-player.js

(() => {
    document.addEventListener('DOMContentLoaded', () => {
      const modalVideo = document.getElementById('modal-video');
  
      // When a play button is clicked
      document.querySelectorAll('.play-btn').forEach(btn => {
        btn.addEventListener('click', () => {
          const camId = btn.dataset.camId;
          const url = btn.dataset.streamUrl;
  
          // Trigger backend transcoding
          fetch(`/apps/video-player/start/${camId}`, { method: 'POST' })
            .then(res => res.json())
            .then(data => {
              const hlsUrl = data.hls_url;
  
              // Attach to video element
              if (Hls.isSupported()) {
                const hls = new Hls();
                hls.loadSource(hlsUrl);
                hls.attachMedia(modalVideo);
                hls.on(Hls.Events.MANIFEST_PARSED, () => modalVideo.play());
              } else if (modalVideo.canPlayType('application/vnd.apple.mpegurl')) {
                modalVideo.src = hlsUrl;
                modalVideo.addEventListener('loadedmetadata', () => modalVideo.play());
              }
            })
            .catch(err => console.error('Stream start failed:', err));
        });
      });
  
      // Cleanup on modal hide
      const modalEl = document.getElementById('videoModal');
      modalEl.addEventListener('hidden.bs.modal', () => {
        modalVideo.pause();
        modalVideo.removeAttribute('src');
        modalVideo.load();
      });
    });
  })();