/* public/js/settings/actions.js
   Factory‑Lens – Actions page (IF → THEN → EVALUATE)
   Supports schema-based validation, type-filtering, tooltips, create/edit/delete
*/

const qs = s => document.querySelector(s);
const toast = (msg, variant = "success") => {
  const t = document.createElement("div");
  t.className = `toast align-items-center text-bg-${variant} border-0 position-fixed bottom-0 end-0 m-3`;
  t.innerHTML = `
    <div class="d-flex">
      <div class="toast-body">${msg}</div>
      <button type="button" class="btn-close btn-close-white ms-auto me-2" data-bs-dismiss="toast"></button>
    </div>`;
  document.body.appendChild(t);
  new bootstrap.Toast(t, { delay: 2500 }).show();
};

let currentEditId = null;  // track whether we're editing an existing action
let devCache = [];
let schemaCache = new Map();
let outType = null;

async function fetchDevs() {
  if (devCache.length) return devCache;
  const r = await fetch("/settings/devices/data");
  devCache = r.ok ? await r.json() : [];
  return devCache;
}

async function getSchema(id) {
  if (schemaCache.has(id)) return schemaCache.get(id);
  const r = await fetch(`/actions/schema/${id}`);
  const js = r.ok ? await r.json() : {};
  schemaCache.set(id, js);
  return js;
}

async function loadRows() {
  const tb = qs("#actionsTable tbody");
  const r = await fetch("/actions/data");
  const rows = r.ok ? await r.json() : [];
  tb.innerHTML = "";
  rows.forEach(o => {
    tb.insertAdjacentHTML("beforeend", `
      <tr>
        <td>${o.name}</td>
        <td>${o.description || "—"}</td>
        <td class="text-center">${o.enabled ? "✔︎" : "—"}</td>
        <td class="text-end pe-0">
          <button class="btn btn-sm btn-outline-primary edit-btn" data-id="${o.id}">
            <i class="ti ti-edit"></i>
          </button>
          <button class="btn btn-sm btn-outline-danger del-btn" data-id="${o.id}">
            <i class="ti ti-trash"></i>
          </button>
        </td>
      </tr>`);
  });
}

// Modal refs
const modal = new bootstrap.Modal("#actionModal");
const modalTitle = qs("#modalTitle");
const f = qs("#actionForm");
const ignoreInputChk = qs("#ignoreInputChk");
const succRow = qs("#succRow"), errRow = qs("#errRow");

// Handle delete & edit clicks
qs("#actionsTable tbody").addEventListener("click", async e => {
  const del = e.target.closest(".del-btn");
  const edit = e.target.closest(".edit-btn");

  if (del) {
    if (!confirm("Delete this action?")) return;
    const res = await fetch(`/actions/${del.dataset.id}`, { method: "DELETE" });
    if (res.ok) {
      await loadRows();
      toast("Deleted");
    } else {
      toast("Error deleting", "danger");
    }
    return;
  }

  if (edit) {
    currentEditId = edit.dataset.id;
    // fetch and populate
    const r = await fetch(`/actions/${currentEditId}`);
    if (!r.ok) {
      toast("Error loading Action", "danger");
      return;
    }
    const a = await r.json();

    // reset form
    f.reset();
    f.classList.remove("was-validated");
    modalTitle.textContent = "Edit Action";

    // basic fields
    f.name.value = a.name;
    f.description.value = a.description;
    f.enabled.checked = a.enabled;

    // rehydrate IF node (chain[0])
    const chain = a.chain;
    const trg = chain[0];
    await buildTriggerDevices();
    f.trigger_device.value = trg.device_id;
    await loadTopics(trg.device_id, "trigger");

    if (trg.cmp && f.trigger_cmp) {
      f.trigger_cmp.value = trg.cmp;
    }
    f.trigger_value.value = trg.match.value;
    f.trigger_topic.value = trg.topic;
    adaptInput("trigger");
    f.trigger_value.value = trg.match.value;

    // THEN node (chain[1])
    const res = chain[1];
    ignoreInputChk.checked = !!res.ignore_input;
    await buildResultDevices();
    f.result_device.value = res.device_id;
    await loadTopics(res.device_id, "result");
    f.result_topic.value = res.topic;
    adaptInput("result");
    f.result_command.value = res.command;

    // EVALUATE
    const hasSuccess = chain.some(n => n.branch === "success");
    const hasError   = chain.some(n => n.branch === "error");
    if (!hasSuccess && !hasError) {
      qs("#evalIgnore").checked = true;
    } else if (hasSuccess && !hasError) {
      qs("#evalSuccess").checked = true;
    } else if (!hasSuccess && hasError) {
      qs("#evalError").checked = true;
    } else {
      qs("#evalBoth").checked = true;
    }
    updateEvalUI();

    if (hasSuccess) {
      const sb = chain.find(n => n.branch === "success");
      await buildEvalDevices("succ");
      f.succ_device.value = sb.device_id;
      await loadTopics(sb.device_id, "succ");
      f.succ_topic.value = sb.topic;
      adaptInput("succ");
      f.succ_command.value = sb.command;
    }
    if (hasError) {
      const eb = chain.find(n => n.branch === "error");
      await buildEvalDevices("err");
      f.err_device.value = eb.device_id;
      await loadTopics(eb.device_id, "err");
      f.err_topic.value = eb.topic;
      adaptInput("err");
      f.err_command.value = eb.command;
    }

    modal.show();
    return;
  }
});

