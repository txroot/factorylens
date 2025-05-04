// public/js/settings/device_settings.js

document.addEventListener("DOMContentLoaded", async () => {
  const addBtn       = document.getElementById("addDeviceBtn");
  const table        = $("#devicesTable").bootstrapTable();
  const modal        = new bootstrap.Modal("#deviceModal", { backdrop: "static", keyboard: false });
  const confirmModal = new bootstrap.Modal("#confirmDeleteModal");
  const form         = document.getElementById("deviceForm");
  const confirmYes   = document.getElementById("confirmYesBtn");

  let pendingDeleteId = null;
  let editor = null;  // JSONEditor instance

  new bootstrap.Tooltip(addBtn);

  // Load category options into <select>
  async function loadCategories(preselectId) {
    const res = await fetch("/settings/device-categories");
    const categories = await res.json();
    const sel = form.category_id;
    sel.innerHTML = categories.map(cat =>
      `<option value="${cat.id}">${cat.name}</option>`
    ).join("");
    if (preselectId) sel.value = preselectId;
  }

  // Load model options based on selected category
  async function loadModels(catId, preselectId) {
    const res = await fetch(`/settings/device-models?cat=${catId}`);
    const models = await res.json();
    const sel = form.device_model_id;
    sel.innerHTML = models.map(m =>
      `<option value="${m.id}">${m.name}</option>`
    ).join("");
    if (preselectId) sel.value = preselectId;
    loadSchema(sel.value);
  }

  // Load JSON schema for selected device model
  async function loadSchema(modelId) {
    const container = document.getElementById("dynamicConfigEditor");
    if (editor) {
      editor.destroy();
      container.innerHTML = "";
    }

    let schema = { type: "object", properties: {} };
    try {
      const res = await fetch(`/settings/devices/schema/${modelId}`);
      if (res.ok) {
        schema = await res.json();
      } else {
        console.warn("No schema found for model", modelId);
      }
    } catch (err) {
      console.error("Error fetching schema:", err);
    }

    editor = new JSONEditor(container, {
      schema,
      theme: "bootstrap5",
      iconlib: "bootstrap5",
      disable_collapse: true,
      disable_edit_json: true,
      no_additional_properties: true
    });
  }

  // Reset form fields
  function resetForm() {
    form.reset();
    form.id.value = "";
    form.querySelector(".modal-title").textContent = window.t("settings_device_new");
    if (editor) editor.setValue({});
  }

  // Show a toast notification
  function showToast(msg, variant = "success") {
    const el = document.createElement("div");
    el.className = `toast align-items-center text-bg-${variant} border-0 position-fixed bottom-0 end-0 m-3`;
    el.innerHTML = `
      <div class="d-flex">
        <div class="toast-body">${msg}</div>
        <button type="button" class="btn-close btn-close-white ms-auto" data-bs-dismiss="toast"></button>
      </div>`;
    document.body.appendChild(el);
    new bootstrap.Toast(el, { delay: 2500 }).show();
  }

  // Handle category change → reload model options
  form.category_id.addEventListener("change", () => {
    loadModels(form.category_id.value);
  });

  // Handle model change → reload schema
  form.device_model_id.addEventListener("change", () => {
    loadSchema(form.device_model_id.value);
  });

  // Add new device button
  addBtn.addEventListener("click", async () => {
    resetForm();
    await loadCategories();
    const firstCategoryId = form.category_id.options[0]?.value;
    if (firstCategoryId) await loadModels(firstCategoryId);
    modal.show();
  });

  // Edit existing device
  table.on("click", ".edit-btn", async function () {
    try {
      const res = await fetch(`/settings/devices/${this.dataset.id}`);
      if (!res.ok) throw new Error(res.statusText);
      const data = await res.json();

      resetForm();
      await loadCategories(data.category_id);
      await loadModels(data.category_id, data.device_model_id);

      Object.entries(data).forEach(([k, v]) => {
        const fld = form[k];
        if (fld && k !== "parameters") {
          if (fld.type === "checkbox") fld.checked = Boolean(v);
          else fld.value = v ?? "";
        }
      });

      if (editor) editor.setValue(data.parameters || {});
      form.querySelector(".modal-title").textContent = window.t("settings_device_edit");
      modal.show();
    } catch (err) {
      showToast(err.message, "danger");
    }
  });

  // Delete device
  table.on("click", ".delete-btn", function () {
    pendingDeleteId = this.dataset.id;
    confirmModal.show();
  });

  confirmYes.addEventListener("click", () => {
    fetch(`/settings/devices/${pendingDeleteId}`, { method: "DELETE" })
      .then(r => {
        if (!r.ok) throw new Error(r.statusText);
      })
      .then(() => {
        table.bootstrapTable("refresh");
        showToast(window.t("settings_device_deleted"));
      })
      .catch(e => showToast(e.message, "danger"))
      .finally(() => {
        pendingDeleteId = null;
        confirmModal.hide();
      });
  });

  // Config button placeholder
  table.on("click", ".cfg-btn", function () {
    location.href = `/settings/devices/${this.dataset.id}/config`;
  });

  // Submit form (create or update)
  form.addEventListener("submit", async e => {
    e.preventDefault();
    const formData = new FormData(form);
    const data = Object.fromEntries(formData.entries());
    const id = data.id;
    delete data.id;

    if (editor) {
      const errors = editor.validate();
      if (errors.length) {
        showToast(window.t("settings_device_parameters_invalid"), "danger");
        return;
      }
      data.parameters = editor.getValue();
    }

    const method = id ? "PUT" : "POST";
    const url = id ? `/settings/devices/${id}` : "/settings/devices";

    try {
      const res = await fetch(url, {
        method,
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data)
      });
      if (!res.ok) throw new Error(await res.text());
      modal.hide();
      table.bootstrapTable("refresh");
      showToast(window.t("settings_device_saved"));
    } catch (err) {
      showToast(err.message, "danger");
    }
  });

  // Initial load of categories and models
  await loadCategories();
  const firstCategoryId = form.category_id.options[0]?.value;
  if (firstCategoryId) await loadModels(firstCategoryId);
});
