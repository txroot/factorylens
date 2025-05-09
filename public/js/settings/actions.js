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
    res.ok
      ? (await loadActionRows(), toast("Deleted"))
      : toast("Error", "danger");
  });

/* ------------------------------------------------------------------ */
/*  Modal & form refs                                                 */
/* ------------------------------------------------------------------ */
const modal     = new bootstrap.Modal("#actionModal");
const form      = document.getElementById("actionForm");
const titleSpan = document.getElementById("modalTitle");

let deviceCache = [];
let schemaCache = new Map();

/* ------------------------------------------------------------------ */
/*  Fetchers                                                          */
/* ------------------------------------------------------------------ */
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

/* ------------------------------------------------------------------ */
/*  Populate device <select> for trigger, result, eval-success, error */
/* ------------------------------------------------------------------ */
async function fillDeviceSelects() {
  const devs = await fetchDevices();
  const grouped = devs.reduce((acc, d) => {
    if (!d.enabled) return acc;
    (acc[d.category] ||= []).push(d);
    return acc;
  }, {});

  ["trigger_device","result_device","eval_success_device","eval_error_device"]
    .forEach(name => {
      const sel = form[name];
      sel.innerHTML = `<option value="" disabled selected>—</option>`;
      Object.entries(grouped).forEach(([cat,list])=>{
        const og = document.createElement("optgroup");
        og.label = cat.charAt(0).toUpperCase()+cat.slice(1);
        list.forEach(d=>
          og.insertAdjacentHTML("beforeend",
            `<option value="${d.id}">${d.name}</option>`));
        sel.appendChild(og);
      });
    });
}

/* ------------------------------------------------------------------ */
/*  Load topics or commands into the IF/THEN dropdowns                */
/* ------------------------------------------------------------------ */
async function loadTopics(devId, prefix) {
  const topicSel = form[`${prefix}_topic`];
  const valCol   = document.getElementById(`${prefix}ValCol`);
  const cmpCol   = document.getElementById(`${prefix}CmpCol`);

  topicSel.innerHTML = '<option value="" disabled selected>—</option>';
  topicSel.disabled  = true;
  cmpCol?.classList.add("d-none");
  valCol.querySelector("input,select")?.setAttribute("disabled","");

  if (!devId) return;
  const schema = await getSchema(devId);
  const src    = prefix==="trigger"? schema.topics : schema.command_topics;
  if (!src) return;

  Object.entries(src).forEach(([t,meta]) => {
    topicSel.insertAdjacentHTML("beforeend",
      `<option value="${t}" data-meta='${JSON.stringify(meta)}'>${meta.label||t}</option>`);
  });
  topicSel.disabled = false;
}

/* ------------------------------------------------------------------ */
/*  Adapt the “Value” / “Command” field after topic selection         */
/* ------------------------------------------------------------------ */
function adaptValueInput(prefix) {
  const topicSel = form[`${prefix}_topic`];
  const metaRaw  = topicSel.selectedOptions[0]?.dataset.meta;
  if (!metaRaw) return;

  const m      = JSON.parse(metaRaw);
  const cmpCol = document.getElementById(`${prefix}CmpCol`);
  const valCol = document.getElementById(`${prefix}ValCol`);

  cmpCol.classList.add("d-none");
  valCol.innerHTML = `
    <label class="form-label">
      ${prefix==="trigger"?"Value":"Command"} *
    </label>
    <input name="${prefix==="trigger"?"trigger_value":"result_command"}"
           class="form-control" required>`;
  const inp = valCol.querySelector("input");
  inp.removeAttribute("disabled");

  if (m.type==="enum"||m.type==="bool") {
    const opts = m.type==="bool"?["true","false"]:m.values;
    valCol.innerHTML = `
      <label class="form-label">
        ${prefix==="trigger"?"Value":"Command"} *
      </label>
      <select name="${prefix==="trigger"?"trigger_value":"result_command"}"
              class="form-select" required>
        <option value="" disabled selected>—</option>
        ${opts.map(v=>
          `<option value="${v}">${m.display?.[v]||v}</option>`).join("")}
      </select>`;
  }
  else if (m.type==="number") {
    cmpCol.classList.remove("d-none");
    cmpCol.innerHTML = `
      <label class="form-label">Cmp.</label>
      <select name="${prefix}_cmp" class="form-select">
        ${ (m.comparators||["<","<=","==","!="," >=",">"])
            .map(c=>`<option value="${c.trim()}">${c.trim()}</option>`).join("")}
      </select>`;
    if (m.range) {
      const [min,max] = m.range;
      if (min!=null) inp.min = min;
      if (max!=null) inp.max = max;
    }
    inp.type = "number";
    if (m.units) inp.placeholder = m.units;
  }
}