// Dropdown builders
async function buildTriggerDevices() {
  const sel = f.trigger_device;
  sel.innerHTML = `<option disabled selected value="">—</option>`;
  (await fetchDevs()).filter(d => d.enabled).forEach(d => {
    sel.insertAdjacentHTML("beforeend", `<option value="${d.id}">${d.name}</option>`);
  });
}

async function buildResultDevices() {
  const sel = f.result_device;
  sel.innerHTML = `<option disabled selected value="">—</option>`;
  let list = (await fetchDevs()).filter(d => d.enabled);
  if (!ignoreInputChk.checked && outType) {
    list = list.filter(d => {
      const schema = schemaCache.get(d.id) || {};
      return Object.values(schema.command_topics||{}).some(m => m.type === outType);
    });
  }
  list.forEach(d => {
    sel.insertAdjacentHTML("beforeend", `<option value="${d.id}">${d.name}</option>`);
  });
}

async function buildEvalDevices(prefix) {
  const sel = f[`${prefix}_device`];
  sel.innerHTML = `<option disabled selected value="">—</option>`;
  (await fetchDevs()).filter(d => d.enabled).forEach(d => {
    sel.insertAdjacentHTML("beforeend", `<option value="${d.id}">${d.name}</option>`);
  });
}

// Load topics for a given device into the `<select name="{prefix}_topic">`
async function loadTopics(devId, prefix) {
  const tSel = f[`${prefix}_topic`];
  const vCol = qs(`#${prefix}ValCol`);
  const cCol = qs(`#${prefix}CmpCol`);

  if (!tSel || !vCol) return;
  // reset UI
  tSel.innerHTML = `<option disabled selected value="">—</option>`;
  tSel.disabled  = true;
  cCol?.classList.add("d-none");
  vCol.querySelector("input,select")?.setAttribute("disabled", "");

  if (!devId) return;

  // fetch the schema (topics vs. command_topics)
  const schema = await getSchema(devId);
  const source = prefix === "trigger"
    ? schema.topics
    : schema.command_topics;
  if (!source) return;

  // populate options
  Object.entries(source).forEach(([topic, meta]) => {
    tSel.insertAdjacentHTML("beforeend", `
      <option value="${topic}"
              data-meta='${JSON.stringify(meta)}'>
        ${meta.label || topic}
      </option>`);
  });

  tSel.disabled = false;
}

// After you pick a topic, swap in the right input (text, select, number+cmp)
function adaptInput(prefix) {
  const topicSel = f[`${prefix}_topic`];
  if (!topicSel) return;

  const opt     = topicSel.selectedOptions[0];
  const metaRaw = opt?.dataset.meta;
  if (!metaRaw) return;

  const m   = JSON.parse(metaRaw);
  const vCol = qs(`#${prefix}ValCol`);
  const cCol = qs(`#${prefix}CmpCol`);
  if (!vCol) return;

  // start over with a simple <input>
  cCol?.classList.add("d-none");
  vCol.innerHTML = `
    <label class="form-label">
      ${prefix === "trigger" ? "Value" : "Command"} *
    </label>
    <input name="${prefix === "trigger"
                  ? "trigger_value"
                  : `${prefix}_command`}"
           class="form-control"
           required>`;
  const inp = vCol.querySelector("input");
  inp?.removeAttribute("disabled");

  // enums & bools → <select>
  if (m.type === "enum" || m.type === "bool") {
    const opts = m.type === "bool" ? ["true","false"] : m.values;
    vCol.innerHTML = `
      <label class="form-label">
        ${prefix === "trigger" ? "Value" : "Command"} *
      </label>
      <select name="${prefix === "trigger"
                     ? "trigger_value"
                     : `${prefix}_command`}"
              class="form-select"
              required>
        <option disabled selected value="">—</option>
        ${opts.map(v => `<option value="${v}">${m.display?.[v]||v}</option>`).join("")}
      </select>`;
    return;
  }

  // numbers → show comparator + constrain input
  if (m.type === "number") {
    if (cCol) {
      cCol.classList.remove("d-none");
      cCol.innerHTML = `
        <label class="form-label">Cmp.</label>
        <select name="${prefix}_cmp" class="form-select">
          ${(m.comparators || ["<","<=","==","!="," >=",">"])
             .map(c => `<option value="${c}">${c}</option>`).join("")}
        </select>`;
    }
    if (inp) {
      const [min, max] = m.range || [null, null];
      if (min !== null) inp.min = min;
      if (max !== null) inp.max = max;
      inp.type = "number";
      if (m.units) inp.placeholder = m.units;
    }
  }

  // special case: remember the type so THEN can filter by it
  if (prefix === "trigger") {
    outType = m.type;
    buildResultDevices();
  }
}

