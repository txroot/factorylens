/* public/js/settings/device_settings.js */

document.addEventListener('DOMContentLoaded', () => {
  const addBtn      = document.getElementById('addDeviceBtn');
  const table       = $('#devicesTable').bootstrapTable();
  const modal       = new bootstrap.Modal('#deviceModal', { backdrop: 'static', keyboard: false });
  const confirmModal= new bootstrap.Modal('#confirmDeleteModal');
  const form        = document.getElementById('deviceForm');
  const confirmYes  = document.getElementById('confirmYesBtn');
  let   pendingDeleteId = null;

  new bootstrap.Tooltip(addBtn);

  const showToast = (msg, variant='success') => {
    const el = document.createElement('div');
    el.className = `toast align-items-center text-bg-${variant} border-0 position-fixed bottom-0 end-0 m-3`;
    el.innerHTML = `
      <div class="d-flex">
        <div class="toast-body">${msg}</div>
        <button class="btn-close btn-close-white ms-auto" data-bs-dismiss="toast"></button>
      </div>`;
    document.body.appendChild(el);
    new bootstrap.Toast(el, { delay: 2500 }).show();
  };

  const resetForm = () => {
    form.reset();
    form.id.value = '';
    form.querySelector('.modal-title').textContent = window.t('settings_device_new');
  };

  window.actionFmt = (_, row) => `
    <button class="btn btn-sm btn-light me-1 edit-btn" data-id="${row.id}">
      <i class="ti ti-pencil"></i>
    </button>
    <button class="btn btn-sm btn-light me-1 cfg-btn" data-id="${row.id}">
      <i class="ti ti-settings"></i>
    </button>
    <button class="btn btn-sm btn-danger delete-btn" data-id="${row.id}">
      <i class="ti ti-trash"></i>
    </button>`;

  addBtn.addEventListener('click', () => {
    resetForm();
    modal.show();
  });

  table.on('click', '.edit-btn', async function(){
    try {
      const res  = await fetch(`/settings/devices/${this.dataset.id}`);
      const data = await res.json();
      resetForm();
      Object.entries(data).forEach(([k,v]) => form[k] && (form[k].value = v ?? ''));
      form.querySelector('.modal-title').textContent = window.t('settings_device_edit');
      modal.show();
    } catch(e) { showToast(e.message,'danger'); }
  });

  table.on('click','.delete-btn', function(){
    pendingDeleteId = this.dataset.id;
    confirmModal.show();
  });

  confirmYes.addEventListener('click', () => {
    fetch(`/settings/devices/${pendingDeleteId}`,{method:'DELETE'})
      .then(r => { if(!r.ok) throw new Error(r.statusText); })
      .then(() => {
        table.bootstrapTable('refresh');
        showToast(window.t('settings_device_deleted'));
      })
      .catch(e => showToast(e.message,'danger'))
      .finally(() => {
        pendingDeleteId = null;
        confirmModal.hide();
      });
  });

  table.on('click','.cfg-btn', function(){
    location.href = `/settings/devices/${this.dataset.id}/config`;
  });

  form.addEventListener('submit', async e=> {
    e.preventDefault();
    const data = Object.fromEntries(new FormData(form));
    const id   = data.id; delete data.id;
    const method = id? 'PUT':'POST';
    const url    = id? `/settings/devices/${id}`:'/settings/devices';
    try {
      const res = await fetch(url,{method,headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});
      if(!res.ok) throw new Error(await res.text());
      modal.hide();
      table.bootstrapTable('refresh');
      showToast(window.t('settings_device_saved'));
    } catch(e){ showToast(e.message,'danger'); }
  });
});
