// public/js/settings/device_settings.js

// ── Formatter for the “Actions” column ────────────────────────────────
window.actionFmt = function(value, row, index) {
  return `
    <button class="btn btn-sm btn-primary edit-btn me-1" data-id="${value}" title="Edit">
      <i class="ti ti-edit"></i>
    </button>
    <button class="btn btn-sm btn-danger delete-btn" data-id="${value}" title="Delete">
      <i class="ti ti-trash"></i>
    </button>
  `;
};

document.addEventListener("DOMContentLoaded", async () => {
  const addBtn         = document.getElementById("addDeviceBtn");
  const table          = $("#devicesTable").bootstrapTable();
  const modal          = new bootstrap.Modal("#deviceModal", { backdrop: "static", keyboard: false });
  const confirmModal   = new bootstrap.Modal("#confirmDeleteModal");
  const form           = document.getElementById("deviceForm");
  const configContainer= document.getElementById("configForm");
  const confirmYes     = document.getElementById("confirmYesBtn");

  let pendingDeleteId = null;

  new bootstrap.Tooltip(addBtn);

  // ── Render a Bootstrap form from JSON-Schema ─────────────────────────
  function renderConfigForm(schema, data = {}) {
    configContainer.innerHTML = "";
    const required = schema.required || [];
    const props    = schema.properties || {};

    Object.entries(props).forEach(([key, prop]) => {
      const isBoolean = prop.type === "boolean";
      const isReq     = required.includes(key);

      // wrapper
      const col = document.createElement("div");
      col.className = isBoolean
        ? "form-check form-switch mb-3 col-md-6"
        : "form-floating mb-3 col-md-6";

      // build input
      let input;
      if (prop.enum) {
        input = document.createElement("select");
        input.className = "form-select";
        prop.enum.forEach(opt => {
          const o = document.createElement("option");
          o.value = opt;
          o.text  = opt;
          input.add(o);
        });
        input.value = data[key] ?? prop.default ?? "";
      } else if (prop.type === "integer") {
        input = document.createElement("input");
        input.type = "number";
        if (prop.minimum != null) input.min = prop.minimum;
        if (prop.maximum != null) input.max = prop.maximum;
        input.className = "form-control";
        input.value     = data[key] ?? prop.default ?? "";
      } else if (isBoolean) {
        input = document.createElement("input");
        input.type    = "checkbox";
        input.className = "form-check-input";
        input.checked = data[key] ?? prop.default ?? false;
      } else {
        input = document.createElement("input");
        input.type    = prop.format === "password" ? "password" : "text";
        input.className = "form-control";
        input.value     = data[key] ?? prop.default ?? "";
      }

      input.id    = `cfg_${key}`;
      input.name  = key;
      if (isReq && !isBoolean) input.required = true;

      // label
      const label = document.createElement("label");
      label.htmlFor   = input.id;
      label.className = isBoolean ? "form-check-label" : "form-label";
      label.innerText = prop.title || key;

      // assemble
      if (isBoolean) {
        col.appendChild(input);
        col.appendChild(label);
      } else {
        col.appendChild(input);
        col.appendChild(label);
      }

      // help text
      if (prop.description) {
        const help = document.createElement("div");
        help.className = "form-text";
        help.innerText = prop.description;
        col.appendChild(help);
      }

      // instant validation
      input.addEventListener("invalid", () => input.classList.add("is-invalid"));
      input.addEventListener("input", () => {
        if (input.checkValidity()) input.classList.remove("is-invalid");
      });

      configContainer.appendChild(col);
    });
  }

  // ── Load category <select> ───────────────────────────────────────────
  async function loadCategories(preselectId) {
    const res        = await fetch("/settings/device-categories");
    const categories = await res.json();
    const sel        = form.category_id;
    sel.innerHTML    = categories
      .map(c => `<option value="${c.id}">${c.name}</option>`)
      .join("");
    if (preselectId) sel.value = preselectId;
  }

  // ── Load model <select> and its schema ─────────────────────────────
  async function loadModels(catId, preselectId) {
    const res   = await fetch(`/settings/device-models?cat=${catId}`);
    const models= await res.json();
    const sel   = form.device_model_id;
    sel.innerHTML = models
      .map(m => `<option value="${m.id}">${m.name}</option>`)
      .join("");
    if (preselectId) sel.value = preselectId;

    // now fetch & render the config form
    await loadSchema(sel.value);
  }

  // ── Fetch schema and render form ────────────────────────────────────
  async function loadSchema(modelId) {
    let schema = { properties: {}, required: [] };
    try {
      const res = await fetch(`/settings/devices/schema/${modelId}`);
      if (res.ok) schema = await res.json();
    } catch (err) {
      console.warn("Schema load failed:", err);
    }
    // if we’re editing, use previously stored params
    const existing = form.dataset.params
      ? JSON.parse(form.dataset.params)
      : {};
    renderConfigForm(schema, existing);
  }

  // ── Reset the modal form ─────────────────────────────────────────────
  function resetForm() {
    form.reset();
    delete form.dataset.params;
    form.id.value = "";
    form.querySelector(".modal-title").textContent = window.t("settings_device_new");
    configContainer.innerHTML = "";
  }

  // ── Toast helper ────────────────────────────────────────────────────
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

  // ── Cascading selects ───────────────────────────────────────────────
  form.category_id.addEventListener("change", async () => {
    await loadModels(form.category_id.value);
  });
  form.device_model_id.addEventListener("change", async () => {
    await loadSchema(form.device_model_id.value);
  });

  // ── “Add Device” button ─────────────────────────────────────────────
  addBtn.addEventListener("click", async () => {
    resetForm();
    await loadCategories();
    const first = form.category_id.options[0]?.value;
    if (first) await loadModels(first);
    modal.show();
  });

  // ── Edit existing device ────────────────────────────────────────────
  table.on("click", ".edit-btn", async function() {
    try {
      const res  = await fetch(`/settings/devices/${this.dataset.id}`);
      if (!res.ok) throw new Error(res.statusText);
      const data = await res.json();

      resetForm();
      form.dataset.params = JSON.stringify(data.parameters || {});
      await loadCategories(data.category_id);
      await loadModels(data.category_id, data.device_model_id);

      Object.entries(data).forEach(([k,v]) => {
        const fld = form[k];
        if (!fld || k==="parameters") return;
        if (fld.type==="checkbox") fld.checked = Boolean(v);
        else fld.value = v ?? "";
      });

      form.querySelector(".modal-title").textContent = window.t("settings_device_edit");
      modal.show();
    } catch (err) {
      showToast(err.message, "danger");
    }
  });

  // ── Delete device ───────────────────────────────────────────────────
  table.on("click", ".delete-btn", () => {
    pendingDeleteId = this.dataset.id;
    confirmModal.show();
  });
  confirmYes.addEventListener("click", () => {
    fetch(`/settings/devices/${pendingDeleteId}`, { method: "DELETE" })
      .then(r => { if (!r.ok) throw new Error(r.statusText); })
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

  // ── Form submit ─────────────────────────────────────────────────────
  form.addEventListener("submit", async e => {
    e.preventDefault();

    // pull out everything except checkboxes…
    const formData = new FormData(form);
    const data     = Object.fromEntries(formData.entries());
    delete data.id;

    // **override** the enabled flag with the real boolean
    data.enabled = form.querySelector('input[name="enabled"]').checked;

    // collect the configForm values
    const params = {};
    configContainer.querySelectorAll("[name]").forEach(inp => {
      if (inp.type === "checkbox") params[inp.name] = inp.checked;
      else if (inp.type === "number")   params[inp.name] = +inp.value;
      else                                params[inp.name] = inp.value;
    });
    data.parameters = params;

    const method = form.id.value ? "PUT" : "POST";
    const url    = form.id.value
      ? `/settings/devices/${form.id.value}`
      : "/settings/devices";

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

  // ── Initial bootstrap ───────────────────────────────────────────────
  await loadCategories();
  const firstCat = form.category_id.options[0]?.value;
  if (firstCat) await loadModels(firstCat);
});
