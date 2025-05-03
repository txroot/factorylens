(() => {
  document.addEventListener('DOMContentLoaded', () => {
    console.log('video‑player.js loaded');

    /* ------------------------------------------------- helpers */
    const clipboardCopy = async text => {
      try {
        await navigator.clipboard.writeText(text);
        bootstrap.Toast ? new bootstrap.Toast(
          Object.assign(document.createElement('div'), {
            className: 'toast align-items-center text-bg-success border-0 position-fixed bottom-0 end-0 m-3',
            role: 'alert',
            innerHTML: `<div class="d-flex"><div class="toast-body">Copied!</div></div>`
          })
        ).show() : alert('Copied!');
      } catch (e) { alert('Copy failed'); }
    };

    /* ------------------------------------------------- popovers */
    document.querySelectorAll('.url-popover').forEach(btn => {
      const url = btn.dataset.url;
      const html   =
        `<div class="d-flex align-items-center">
           <code class="me-2 flex-grow-1" style="word-break:break-all;">${url}</code>
           <button class="btn btn-sm btn-light copy-btn" data-url="${url}">
             <i class="ti ti-copy"></i>
           </button>
         </div>`;
      new bootstrap.Popover(btn, {
        html: true,
        trigger: 'focus',
        placement: 'auto',
        title: 'URL',
        content: html
      });
    });

    // delegate copy‑btn clicks
    document.body.addEventListener('click', e => {
      if (e.target.closest('.copy-btn')) {
        const url = e.target.closest('.copy-btn').dataset.url;
        clipboardCopy(url);
      }
    });

    /* ------------------------------------------------- snapshot refresh */
    const snapshotModal   = new bootstrap.Modal('#snapshotModal');
    const snapshotImgElem = document.getElementById('snapshot-img');

    document.querySelectorAll('.snapshot-btn').forEach(btn => {
      btn.addEventListener('click', async () => {
        const camId = btn.dataset.camId;
        const src   = `/apps/video-player/snapshot/${camId}?t=${Date.now()}`; // cache‑bust
        snapshotImgElem.src = src;
        snapshotModal.show();
      });
    });

    /* ------------------------------------------------- play in modal */
    const videoModalEl = document.getElementById('videoModal');
    const modalVideo   = document.getElementById('modal-video');
    const bsModal      = new bootstrap.Modal(videoModalEl);

    document.querySelectorAll('.play-btn').forEach(btn => {
      btn.addEventListener('click', async () => {
        const camId   = btn.dataset.camId;
        const spinner = btn.parentElement.querySelector('.spinner-border');
        spinner.classList.remove('d-none');

        try {
          const res  = await fetch(`/apps/video-player/start/${camId}`, { method: 'POST' });
          const data = await res.json();
          const hlsUrl = data.hls_url;

          attachHls(hlsUrl);
          videoModalEl.dataset.camId = camId;
          bsModal.show();
        } catch (err) {
          console.error(err);
          alert('Unable to start stream');
        } finally {
          spinner.classList.add('d-none');
        }
      });
    });

    // stop ffmpeg when modal hides
    videoModalEl.addEventListener('hidden.bs.modal', () => {
      const camId = videoModalEl.dataset.camId;
      modalVideo.pause();
      modalVideo.removeAttribute('src');
      modalVideo.load();
      if (camId) fetch(`/apps/video-player/stop/${camId}`, { method: 'POST' });
    });

    /* ------------------------------------------------- snapshot loader hide */
    document.querySelectorAll('.snapshot-img').forEach(img => {
      img.addEventListener('load', () => {
        document.getElementById(`spinner-${img.dataset.camId}`).classList.add('d-none');
      });
    });

    /* ------------------------------------------------- hls attach helper */
    function attachHls(src, retry = true) {
      if (window.Hls && Hls.isSupported()) {
        const hls = new Hls();
        hls.loadSource(src);
        hls.attachMedia(modalVideo);
        hls.on(Hls.Events.MANIFEST_PARSED, () => modalVideo.play());
        hls.on(Hls.Events.ERROR, (_, data) => {
          if (retry && data.type === Hls.ErrorTypes.NETWORK_ERROR) {
            console.warn('manifest not ready – retry once');
            setTimeout(() => attachHls(src, false), 1500);
          }
        });
      } else if (modalVideo.canPlayType('application/vnd.apple.mpegurl')) {
        modalVideo.src = src;
        modalVideo.addEventListener('loadedmetadata', () => modalVideo.play(), { once: true });
      } else {
        alert('HLS not supported in this browser');
      }
    }
  });
})();
