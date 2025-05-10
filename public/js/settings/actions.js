// public/js/settings/actions.js
// Factory-Lens – Actions page (IF → THEN → EVALUATE)
// Supports schema-based validation, type-filtering, tooltips, create/edit/delete,
// plus custom poll interval & timeouts, hidden chain fields

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

let currentEditId = null;
let devCache = [];
let schemaCache = new Map();
let outType = null;

// Modal & form refs
const modal             = new bootstrap.Modal("#actionModal");
const modalTitle        = qs("#modalTitle");
const f                  = qs("#actionForm");
const ignoreInputChk     = qs("#ignoreInputChk");
const succRow            = qs("#succRow");
const errRow             = qs("#errRow");

// Custom poll & timeout rows & checkboxes
const triggerPollRow    = qs(".custom-poll");
const triggerPollChk    = qs("#triggerPollChk");
const resultTimeoutRow  = qs(".custom-timeout");
const resultTimeoutChk  = qs("#resultTimeoutChk");
const succTimeoutRow    = qs(".custom-timeout-succ");
const succTimeoutChk    = qs("#succTimeoutChk");
const errTimeoutRow     = qs(".custom-timeout-err");
const errTimeoutChk     = qs("#errTimeoutChk");

// Toggle custom-poll & custom-timeout inputs
[ triggerPollChk, resultTimeoutChk, succTimeoutChk, errTimeoutChk ].forEach(chk => {
  if (!chk) return;
  chk.addEventListener("change", () => {
    let prefix, valName, unitName;
    if (chk === triggerPollChk)      { prefix="trigger"; valName="poll_value";   unitName="poll_unit"; }
    else if (chk === resultTimeoutChk){ prefix="result";  valName="timeout_value";unitName="timeout_unit"; }
    else if (chk === succTimeoutChk)  { prefix="succ";    valName="timeout_value";unitName="timeout_unit"; }
    else                              { prefix="err";     valName="timeout_value";unitName="timeout_unit"; }
    const inpVal  = f[`${prefix}_${valName}`];
    const inpUnit = f[`${prefix}_${unitName}`];
    if (inpVal)  inpVal.disabled  = !chk.checked;
    if (inpUnit) inpUnit.disabled = !chk.checked;
  });
});

// Fetch device list
async function fetchDevs() {
  if (devCache.length) return devCache;
  const r = await fetch("/settings/devices/data");
  devCache = r.ok ? await r.json() : [];
  return devCache;
}

// Fetch & cache a device's action-schema
async function getSchema(id) {
  if (schemaCache.has(id)) return schemaCache.get(id);
  const r = await fetch(`/actions/schema/${id}`);
  const js = r.ok ? await r.json() : {};
  schemaCache.set(id, js);
  return js;
}

