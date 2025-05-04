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

    // Copy URL button
    document.body.addEventListener('click', e => {
      const btn = e.target.closest('.copy-btn');
      if (!btn) return;
      const container = btn.closest('.input-group');
      const field = container && container.querySelector('textarea, input');
      if (field) clipboardCopy(field.value.trim());
    });

    // Hide URL panel
    document.body.addEventListener('click', e => {
      const btn = e.target.closest('.hide-url-btn');
      if (!btn) return;
      const targetId = btn.dataset.target;
      const panel = document.getElementById(targetId);
      if (panel) bootstrap.Collapse.getOrCreateInstance(panel).hide();
    });


    /* ------------------------- Snapshot Modal ----------------------- */
    const snapshotModalEl   = document.getElementById('snapshotModal');
    const snapshotModal     = new bootstrap.Modal(snapshotModalEl);
    const snapshotImg       = document.getElementById('snapshot-img');
    const spinnerOverlay    = document.getElementById('snapshot-spinner');
    const titleEl           = document.getElementById('snapshotModalTitle');
    const downloadBtn       = document.getElementById('snapshot-download-btn');
    const pdfBtn            = document.getElementById('snapshot-pdf-btn');
    const fullBtn           = document.getElementById('snapshot-full-btn');

    let currentFilenameBase = '';

    function openSnapshotModal(camId, streamId=null) {
      const now = new Date();
      const ts = now.toISOString().replace('T',' ').split('.')[0];
      currentFilenameBase = `snapshot_${camId}_${ts.replace(/[: ]/g,'_')}`;

      titleEl.textContent = `Snapshot (${ts})`;
      spinnerOverlay.classList.remove('d-none');
      snapshotImg.classList.add('d-none');

      let url = `/apps/video-player/snapshot/${camId}`;
      if (streamId) url += `?stream_id=${streamId}`; 
      else url += `?t=${Date.now()}`;

      snapshotImg.src = url;
      downloadBtn.href = url;
      downloadBtn.download = `${currentFilenameBase}.jpg`;
      pdfBtn.dataset.snapshotSrc = url;
      snapshotModal.show();
    }

    // Default snapshot button
    document.querySelectorAll('.snapshot-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        const camId = btn.dataset.camId;
        openSnapshotModal(camId);
      });
    });

    // Snapshot via direct URL
    document.body.addEventListener('click', e => {
      const el = e.target.closest('.snapshot-url-item');
      if (!el) return;
      e.preventDefault();
      openSnapshotModal(el.dataset.camId);
    });

    // Snapshot via specific stream
    document.body.addEventListener('click', e => {
      const el = e.target.closest('.snapshot-stream-item');
      if (!el) return;
      e.preventDefault();
      openSnapshotModal(el.dataset.camId, el.dataset.streamId);
    });

    snapshotImg.addEventListener('load', () => {
      spinnerOverlay.classList.add('d-none');
      snapshotImg.classList.remove('d-none');
    });

    fullBtn.addEventListener('click', () => {
      if (!document.fullscreenElement) {
        snapshotImg.requestFullscreen().catch(() => {});
      } else {
        document.exitFullscreen().catch(() => {});
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
      } catch (err) {
        console.error(err);
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

    // Start default stream
    document.querySelectorAll('.play-btn').forEach(btn => {
      btn.addEventListener('click', async () => {
        const camId   = btn.dataset.camId;
        const spinner = btn.parentElement.querySelector('.spinner-border');
        spinner.classList.remove('d-none');
        try {
          const res = await fetch(`/apps/video-player/start/${camId}`, { method: 'POST' });
          const { hls_url } = await res.json();
          attachHls(hls_url);
          videoModalEl.dataset.camId = camId;
          bsVideoModal.show();
        } catch {
          showToast('Unable to start stream', 'danger');
        } finally {
          spinner.classList.add('d-none');
        }
      });
    });

    // Start specific stream
    document.body.addEventListener('click', async e => {
      const el = e.target.closest('.play-stream-item');
      if (!el) return;
      e.preventDefault();
      const camId    = el.dataset.camId;
      const streamId = el.dataset.streamId;
      const spinner  = el.closest('.card-body').querySelector('.spinner-border');
      spinner.classList.remove('d-none');
      try {
        const res = await fetch(
          `/apps/video-player/start/${camId}?stream_id=${streamId}`,
          { method: 'POST' }
        );
        const { hls_url } = await res.json();
        attachHls(hls_url);
        videoModalEl.dataset.camId = camId;
        bsVideoModal.show();
      } catch {
        showToast('Unable to start stream', 'danger');
      } finally {
        spinner.classList.add('d-none');
      }
    });

    // Stop when modal closes
    videoModalEl.addEventListener('hidden.bs.modal', () => {
      const camId = videoModalEl.dataset.camId;
      modalVideo.pause();
      modalVideo.removeAttribute('src');
      modalVideo.load();
      if (camId) fetch(`/apps/video-player/stop/${camId}`, { method: 'POST' });
    });

  });
})();
