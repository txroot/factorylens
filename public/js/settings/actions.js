/*  public/js/settings/actions.js
 *  ═══════════════════════════════════════════════════════════════════
 *  Modern Bootstrap‑5 UI helpers for the “Actions” page
 *  – auto‑suggests topics / payloads from each Device‑Model topic‑schema
 *  – groups devices by category in selects
 *  – tiny toast & form‑validation helpers
 *  ═══════════════════════════════════════════════════════════════════ */

/* ------------------------------------------------------------------ */
/*  Toast helper                                                      */
/* ------------------------------------------------------------------ */
const toast = (msg, variant = "success") => {
  const t = document.createElement("div");
  t.className =
    `toast align-items-center text-bg-${variant} border-0 position-fixed bottom-0 end-0 m-3`;
  t.role = "alert";
  t.innerHTML = `
      <div class="d-flex">
        <div class="toast-body">${msg}</div>
        <button type="button" class="btn-close btn-close-white ms-auto me-2" data-bs-dismiss="toast"></button>
      </div>`;
  document.body.appendChild(t);
  new bootstrap.Toast(t, { delay: 2500 }).show();
};

/* ------------------------------------------------------------------ */
/*  Action table                                                      */
/* ------------------------------------------------------------------ */
async function loadActionRows() {
  const tbody = document.querySelector("#actionsTable tbody");
  const res   = await fetch("/actions/data");
  const rows  = res.ok ? await res.json() : [];
  tbody.innerHTML = "";
  rows.forEach(r => {
    tbody.insertAdjacentHTML("beforeend", `
      <tr>
        <td>${r.name}</td>
        <td>${r.description || "—"}</td>
        <td class="text-center">${r.enabled ? "✔︎" : "—"}</td>
        <td class="text-end pe-0">
          <button class="btn btn-sm btn-outline-primary edit-btn" data-id="${r.id}">
            <i class="ti ti-edit"></i>
          </button>
          <button class="btn btn-sm btn-outline-danger del-btn" data-id="${r.id}">
            <i class="ti ti-trash"></i>
          </button>
        </td>
      </tr>`);
  });
}

document
  .querySelector("#actionsTable tbody")
  .addEventListener("click", async e => {
    const btn = e.target.closest(".del-btn");
    if (!btn) return;
    if (!confirm("Delete this action?")) return;
    const res = await fetch(`/actions/${btn.dataset.id}`, { method: "DELETE" });
    res.ok ? (await loadActionRows(), toast("Deleted")) : toast("Error", "danger");
  });

/* ------------------------------------------------------------------ */
/*  Modal helpers                                                     */
/* ------------------------------------------------------------------ */
const modal     = new bootstrap.Modal("#actionModal");
const form      = document.getElementById("actionForm");
const titleSpan = document.getElementById("modalTitle");

let deviceCache = [];                // [{id,name,category,enabled,…},…]
let schemaCache = new Map();         // Map<deviceId, schemaJSON>

/* --- Device / schema fetchers ------------------------------------- */
async function fetchDevices() {
  if (deviceCache.length) return deviceCache;
  const res = await fetch("/settings/devices/data");
  deviceCache = res.ok ? await res.json() : [];
  return deviceCache;
}

async function getSchema(devId) {
  if (schemaCache.has(devId)) return schemaCache.get(devId);
  const res = await fetch(`/actions/schema/${devId}`);
  const js  = res.ok ? await res.json() : {};
  schemaCache.set(devId, js);
  return js;
}

/* --- Build <select> with opt‑groups by category -------------------- */
async function fillDeviceSelects() {
  const devs = await fetchDevices();

  const grouped = devs.reduce((acc, d) => {
    if (!d.enabled) return acc;
    (acc[d.category] ||= []).push(d);
    return acc;
  }, {});                                                // {camera:[…], iot:[…] …}

  ["trigger_device", "result_device"].forEach(name => {
    const sel = form[name];
    sel.innerHTML = `<option value="" disabled selected>—</option>`;
    Object.entries(grouped).forEach(([cat, list]) => {
      const og = document.createElement("optgroup");
      og.label = cat.charAt(0).toUpperCase() + cat.slice(1);
      list.forEach(d =>
        og.insertAdjacentHTML("beforeend",
          `<option value="${d.id}">${d.name}</option>`));
      sel.appendChild(og);
    });
  });
}