/* ------------------------------------------------------------------ */
/*  Load “functions” for eval-success or eval-error                   */
/* ------------------------------------------------------------------ */
async function loadFunctions(devId, prefix) {
  const fnSel = form[`${prefix}_fn`];
  fnSel.innerHTML = `<option value="" disabled selected>—</option>`;
  fnSel.disabled = true;
  if (!devId) return;
  const schema = await getSchema(devId);
  const funcs  = schema.functions||[];
  funcs.forEach(f=>{
    fnSel.insertAdjacentHTML("beforeend",
      `<option value="${f.name}">${f.label||f.name}</option>`);
  });
  fnSel.disabled = false;
}

/* ------------------------------------------------------------------ */
/*  Modal open + wiring                                               */
/* ------------------------------------------------------------------ */
document.getElementById("addActionBtn")?.addEventListener("click", async () => {
  form.reset();
  form.classList.remove("was-validated");
  titleSpan.textContent = "New Action";
  await fillDeviceSelects();
  modal.show();
});

form.addEventListener("change", e => {
  switch(e.target.name) {
    case "trigger_device":
      loadTopics(e.target.value, "trigger");
      break;
    case "result_device":
      loadTopics(e.target.value, "result");
      break;
    case "trigger_topic":
      adaptValueInput("trigger");
      break;
    case "result_topic":
      adaptValueInput("result");
      break;
    case "evaluate":
      // show/hide configs
      document.getElementById("successConfig")
        .classList.toggle("d-none", e.target.value!=="success");
      document.getElementById("errorConfig")
        .classList.toggle("d-none", e.target.value!=="error");
      // enable or disable fields
      ["eval_success_device","eval_success_fn","eval_success_args"]
        .forEach(n => form[n].disabled = e.target.value!=="success");
      ["eval_error_device","eval_error_fn","eval_error_args"]
        .forEach(n => form[n].disabled = e.target.value!=="error");
      break;
    case "eval_success_device":
      loadFunctions(e.target.value, "eval_success");
      break;
    case "eval_error_device":
      loadFunctions(e.target.value, "eval_error");
      break;
  }
});

/* ------------------------------------------------------------------ */
/*  Save form → POST                                                  */
/* ------------------------------------------------------------------ */
document.getElementById("saveActionBtn").addEventListener("click", async () => {
  form.classList.add("was-validated");
  if (!form.checkValidity()) return;

  const evaluateMode = form.evaluate.value;
  const payload = {
    name:        form.name.value.trim(),
    description: form.description.value.trim(),
    enabled:     form.enabled.checked,
    trigger: {
      device_id: +form.trigger_device.value,
      topic:     form.trigger_topic.value,
      cmp:       form.trigger_cmp?.value || "==",
      value:     form.trigger_value?.value || ""
    },
    result: {
      device_id: +form.result_device.value,
      topic:     form.result_topic.value,
      cmp:       form.result_cmp?.value || "==",
      command:   form.result_command?.value || ""
    },
    evaluate: {
      mode: evaluateMode,
      success: evaluateMode==="success" && {
        device_id: +form.eval_success_device.value,
        fn:        form.eval_success_fn.value,
        args:      JSON.parse(form.eval_success_args.value || "{}")
      },
      error: evaluateMode==="error" && {
        device_id: +form.eval_error_device.value,
        fn:        form.eval_error_fn.value,
        args:      JSON.parse(form.eval_error_args.value || "{}")
      }
    }
  };

  const res = await fetch("/actions/", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
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
/*  Initial load                                                      */
/* ------------------------------------------------------------------ */
document.addEventListener("DOMContentLoaded", loadActionRows);
