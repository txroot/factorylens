// device_settings.js

(() => {
    const table = $('#devicesTable');
    const modal = new bootstrap.Modal('#deviceModal');
    const form  = document.getElementById('deviceForm');
  
    // open modal on FAB click
    document.getElementById('addDeviceBtn')
            .addEventListener('click', () => modal.show());
  
    // submit form via fetch JSON
    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      const data = Object.fromEntries(new FormData(form));
      try {
        const r = await fetch('/settings/devices', {
          method: 'POST',
          headers: {'Content-Type':'application/json'},
          body: JSON.stringify(data)
        });
        if (!r.ok) throw new Error(await r.text());
        modal.hide();
        table.bootstrapTable('refresh');   // reload rows
        form.reset();
  
        // show toast
        const toastEl = document.createElement('div');
        toastEl.className = 'toast align-items-center text-bg-success border-0 position-fixed bottom-0 end-0 m-3';
        toastEl.innerHTML = `
          <div class="d-flex">
            <div class="toast-body">${window.t('settings_device_saved')}</div>
            <button type="button" class="btn-close btn-close-white ms-auto" data-bs-dismiss="toast"></button>
          </div>`;
        document.body.appendChild(toastEl);
        new bootstrap.Toast(toastEl, { delay: 2000 }).show();
      } catch (err) {
        alert(err);
      }
    });
  })();
  