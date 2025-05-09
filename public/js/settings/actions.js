// public/js/settings/actions.js
// Factory-Lens – Actions page (IF → THEN → EVALUATE)
// Enhanced with Event/Result topic fields, custom poll & timeouts, and Tabler icons.

const qs   = s => document.querySelector(s);
const qsa  = s => Array.from(document.querySelectorAll(s));
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
let devCache      = [];
let schemaCache   = new Map();
let outType       = null;

// ─── Fetch once & cache ────────────────────────────────────────
async function fetchDevs() {
  if (devCache.length) return devCache;
  const res = await fetch("/settings/devices/data");
  devCache = res.ok ? await res.json() : [];
  return devCache;
}

// ─── Fetch per-device schema (topics & command_topics) ────────
async function getSchema(deviceId) {
  if (schemaCache.has(deviceId)) return schemaCache.get(deviceId);
  const res = await fetch(`/actions/schema/${deviceId}`);
  const js  = res.ok ? await res.json() : {};
  schemaCache.set(deviceId, js);
  return js;
}

// ─── Load table of existing actions ───────────────────────────
async function loadRows() {
  const tbody = qs("#actionsTable tbody");
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

// ─── Modal & form refs ────────────────────────────────────────
const modal            = new bootstrap.Modal("#actionModal");
const modalTitle       = qs("#modalTitle");
const f                = qs("#actionForm");
const ignoreInputChk   = qs("#ignoreInputChk");
const succRow          = qs("#succRow"), errRow = qs("#errRow");

// custom-poll & timeout rows + checkboxes
const triggerPollRow   = qs(".custom-poll"),
      triggerPollChk   = qs("#triggerPollChk"),
      resultTimeoutRow = qs(".custom-timeout"),
      resultTimeoutChk = qs("#resultTimeoutChk"),
      succTimeoutRow   = qs(".custom-timeout-succ"),
      succTimeoutChk   = qs("#succTimeoutChk"),
      errTimeoutRow    = qs(".custom-timeout-err"),
      errTimeoutChk    = qs("#errTimeoutChk");

// toggle custom-poll/timeout inputs on checkbox change
[ triggerPollChk, resultTimeoutChk, succTimeoutChk, errTimeoutChk ]
 .forEach(chk => {
   if (!chk) return;
   chk.addEventListener("change", () => {
     let prefix, valName, unitName;
     if      (chk===triggerPollChk)   { prefix="trigger"; valName="poll_value";    unitName="poll_unit"; }
     else if (chk===resultTimeoutChk) { prefix="result";  valName="timeout_value"; unitName="timeout_unit"; }
     else if (chk===succTimeoutChk)   { prefix="succ";    valName="timeout_value"; unitName="timeout_unit"; }
     else                              { prefix="err";     valName="timeout_value"; unitName="timeout_unit"; }
     const iv = f[`${prefix}_${valName}`],
           iu = f[`${prefix}_${unitName}`];
     if (iv) iv.disabled  = !chk.checked;
     if (iu) iu.disabled = !chk.checked;
   });
 });

// ─── Delete & Edit button handling ────────────────────────────
qs("#actionsTable tbody").addEventListener("click", async e => {
  const del  = e.target.closest(".del-btn");
  const edit = e.target.closest(".edit-btn");
  if (del) {
    if (!confirm("Delete this action?")) return;
    const r = await fetch(`/actions/${del.dataset.id}`, { method: "DELETE" });
    if (r.ok) { await loadRows(); toast("Deleted"); }
    else      toast("Delete failed", "danger");
    return;
  }
  if (edit) {
    currentEditId = edit.dataset.id;
    const r = await fetch(`/actions/${currentEditId}`);
    if (!r.ok) { toast("Load failed", "danger"); return; }
    const a = await r.json();

    // reset form
    f.reset(); f.classList.remove("was-validated");
    modalTitle.textContent = "Edit Action";
    outType = null;
    ignoreInputChk.checked = false;

    // basic fields
    f.name.value        = a.name;
    f.description.value = a.description;
    f.enabled.checked   = a.enabled;

    // ── IF node ─────────────────────────────────────────────
    const [trg, cmd, ...branches] = a.chain;
    await buildTriggerDevices();
    f.trigger_device.value = trg.device_id;
    await loadTopics(trg.device_id, "trigger");
    if (trg.cmp && f.trigger_cmp) f.trigger_cmp.value = trg.cmp;
    f.trigger_topic.value = trg.topic;
    adaptInput("trigger");
    f.trigger_value.value = trg.match.value;

    // ── THEN node ──────────────────────────────────────────
    ignoreInputChk.checked = !!cmd.ignore_input;
    await buildResultDevices();
    f.result_device.value  = cmd.device_id;
    await loadTopics(cmd.device_id, "result");
    f.result_topic.value   = cmd.topic;
    adaptInput("result");
    f.result_command.value = cmd.command;

    // ── EVALUATE ───────────────────────────────────────────
    const hasS = branches.some(n => n.branch==="success");
    const hasE = branches.some(n => n.branch==="error");
    qs("#evalIgnore").checked = !(hasS||hasE);
    qs("#evalSuccess").checked= hasS&&!hasE;
    qs("#evalError").checked  = !hasS&&hasE;
    qs("#evalBoth").checked   =  hasS&&hasE;
    updateEvalUI();

    // success branch
    if (hasS) {
      const sb = branches.find(n=>n.branch==="success");
      await buildEvalDevices("succ");
      f.succ_device.value = sb.device_id;
      await loadTopics(sb.device_id, "succ");
      f.succ_topic.value   = sb.topic;
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

    // error branch
    if (hasE) {
      const eb = branches.find(n=>n.branch==="error");
      await buildEvalDevices("err");
      f.err_device.value = eb.device_id;
      await loadTopics(eb.device_id, "err");
      f.err_topic.value   = eb.topic;
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

// ─── Build the trigger-device select ─────────────────────────
async function buildTriggerDevices() {
  const sel = f.trigger_device;
  sel.innerHTML = `<option disabled selected value="">—</option>`;
  (await fetchDevs()).filter(d=>d.enabled).forEach(d=>{
    sel.insertAdjacentHTML("beforeend",
      `<option value="${d.id}">${d.name}</option>`);
  });
  f.result_device.disabled = true;  // lock THEN until we pick an event
}

// ─── Build the THEN-device select, filtered by outType ─────────
async function buildResultDevices() {
  const sel = f.result_device;
  sel.innerHTML = `<option disabled selected value="">—</option>`;
  if (!outType) {
    sel.disabled = true;
    return;
  }
  const devices = (await fetchDevs()).filter(d=>d.enabled);
  const list = ignoreInputChk.checked
    ? devices
    : await Promise.all(devices.map(async d=>{
        const schema = await getSchema(d.id);
        const ct = schema.command_topics||{};
        return Object.values(ct).some(m=>m.type===outType) ? d : null;
      })).then(arr=>arr.filter(x=>x));
  list.forEach(d=>{
    sel.insertAdjacentHTML("beforeend",
      `<option value="${d.id}">${d.name}</option>`);
  });
  sel.disabled = false;
}

// ─── Build success/error device selects (all devices) ─────────
async function buildEvalDevices(prefix) {
  const sel = f[`${prefix}_device`];
  sel.innerHTML = `<option disabled selected value="">—</option>`;
  (await fetchDevs()).filter(d=>d.enabled).forEach(d=>{
    sel.insertAdjacentHTML("beforeend",
      `<option value="${d.id}">${d.name}</option>`);
  });
}

// ─── Load topics into select[name="{prefix}_topic"] ────────────
async function loadTopics(devId, prefix) {
  const tSel = f[`${prefix}_topic`];
  const vCol = qs(`#${prefix}ValCol`);
  const cCol = qs(`#${prefix}CmpCol`);
  if (!tSel||!vCol) return;

  // reset
  tSel.innerHTML = `<option disabled selected value="">—</option>`;
  tSel.disabled  = true;
  cCol?.classList.add("d-none");
  vCol.querySelector("input,select")?.setAttribute("disabled","");

  if (!devId) {
    if (prefix==="trigger") triggerPollRow.classList.add("d-none");
    return;
  }

  const schema = await getSchema(devId);
  const source = (prefix==="trigger" ? schema.topics : (
                   prefix==="result"  ? schema.command_topics :
                   source={} ));
  if (!source) {
    if (prefix==="trigger") triggerPollRow.classList.add("d-none");
    return;
  }

  Object.entries(source).forEach(([topic,meta])=>{
    tSel.insertAdjacentHTML("beforeend", `
      <option value="${topic}" data-meta='${JSON.stringify(meta)}'>
        ${meta.label||topic}
      </option>`);
  });
  tSel.disabled = false;
}

// ─── Adapt the input field + custom rows ────────────────────────
function adaptInput(prefix) {
  const topicSel = f[`${prefix}_topic`];
  if (!topicSel) return;
  const opt   = topicSel.selectedOptions[0];
  const raw   = opt?.dataset.meta;
  if (!raw) return;
  const m     = JSON.parse(raw);
  const vCol  = qs(`#${prefix}ValCol`);
  const cCol  = qs(`#${prefix}CmpCol`);
  if (!vCol) return;

  // start with <input>
  cCol?.classList.add("d-none");
  vCol.innerHTML = `
    <label class="form-label">${prefix==="trigger"?"Value":"Command"} *</label>
    <input name="${prefix==="trigger"?"trigger_value":`${prefix}_command`}"
           class="form-control" required>`;
  const inp = vCol.querySelector("input");
  inp?.removeAttribute("disabled");

  // enum/bool → <select>
  if (m.type==="enum"||m.type==="bool") {
    const opts = m.type==="bool"?["true","false"]:m.values;
    vCol.innerHTML = `
      <label class="form-label">${prefix==="trigger"?"Value":"Command"} *</label>
      <select name="${prefix==="trigger"?"trigger_value":`${prefix}_command`}"
              class="form-select" required>
        <option disabled selected value="">—</option>
        ${opts.map(v=>`<option value="${v}">${m.display?.[v]||v}</option>`).join("")}
      </select>`;
    if (prefix==="trigger") {
      outType = m.type;
      buildResultDevices();
    }
    return;
  }

  // number → comparator + range
  if (m.type==="number") {
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
      if (min!=null) inp.min = min;
      if (max!=null) inp.max = max;
      inp.type = "number";
      if (m.units) inp.placeholder = m.units;
    }
    if (prefix==="trigger") {
      outType = m.type;
      buildResultDevices();
    }
  }

  // ── custom-poll & custom-timeouts ────────────────────────────
  if (prefix==="trigger") {
    if (m.poll_interval>0) {
      triggerPollRow.classList.remove("d-none");
      triggerPollChk.checked = false;
      f.trigger_poll_value.value = m.poll_interval;
      f.trigger_poll_unit.value  = m.poll_interval_unit||"sec";
      f.trigger_poll_value.disabled = true;
      f.trigger_poll_unit.disabled  = true;
    } else {
      triggerPollRow.classList.add("d-none");
    }
  }
  if (prefix==="result"  && m.timeout>0) {
    resultTimeoutRow.classList.remove("d-none");
    resultTimeoutChk.checked = false;
    f.result_timeout_value.value = m.timeout;
    f.result_timeout_unit.value  = m.timeout_unit||"sec";
    f.result_timeout_value.disabled = true;
    f.result_timeout_unit.disabled  = true;
  }
  if (prefix==="succ"    && m.timeout>0) {
    succTimeoutRow.classList.remove("d-none");
    succTimeoutChk.checked = false;
    f.succ_timeout_value.value = m.timeout;
    f.succ_timeout_unit.value  = m.timeout_unit||"sec";
    f.succ_timeout_value.disabled = true;
    f.succ_timeout_unit.disabled  = true;
  }
  if (prefix==="err"     && m.timeout>0) {
    errTimeoutRow.classList.remove("d-none");
    errTimeoutChk.checked = false;
    f.err_timeout_value.value = m.timeout;
    f.err_timeout_unit.value  = m.timeout_unit||"sec";
    f.err_timeout_value.disabled = true;
    f.err_timeout_unit.disabled  = true;
  }
}

// ─── EVALUATE UI show/hide ────────────────────────────────────
qsa('input[name="eval_mode"]').forEach(r=>{
  r.addEventListener("change",()=>{
    const val = f.eval_mode.value;
    succRow.classList.toggle("d-none", !["success","both"].includes(val));
    errRow.classList.toggle("d-none", !["error","both"].includes(val));
  });
});

// ─── “New Action” button ─────────────────────────────────────
qs("#addActionBtn").addEventListener("click", async()=>{
  currentEditId = null;
  f.reset(); f.classList.remove("was-validated");
  modalTitle.textContent = "New Action";
  outType = null;
  ignoreInputChk.checked = false;
  // hide all custom rows
  triggerPollRow?.classList.add("d-none");
  resultTimeoutRow?.classList.add("d-none");
  succTimeoutRow?.classList.add("d-none");
  errTimeoutRow?.classList.add("d-none");
  await buildTriggerDevices();
  // leave THEN/EVAL until topics chosen
  modal.show();
});

// ─── Form change dispatch ────────────────────────────────────
f.addEventListener("change", e=>{
  const n = e.target.name;
  if      (n==="trigger_device") loadTopics(e.target.value,"trigger");
  else if (n==="trigger_topic")  adaptInput("trigger");
  else if (n==="result_device")  loadTopics(e.target.value,"result");
  else if (n==="result_topic")   adaptInput("result");
  else if (n==="succ_device")    loadTopics(e.target.value,"succ");
  else if (n==="succ_topic")     adaptInput("succ");
  else if (n==="err_device")     loadTopics(e.target.value,"err");
  else if (n==="err_topic")      adaptInput("err");
  else if (e.target===ignoreInputChk) buildResultDevices();
});

// ─── Save (create/update) ────────────────────────────────────
qs("#saveActionBtn").addEventListener("click",async()=>{
  f.classList.add("was-validated");
  if (!f.checkValidity()) return;

  // build branches
  const evalMode = f.eval_mode.value;
  let sb = ["success","both"].includes(evalMode) ? {
    device_id: +f.succ_device.value,
    topic:     f.succ_topic.value,
    command:   f.succ_command.value
  } : null;
  let eb = ["error","both"].includes(evalMode) ? {
    device_id: +f.err_device.value,
    topic:     f.err_topic.value,
    command:   f.err_command.value
  } : null;
  // custom timeouts
  if (sb && succTimeoutChk.checked) {
    sb.timeout = {
      value: +f.succ_timeout_value.value,
      unit:  f.succ_timeout_unit.value
    };
  }
  if (eb && errTimeoutChk.checked) {
    eb.timeout = {
      value: +f.err_timeout_value.value,
      unit:  f.err_timeout_unit.value
    };
  }

  // base payload
  const payload = {
    name:        f.name.value.trim(),
    description: f.description.value.trim(),
    enabled:     f.enabled.checked,
    trigger: {
      device_id: +f.trigger_device.value,
      topic:     f.trigger_topic.value,
      cmp:       f.trigger_cmp?.value||"==",
      value:     f.trigger_value.value||""
    },
    result: {
      device_id:    +f.result_device.value,
      topic:        f.result_topic.value,
      command:      f.result_command.value,
      ignore_input: ignoreInputChk.checked
    },
    evaluate: { mode: evalMode, success: sb, error: eb }
  };

  // custom-poll
  if (triggerPollChk.checked) {
    payload.trigger.poll_interval = {
      value: +f.trigger_poll_value.value,
      unit:  f.trigger_poll_unit.value
    };
  }
  // custom THEN-timeout
  if (resultTimeoutChk.checked) {
    payload.result.timeout = {
      value: +f.result_timeout_value.value,
      unit:  f.result_timeout_unit.value
    };
  }

  const url    = currentEditId?`/actions/${currentEditId}`:"/actions/";
  const method = currentEditId?"PUT":"POST";
  const res    = await fetch(url, {
    method, headers: {"Content-Type":"application/json"},
    body: JSON.stringify(payload)
  });

  if (res.ok) {
    modal.hide();
    await loadRows();
    currentEditId = null;
    toast("Saved");
  } else {
    const err = await res.json();
    toast(err?.message || "Error", "danger");
  }
});

// ─── Kick it off ─────────────────────────────────────────────
document.addEventListener("DOMContentLoaded", loadRows);