// EVAL UI
const modeRadios = Array.from(f.querySelectorAll('input[name="eval_mode"]'));
function updateEvalUI() {
  const mode = f.eval_mode.value;
  succRow.classList.toggle("d-none", !["success","both"].includes(mode));
  errRow.classList.toggle("d-none", !["error","both"].includes(mode));
}
modeRadios.forEach(r => r.addEventListener("change", updateEvalUI));

// New Action button
qs("#addActionBtn").addEventListener("click", async () => {
  currentEditId = null;
  f.reset(); f.classList.remove("was-validated");
  modalTitle.textContent = "New Action";
  outType = null;
  ignoreInputChk.checked = false;
  qs("#evalIgnore").checked = true;
  updateEvalUI();
  await buildTriggerDevices();
  await buildResultDevices();
  await buildEvalDevices("succ");
  await buildEvalDevices("err");
  modal.show();
});

// Form change events
f.addEventListener("change", e => {
  const n = e.target.name;
  if (n === "trigger_device") loadTopics(e.target.value, "trigger");
  if (n === "trigger_topic") adaptInput("trigger");
  if (n === "result_device") loadTopics(e.target.value, "result");
  if (n === "result_topic") adaptInput("result");
  if (n === "succ_device") loadTopics(e.target.value, "succ");
  if (n === "succ_topic") adaptInput("succ");
  if (n === "err_device") loadTopics(e.target.value, "err");
  if (n === "err_topic") adaptInput("err");
});
ignoreInputChk.addEventListener("change", buildResultDevices);

// Save (create or update)
qs("#saveActionBtn").addEventListener("click", async () => {
  f.classList.add("was-validated");
  if (!f.checkValidity()) return;

  // build payload (as existing logic)
  const evalMode = f.eval_mode.value;
  const successBranch = ["success","both"].includes(evalMode) ? {
    device_id: +f.succ_device.value,
    topic:      f.succ_topic.value,
    command:    f.succ_command.value
  } : null;
  const errorBranch = ["error","both"].includes(evalMode) ? {
    device_id: +f.err_device.value,
    topic:      f.err_topic.value,
    command:    f.err_command.value
  } : null;

  const payload = {
    name: f.name.value.trim(),
    description: f.description.value.trim(),
    enabled: f.enabled.checked,
    trigger: {
      device_id: +f.trigger_device.value,
      topic:      f.trigger_topic.value,
      cmp:        f.trigger_cmp?.value || "==",
      value:      f.trigger_value?.value || ""
    },
    result: {
      device_id:    +f.result_device.value,
      topic:        f.result_topic.value,
      command:      f.result_command.value,
      ignore_input: ignoreInputChk.checked
    },
    evaluate: {
      mode:    evalMode,
      success: successBranch,
      error:   errorBranch
    }
  };

  // choose method & URL
  const url    = currentEditId ? `/actions/${currentEditId}` : "/actions/";
  const method = currentEditId ? "PUT"            : "POST";

  const res = await fetch(url, {
    method,
    headers: { "Content-Type": "application/json" },
    body:    JSON.stringify(payload)
  });

  if (res.ok) {
    modal.hide();
    await loadRows();
    currentEditId = null;
    toast("Saved");
  } else {
    toast((await res.json())?.message || "Error", "danger");
  }
});

// Initial load
document.addEventListener("DOMContentLoaded", loadRows);