/* --- Topic / command drop‑downs ----------------------------------- */
async function loadTopics(devId, prefix) {
  const topicSel = form[`${prefix}_topic`];
  const valueCol = document.getElementById(`${prefix}ValCol`);
  const cmpCol   = document.getElementById(`${prefix}CmpCol`);

  topicSel.innerHTML = '<option value="" disabled selected>—</option>';
  topicSel.disabled  = true;
  cmpCol?.classList.add("d-none");
  valueCol.querySelector("input,select")?.setAttribute("disabled","");

  if (!devId) return;

  const schema = await getSchema(devId);
  const source = prefix === "trigger" ? schema.topics : schema.command_topics;
  if (!source) return;

  Object.entries(source).forEach(([t, meta]) => {
    topicSel.insertAdjacentHTML(
      "beforeend",
      `<option value="${t}" data-meta='${JSON.stringify(meta)}'>${meta.label || t}</option>`
    );
  });
  topicSel.disabled = false;
}

/* --- Adapt input field when topic selected ------------------------ */
function adaptValueInput(prefix) {
  const topicSel = form[`${prefix}_topic`];
  const metaRaw  = topicSel.selectedOptions[0]?.dataset.meta;
  if (!metaRaw) return;

  const m        = JSON.parse(metaRaw);
  const cmpCol   = document.getElementById(`${prefix}CmpCol`);
  const valCol   = document.getElementById(`${prefix}ValCol`);

  /* reset */
  cmpCol.classList.add("d-none");
  valCol.innerHTML =
    `<label class="form-label">${prefix === "trigger" ? "Value" : "Command"} *</label>
     <input name="${prefix === "trigger" ? "trigger_value" : "result_command"}"
            class="form-control" required>`;
  const inp = valCol.querySelector("input");
  inp.removeAttribute("disabled");

  /* enums / booleans → dropdown ------------------------------ */
  if (m.type === "enum" || m.type === "bool") {
    const opts = m.type === "bool" ? ["true", "false"] : m.values;
    valCol.innerHTML =
      `<label class="form-label">${prefix === "trigger" ? "Value" : "Command"} *</label>
       <select name="${prefix === "trigger" ? "trigger_value" : "result_command"}"
               class="form-select" required>
         <option value="" disabled selected>—</option>
         ${opts.map(v =>
            `<option value="${v}">${m.display?.[v] || v}</option>`).join("")}
       </select>`;
  }
  /* numbers → comparator + numeric input --------------------- */
  else if (m.type === "number") {
    cmpCol.classList.remove("d-none");
    cmpCol.innerHTML =
      `<label class="form-label">Cmp.</label>
       <select name="${prefix}_cmp" class="form-select">
         ${(m.comparators || ["<","<=","==","!="," >=",">"])
            .map(c => `<option value="${c.trim()}">${c.trim()}</option>`).join("")}
       </select>`;
    const [min,max] = m.range || [null, null];
    if (min !== null) inp.min = min;
    if (max !== null) inp.max = max;
    inp.type  = "number";
    if (m.units) inp.placeholder = m.units;
  }
}

/* ------------------------------------------------------------------ */
/*  Modal open + dynamic listeners                                    */
/* ------------------------------------------------------------------ */
document.getElementById("addActionBtn")?.addEventListener("click", async () => {
  form.reset();
  form.classList.remove("was-validated");
  titleSpan.textContent = "New Action";
  await fillDeviceSelects();
  modal.show();
});

form.addEventListener("change", e => {
  if (e.target.name === "trigger_device") loadTopics(e.target.value, "trigger");
  if (e.target.name === "result_device")  loadTopics(e.target.value, "result");
  if (e.target.name === "trigger_topic")  adaptValueInput("trigger");
  if (e.target.name === "result_topic")   adaptValueInput("result");
});

/* ------------------------------------------------------------------ */
/*  Save                                                               */
/* ------------------------------------------------------------------ */
document.getElementById("saveActionBtn").addEventListener("click", async () => {
  form.classList.add("was-validated");
  if (!form.checkValidity()) return;

  const data = {
    name:        form.name.value.trim(),
    description: form.description.value.trim(),
    enabled:     form.enabled.checked,
    trigger: {
      device_id: +form.trigger_device.value,
      topic:     form.trigger_topic.value,
      cmp:       form.trigger_cmp?.value || "==",
      value:     form.trigger_value ? form.trigger_value.value : ""
    },
    result: {
      device_id: +form.result_device.value,
      topic:     form.result_topic.value,
      command:   form.result_command ? form.result_command.value : ""
    }
  };

  const res = await fetch("/actions/", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data)
  });

  if (res.ok) {
    modal.hide();
    await loadActionRows();
    toast("Saved");
  } else {
    const msg = (await res.json())?.message || "Error";
    toast(msg, "danger");
  }
});

/* ------------------------------------------------------------------ */
/*  Boot                                                               */
/* ------------------------------------------------------------------ */
document.addEventListener("DOMContentLoaded", loadActionRows);
