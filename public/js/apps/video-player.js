// public/js/apps/video-player.js

(() => {
  document.addEventListener('DOMContentLoaded', () => {

    /* ---------------------------- Toast ---------------------------- */
    function showToast(message, variant = 'success') {
      const toastEl = document.createElement('div');
      toastEl.className = `toast align-items-center text-bg-${variant} border-0 position-fixed bottom-0 end-0 m-3`;
      toastEl.role = 'alert';
      toastEl.innerHTML = `
        <div class="d-flex">
          <div class="toast-body">${message}</div>
          <button type="button" class="btn-close btn-close-white ms-auto me-2" data-bs-dismiss="toast"></button>
        </div>`;
      document.body.appendChild(toastEl);
      new bootstrap.Toast(toastEl, { delay: 2000 }).show();
    }

    /* ------------------------ Clipboard Copy ------------------------ */
    async function clipboardCopy(text) {
      try {
        await navigator.clipboard.writeText(text);
        showToast('Copied to clipboard');
      } catch {
        showToast('Copy failed', 'danger');
      }
    }

    document.body.addEventListener('click', e => {
      if (e.target.closest('.copy-btn')) {
        const btn = e.target.closest('.copy-btn');
        const input = btn.closest('.input-group').querySelector('textarea, input');
        if (input) clipboardCopy(input.value.trim());
      }
      if (e.target.closest('.hide-url-btn')) {
        const btn = e.target.closest('.hide-url-btn');
        const panel = document.getElementById(btn.dataset.target);
        if (panel) bootstrap.Collapse.getOrCreateInstance(panel).hide();
      }
    });

    /* ------------------------- Snapshot Modal ----------------------- */
    const snapshotModalEl = document.getElementById('snapshotModal');
    const snapshotModal   = new bootstrap.Modal(snapshotModalEl);
    const snapshotImg     = document.getElementById('snapshot-img');
    const spinnerOverlay  = document.getElementById('snapshot-spinner');
    const titleEl         = document.getElementById('snapshotModalTitle');
    const downloadBtn     = document.getElementById('snapshot-download-btn');
    const pdfBtn          = document.getElementById('snapshot-pdf-btn');
    const fullBtn         = document.getElementById('snapshot-full-btn');
    let currentFilenameBase = '';

    function openSnapshotModal(camId, streamId = null) {
      const now = new Date();
      const ts = now.toISOString().replace('T',' ').split('.')[0];
      currentFilenameBase = `snapshot_${camId}_${ts.replace(/[: ]/g,'_')}`;

      titleEl.textContent = `Snapshot (${ts})`;
      spinnerOverlay.classList.remove('d-none');
      snapshotImg.classList.add('d-none');

      let url = `/apps/video-player/snapshot/${camId}`;
      url += streamId ? `?stream_id=${streamId}` : `?t=${Date.now()}`;

      snapshotImg.src = url;
      downloadBtn.href = url;
      downloadBtn.download = `${currentFilenameBase}.jpg`;
      pdfBtn.dataset.snapshotSrc = url;
      snapshotModal.show();
    }

    document.body.addEventListener('click', e => {
      const byUrl = e.target.closest('.snapshot-url-item');
      if (byUrl) {
        e.preventDefault();
        openSnapshotModal(byUrl.dataset.camId);
      }
      const byStream = e.target.closest('.snapshot-stream-item');
      if (byStream) {
        e.preventDefault();
        openSnapshotModal(byStream.dataset.camId, byStream.dataset.streamId);
      }
    });

    document.querySelectorAll('.snapshot-btn').forEach(btn => {
      btn.addEventListener('click', () => openSnapshotModal(btn.dataset.camId));
    });

    snapshotImg.addEventListener('load', () => {
      spinnerOverlay.classList.add('d-none');
      snapshotImg.classList.remove('d-none');
    });

    fullBtn.addEventListener('click', () => {
      if (!document.fullscreenElement) {
        snapshotImg.requestFullscreen().catch(() =>{});
      } else {
        document.exitFullscreen().catch(() =>{});
      }
    });

    pdfBtn.addEventListener('click', async e => {
      e.preventDefault();
      spinnerOverlay.classList.remove('d-none');
      try {
        const jpgRes  = await fetch(pdfBtn.dataset.snapshotSrc);
        const jpgBlob = await jpgRes.blob();
        const form    = new FormData();
        form.append('image', jpgBlob, `${currentFilenameBase}.jpg`);

        const pdfRes = await fetch('/apps/video-player/snapshot/pdf', {
          method: 'POST',
          body: form
        });
        if (!pdfRes.ok) throw new Error('PDF generation failed');

        const pdfBlob = await pdfRes.blob();
        const url     = URL.createObjectURL(pdfBlob);
        const a       = document.createElement('a');
        a.href        = url;
        a.download    = `${currentFilenameBase}.pdf`;
        document.body.appendChild(a);
        a.click();
        a.remove();
        URL.revokeObjectURL(url);
      } catch {
        showToast('Failed to generate PDF', 'danger');
      } finally {
        spinnerOverlay.classList.add('d-none');
      }
    });


    /* ---------------------- Video (HLS) Modal ----------------------- */
    const videoModalEl = document.getElementById('videoModal');
    const modalVideo   = document.getElementById('modal-video');
    const bsVideoModal = new bootstrap.Modal(videoModalEl);

    function attachHls(src, retry = true) {
      if (window.Hls && Hls.isSupported()) {
        const hls = new Hls();
        hls.loadSource(src);
        hls.attachMedia(modalVideo);
        hls.on(Hls.Events.MANIFEST_PARSED, () => modalVideo.play());
        hls.on(Hls.Events.ERROR, (_, data) => {
          if (retry && data.type === Hls.ErrorTypes.NETWORK_ERROR) {
            setTimeout(() => attachHls(src, false), 1500);
          }
        });
      } else if (modalVideo.canPlayType('application/vnd.apple.mpegurl')) {
        modalVideo.src = src;
        modalVideo.addEventListener('loadedmetadata', () => modalVideo.play(), { once: true });
      } else {
        showToast('HLS not supported', 'warning');
      }
    }

    // Unified “play” handler for both main button and dropdown items
    document.body.addEventListener('click', async e => {
      const trigger = e.target.closest('.play-btn, .play-stream-item');
      if (!trigger) return;
      e.preventDefault();

      const camId    = trigger.dataset.camId;
      const streamId = trigger.dataset.streamId;
      const cardBody = trigger.closest('.card-body');
      const spinner  = cardBody && cardBody.querySelector('.spinner-border');
      if (spinner) spinner.classList.remove('d-none');

      try {
        let url = `/apps/video-player/start/${camId}`;
        if (streamId) url += `?stream_id=${streamId}`;
        const res = await fetch(url, { method: 'POST' });
        const { hls_url } = await res.json();

        attachHls(hls_url);
        videoModalEl.dataset.camId = camId;
        bsVideoModal.show();
      } catch {
        showToast('Unable to start stream', 'danger');
      } finally {
        if (spinner) spinner.classList.add('d-none');
      }
    });

    videoModalEl.addEventListener('hidden.bs.modal', () => {
      const camId = videoModalEl.dataset.camId;
      modalVideo.pause();
      modalVideo.removeAttribute('src');
      modalVideo.load();
      if (camId) {
        fetch(`/apps/video-player/stop/${camId}`, { method: 'POST' });
      }
    });

  });
})();