// Populate actions table
async function loadRows() {
  const tb = qs("#actionsTable tbody");
  const r  = await fetch("/actions/data");
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

// ─── Build device dropdowns ───────────────────────────────────────
async function buildTriggerDevices() {
  const sel = f.trigger_device;
  sel.innerHTML = `<option disabled selected value="">—</option>`;
  (await fetchDevs()).filter(d => d.enabled)
    .forEach(d => sel.insertAdjacentHTML("beforeend", `<option value="${d.id}">${d.name}</option>`));
  // reset topics
  f.trigger_event_topic.disabled = true;
  f.trigger_topic.disabled       = true;
}
async function buildResultDevices() {
  const sel = f.result_device;
  sel.innerHTML = `<option disabled selected value="">—</option>`;
  (await fetchDevs()).filter(d => d.enabled)
    .forEach(d => sel.insertAdjacentHTML("beforeend", `<option value="${d.id}">${d.name}</option>`));
  f.result_event_topic.disabled = true;
  f.result_topic.disabled       = true;
}
async function buildEvalDevices(prefix) {
  const sel = f[`${prefix}_device`];
  sel.innerHTML = `<option disabled selected value="">—</option>`;
  (await fetchDevs()).filter(d => d.enabled)
    .forEach(d => sel.insertAdjacentHTML("beforeend", `<option value="${d.id}">${d.name}</option>`));
  f[`${prefix}_event_topic`].disabled = true;
  f[`${prefix}_topic`].disabled       = true;
}

// ─── Load topics into event-topic select & reset hidden topic select ─
async function loadTopics(devId, prefix) {
  const eventSel  = f[`${prefix}_event_topic`];
  const hiddenSel = f[`${prefix}_topic`];
  const vCol      = qs(`#${prefix}ValCol`);
  const cCol      = qs(`#${prefix}CmpCol`);
  if (!eventSel || !vCol) return;

  // reset UI
  eventSel.innerHTML   = `<option disabled selected value="">—</option>`;
  eventSel.disabled    = true;
  if (hiddenSel) {
    hiddenSel.innerHTML = `<option disabled selected value="">—</option>`;
    hiddenSel.disabled  = true;
  }
  cCol?.classList.add("d-none");
  vCol.querySelector("input,select")?.setAttribute("disabled", "");

  if (prefix==="trigger") triggerPollRow?.classList.add("d-none");
  if (!devId) return;

  const schema = await getSchema(devId);
  const source = prefix==="trigger" ? schema.topics : schema.command_topics;
  if (!source) return;

  // populate event-topic dropdown
  Object.entries(source).forEach(([topic, meta]) => {
    eventSel.insertAdjacentHTML("beforeend", `
      <option value="${topic}" data-meta='${JSON.stringify(meta)}'>
        ${meta.label||topic}
      </option>`);
  });
  eventSel.disabled = false;
}

// ─── Swap in correct input & handle custom poll/timeout & hidden fields ─
function adaptInput(prefix) {
  const eventSel = f[`${prefix}_event_topic`];
  if (!eventSel) return;
  const opt     = eventSel.selectedOptions[0];
  const metaRaw = opt?.dataset.meta;
  if (!metaRaw) return;
  const m       = JSON.parse(metaRaw);
  const vCol    = qs(`#${prefix}ValCol`);
  const cCol    = qs(`#${prefix}CmpCol`);
  if (!vCol) return;

  // populate hidden topic select (poll_topic or result_topic)
  const hiddenSel = f[`${prefix}_topic`];
  if (hiddenSel) {
    const hiddenVal = m.poll_topic ?? m.result_topic ?? "";
    hiddenSel.innerHTML = `<option value="${hiddenVal}" selected>${hiddenVal}</option>`;
    hiddenSel.disabled = true;
  }

  // start fresh input
  cCol?.classList.add("d-none");
  vCol.innerHTML = `
    <label class="form-label">
      ${prefix==="trigger" ? "Value" : "Payload"} *
    </label>
    <input name="${prefix==="trigger" ? "trigger_value" : `${prefix}_command`}"
           class="form-control" required>`;
  const inp = vCol.querySelector("input");
  inp?.removeAttribute("disabled");

  // enum/bool → <select>
  if (m.type==="enum"||m.type==="bool") {
    const opts = m.type==="bool"?["true","false"]:m.values;
    vCol.innerHTML = `
      <label class="form-label">
        ${prefix==="trigger" ? "Value" : "Payload"} *
      </label>
      <select name="${prefix==="trigger" ? "trigger_value" : `${prefix}_command`}"
              class="form-select" required>
        <option disabled selected value="">—</option>
        ${opts.map(v=>`<option value="${v}">${m.display?.[v]||v}</option>`).join("")}
      </select>`;
    if (prefix==="trigger") { outType = m.type; buildResultDevices(); }
  }
  // number → comparator + constraints
  else if (m.type==="number") {
    if (cCol) {
      cCol.classList.remove("d-none");
      cCol.innerHTML = `
        <label class="form-label">Cmp.</label>
        <select name="${prefix}_cmp" class="form-select">
          ${(m.comparators||["<","<=","==","!="," >=",">"])
             .map(c=>`<option value="${c}">${c}</option>`).join("")}
        </select>`;
    }
    if (inp) {
      const [min,max] = m.range||[null,null];
      if (min!==null) inp.min = min;
      if (max!==null) inp.max = max;
      inp.type = "number";
      if (m.units) inp.placeholder = m.units;
    }
    if (prefix==="trigger") { outType = m.type; buildResultDevices(); }
  }

  // custom poll interval for trigger
  if (prefix==="trigger") {
    if (m.poll_interval>0) {
      triggerPollRow.classList.remove("d-none");
      triggerPollChk.checked = false;
      f.trigger_poll_value.value = m.poll_interval;
      f.trigger_poll_unit.value  = m.poll_interval_unit || "sec";
      f.trigger_poll_value.disabled = true;
      f.trigger_poll_unit.disabled  = true;
    } else {
      triggerPollRow.classList.add("d-none");
    }
  }

  // custom timeout for result/succ/err
  ["result","succ","err"].forEach(p => {
    if (prefix===p && m.timeout>0) {
      const row = p==="result" ? resultTimeoutRow
                : p==="succ"   ? succTimeoutRow
                               : errTimeoutRow;
      const chk = p==="result" ? resultTimeoutChk
                : p==="succ"   ? succTimeoutChk
                               : errTimeoutChk;
      const val = f[`${p}_timeout_value`];
      const unit= f[`${p}_timeout_unit`];
      row.classList.remove("d-none");
      chk.checked = false;
      val.value = m.timeout;
      unit.value = m.timeout_unit || "sec";
      val.disabled = true;
      unit.disabled = true;
    }
  });
}

// ─── EVALUATE UI ────────────────────────────────────────────────
const modeRadios = Array.from(f.querySelectorAll('input[name="eval_mode"]'));
function updateEvalUI() {
  const mode = f.eval_mode.value;
  succRow.classList.toggle("d-none", !["success","both"].includes(mode));
  errRow.classList.toggle("d-none", !["error","both"].includes(mode));
}
modeRadios.forEach(r => r.addEventListener("change", updateEvalUI));

// ─── Delete & Edit clicks ─────────────────────────────────────
qs("#actionsTable tbody").addEventListener("click", async e => {
  const del  = e.target.closest(".del-btn");
  const edit = e.target.closest(".edit-btn");
  if (del) {
    if (!confirm("Delete this action?")) return;
    const res = await fetch(`/actions/${del.dataset.id}`, { method: "DELETE" });
    if (res.ok) { await loadRows(); toast("Deleted"); }
    else        toast("Error deleting", "danger");
    return;
  }
  if (edit) {
    currentEditId = edit.dataset.id;
    const r = await fetch(`/actions/${currentEditId}`);
    if (!r.ok) { toast("Error loading action", "danger"); return; }
    const a = await r.json();

    // reset form
    f.reset();
    f.classList.remove("was-validated");
    modalTitle.textContent = "Edit Action";
    outType = null;
    ignoreInputChk.checked = false;

    // basic
    f.name.value        = a.name;
    f.description.value = a.description;
    f.enabled.checked   = a.enabled;

    // ── IF node
    const [ trg, cmd, ...branches ] = a.chain;
    await buildTriggerDevices();
    f.trigger_device.value = trg.device_id;
    await loadTopics(trg.device_id, "trigger");
    f.trigger_event_topic.value = trg.topic;
    adaptInput("trigger");
    f.trigger_value.value = trg.match.value;

    // ── THEN node
    ignoreInputChk.checked = !!cmd.ignore_input;
    await buildResultDevices();
    f.result_device.value = cmd.device_id;
    await loadTopics(cmd.device_id, "result");
    f.result_event_topic.value = cmd.topic;
    adaptInput("result");
    f.result_command.value = cmd.command;

    // ── EVALUATE
    const hasSuccess = branches.some(n => n.branch==="success");
    const hasError   = branches.some(n => n.branch==="error");
    if      (!hasSuccess && !hasError) qs("#evalIgnore").checked = true;
    else if (hasSuccess && !hasError) qs("#evalSuccess").checked = true;
    else if (!hasSuccess && hasError) qs("#evalError").checked   = true;
    else                             qs("#evalBoth").checked    = true;
    updateEvalUI();

    // Success branch
    if (hasSuccess) {
      const sb = branches.find(n => n.branch==="success");
      await buildEvalDevices("succ");
      f.succ_device.value = sb.device_id;
      await loadTopics(sb.device_id, "succ");
      f.succ_event_topic.value = sb.topic;
      adaptInput("succ");
      f.succ_command.value = sb.command;
      if (sb.timeout) {
        succTimeoutRow.classList.remove("d-none");
        succTimeoutChk.checked = false;
        f.succ_timeout_value.value = sb.timeout.value;
        f.succ_timeout_unit.value  = sb.timeout.unit;
        f.succ_timeout_value.disabled = true;
        f.succ_timeout_unit.disabled  = true;
      }
    }

    // Error branch
    if (hasError) {
      const eb = branches.find(n => n.branch==="error");
      await buildEvalDevices("err");
      f.err_device.value = eb.device_id;
      await loadTopics(eb.device_id, "err");
      f.err_event_topic.value = eb.topic;
      adaptInput("err");
      f.err_command.value = eb.command;
      if (eb.timeout) {
        errTimeoutRow.classList.remove("d-none");
        errTimeoutChk.checked = false;
        f.err_timeout_value.value = eb.timeout.value;
        f.err_timeout_unit.value  = eb.timeout.unit;
        f.err_timeout_value.disabled = true;
        f.err_timeout_unit.disabled  = true;
      }
    }

    modal.show();
  }
});

// ─── “New Action” button ────────────────────────────────────────
qs("#addActionBtn").addEventListener("click", async () => {
  currentEditId = null;
  f.reset(); f.classList.remove("was-validated");
  modalTitle.textContent = "New Action";
  outType = null;
  ignoreInputChk.checked = false;
  updateEvalUI();
  await buildTriggerDevices();
  await buildResultDevices();
  await buildEvalDevices("succ");
  await buildEvalDevices("err");
  modal.show();
});

// ─── Form change handlers ───────────────────────────────────────
f.addEventListener("change", e => {
  const n = e.target.name;
  if      (n==="trigger_device")        loadTopics(e.target.value, "trigger");
  else if (n==="trigger_event_topic")   adaptInput("trigger");
  else if (n==="result_device")         loadTopics(e.target.value, "result");
  else if (n==="result_event_topic")    adaptInput("result");
  else if (n==="succ_device")           loadTopics(e.target.value, "succ");
  else if (n==="succ_event_topic")      adaptInput("succ");
  else if (n==="err_device")            loadTopics(e.target.value, "err");
  else if (n==="err_event_topic")       adaptInput("err");
});
ignoreInputChk.addEventListener("change", buildResultDevices);

// ─── Save (create/update) ──────────────────────────────────────
qs("#saveActionBtn").addEventListener("click", async () => {
  f.classList.add("was-validated");
  if (!f.checkValidity()) return;

  // Build evaluation branches
  const evalMode = f.eval_mode.value;

  let successBranch = ["success", "both"].includes(evalMode) ? {
    device_id: +f.succ_device.value,
    topic:     f.succ_event_topic.value,
    command:   f.succ_command.value,
    result_topic: f.succ_topic.value,
    timeout: {
      value: +f.succ_timeout_value.value || 0,
      unit:  f.succ_timeout_unit.value || "sec"
    }
  } : null;

  let errorBranch = ["error", "both"].includes(evalMode) ? {
    device_id: +f.err_device.value,
    topic:     f.err_event_topic.value,
    command:   f.err_command.value,
    result_topic: f.err_topic.value,
    timeout: {
      value: +f.err_timeout_value.value || 0,
      unit:  f.err_timeout_unit.value || "sec"
    }
  } : null;

  const payload = {
    name:        f.name.value.trim(),
    description: f.description.value.trim(),
    enabled:     f.enabled.checked,
    trigger: {
      device_id:     +f.trigger_device.value,
      topic:         f.trigger_event_topic.value,
      cmp:           f.trigger_cmp?.value || "==",
      value:         f.trigger_value.value || "",
      poll_topic:    f.trigger_topic.value,
      poll_interval: {
        value: +f.trigger_poll_value.value || 0,
        unit:  f.trigger_poll_unit.value || "sec"
      }
    },
    result: {
      device_id:    +f.result_device.value,
      topic:        f.result_event_topic.value,
      command:      f.result_command.value,
      ignore_input: ignoreInputChk.checked,
      result_topic: f.result_topic.value,
      timeout: {
        value: +f.result_timeout_value.value || 0,
        unit:  f.result_timeout_unit.value || "sec"
      }
    },
    evaluate: {
      mode:    evalMode,
      success: successBranch,
      error:   errorBranch
    }
  };

  const url    = currentEditId ? `/actions/${currentEditId}` : "/actions/";
  const method = currentEditId ? "PUT"                        : "POST";

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

// ─── Initial load ───────────────────────────────────────────────
document.addEventListener("DOMContentLoaded", loadRows);
