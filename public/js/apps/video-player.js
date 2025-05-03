// video-player.js
(() => {
  document.addEventListener('DOMContentLoaded', () => {
    console.log('video-player.js loaded');

    /* ---------------------------- Helpers ---------------------------- */

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

    const clipboardCopy = async text => {
      try {
        await navigator.clipboard.writeText(text);
        showToast('Copied to clipboard');
      } catch {
        showToast('Copy failed', 'danger');
      }
    };

    /* -------------------------- URL Buttons -------------------------- */

    // Copy button (textarea or input)
    document.body.addEventListener('click', e => {
      const btn = e.target.closest('.copy-btn');
      if (btn) {
        const container = btn.closest('.input-group');
        const input = container?.querySelector('input, textarea');
        if (input) clipboardCopy(input.value);
      }
    });

    // Hide button
    document.body.addEventListener('click', e => {
      const btn = e.target.closest('.hide-url-btn');
      if (btn) {
        const el = document.getElementById(btn.dataset.target);
        if (el) bootstrap.Collapse.getOrCreateInstance(el).hide();
      }
    });

    /* ------------------------- Snapshot Modal ------------------------ */

    const snapshotModalEl = document.getElementById('snapshotModal');
    const snapshotModal   = new bootstrap.Modal(snapshotModalEl);
    const snapshotImg     = document.getElementById('snapshot-img');
    const spinnerOverlay  = document.getElementById('snapshot-spinner');
    const fullBtn         = document.getElementById('snapshot-full-btn');
    const downloadBtn     = document.getElementById('snapshot-download-btn');
    const pdfBtn          = document.getElementById('snapshot-pdf-btn');
    const titleEl         = document.getElementById('snapshotModalTitle');

    let currentTimestamp = '';
    let currentFilenameBase = '';

    document.querySelectorAll('.snapshot-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        const camId   = btn.dataset.camId;
        const camName = btn.dataset.camName;

        const now = new Date();
        const ts = [
          now.getFullYear(),
          String(now.getMonth() + 1).padStart(2, '0'),
          String(now.getDate()).padStart(2, '0')
        ].join('-') + '_' +
          String(now.getHours()).padStart(2, '0') + '-' +
          String(now.getMinutes()).padStart(2, '0') + '-' +
          String(now.getSeconds()).padStart(2, '0');
        const titleTs = ts.replace('_', ' / ').replace(/-/g, ':');

        currentTimestamp = ts;
        currentFilenameBase = `snapshot_${camName}_${ts}`;

        titleEl.textContent = `Snapshot ${titleTs}`;
        spinnerOverlay.classList.remove('d-none');
        snapshotImg.classList.add('d-none');

        const jpgUrl = `/apps/video-player/snapshot/${camId}?t=${Date.now()}`;
        snapshotImg.src = jpgUrl;

        downloadBtn.href = jpgUrl;
        downloadBtn.download = `${currentFilenameBase}.jpg`;

        snapshotModal.show();
      });
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

    // PDF generation
    pdfBtn.addEventListener('click', async (e) => {
      e.preventDefault();
      spinnerOverlay.classList.remove('d-none');

      try {
        const resJpg = await fetch(snapshotImg.src);
        const blobJpg = await resJpg.blob();

        const form = new FormData();
        form.append('image', blobJpg, `${currentFilenameBase}.jpg`);

        const resPdf = await fetch('/apps/video-player/snapshot/pdf', {
          method: 'POST',
          body: form
        });

        if (!resPdf.ok) throw new Error(`PDF error: ${resPdf.status}`);

        const pdfBlob = await resPdf.blob();
        const url = URL.createObjectURL(pdfBlob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `${currentFilenameBase}.pdf`;
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

    /* ---------------------- Video-Player (HLS) ----------------------- */

    const videoModalEl = document.getElementById('videoModal');
    const modalVideo   = document.getElementById('modal-video');
    const bsVideoModal = new bootstrap.Modal(videoModalEl);

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

    videoModalEl.addEventListener('hidden.bs.modal', () => {
      const camId = videoModalEl.dataset.camId;
      modalVideo.pause();
      modalVideo.removeAttribute('src');
      modalVideo.load();
      if (camId) fetch(`/apps/video-player/stop/${camId}`, { method: 'POST' });
    });

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
  });
})();
