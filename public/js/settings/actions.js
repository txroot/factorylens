// public/js/settings/actions.js

/* Factory‑Lens – Actions page (IF → THEN → EVALUATE)
   Supports schema-based validation, type-filtering, and tooltips */

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
   
   qs("#actionsTable tbody")?.addEventListener("click", async e => {
     const btn = e.target.closest(".del-btn");
     if (!btn) return;
     if (!confirm("Delete this action?")) return;
     const res = await fetch(`/actions/${btn.dataset.id}`, { method: "DELETE" });
     res.ok ? (await loadRows(), toast("Deleted")) : toast("Error", "danger");
   });
   
   // Modal refs
   const modal = new bootstrap.Modal("#actionModal");
   const f = qs("#actionForm");
   const ignoreInputChk = qs("#ignoreInputChk");
   const succRow = qs("#succRow"), errRow = qs("#errRow");
   
   // Dropdowns
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
         const cmds = schema.command_topics || {};
         return Object.values(cmds).some(m => m.type === outType);
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
   
   async function loadTopics(devId, prefix) {
     const tSel = f[`${prefix}_topic`];
     const vCol = qs(`#${prefix}ValCol`);
     const cCol = qs(`#${prefix}CmpCol`);
   
     if (!tSel || !vCol) return;
     tSel.innerHTML = `<option disabled selected value="">—</option>`;
     tSel.disabled = true;
     cCol?.classList.add("d-none");
     vCol.querySelector("input,select")?.setAttribute("disabled", "");
   
     if (!devId) return;
   
     const schema = await getSchema(devId);
     const source = prefix === "trigger" ? schema.topics : schema.command_topics;
     if (!source) return;
   
     Object.entries(source).forEach(([t, m]) => {
       tSel.insertAdjacentHTML("beforeend",
         `<option value="${t}" data-meta='${JSON.stringify(m)}'>${m.label || t}</option>`);
     });
     tSel.disabled = false;
   }
   
   function adaptInput(prefix) {
     const topicSel = f[`${prefix}_topic`];
     if (!topicSel) return;
   
     const opt = topicSel.selectedOptions[0];
     const metaRaw = opt?.dataset.meta;
     if (!metaRaw) return;
   
     const m = JSON.parse(metaRaw);
     const vCol = qs(`#${prefix}ValCol`);
     const cCol = qs(`#${prefix}CmpCol`);
   
     if (!vCol) return;
   
     cCol?.classList.add("d-none");
     vCol.innerHTML =
       `<label class="form-label">${prefix === "trigger" ? "Value" : "Command"} *</label>
        <input name="${prefix === "trigger" ? "trigger_value" : `${prefix}_command`}"
               class="form-control" required>`;
     const inp = vCol.querySelector("input");
     inp?.removeAttribute("disabled");
   
     if (m.type === "enum" || m.type === "bool") {
       const opts = m.type === "bool" ? ["true", "false"] : m.values;
       vCol.innerHTML =
         `<label class="form-label">${prefix === "trigger" ? "Value" : "Command"} *</label>
          <select name="${prefix === "trigger" ? "trigger_value" : `${prefix}_command`}"
                  class="form-select" required>
            <option disabled selected value="">—</option>
            ${opts.map(v => `<option value="${v}">${m.display?.[v] || v}</option>`).join("")}
          </select>`;
     } else if (m.type === "number") {
       if (cCol) {
         cCol.classList.remove("d-none");
         cCol.innerHTML =
           `<label class="form-label">Cmp.</label>
            <select name="${prefix}_cmp" class="form-select">
              ${(m.comparators || ["<", "<=", "==", "!=", ">=", ">"])
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
   
     if (prefix === "trigger") {
       outType = m.type;
       buildResultDevices();
     }
   }
   
   const modeRadios = Array.from(f.querySelectorAll('input[name="eval_mode"]'));
   function updateEvalUI() {
     const mode = f.eval_mode.value;
     succRow.classList.toggle("d-none", !["success", "both"].includes(mode));
     errRow.classList.toggle("d-none", !["error", "both"].includes(mode));
   }
   modeRadios.forEach(r => r.addEventListener("change", updateEvalUI));
   
   qs("#addActionBtn")?.addEventListener("click", async () => {
     f.reset(); f.classList.remove("was-validated");
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
   
   qs("#saveActionBtn")?.addEventListener("click", async () => {
     f.classList.add("was-validated");
     if (!f.checkValidity()) return;
   
     const evalMode = f.eval_mode.value;
     const successBranch = ["success", "both"].includes(evalMode) ? {
       device_id: +f.succ_device.value,
       topic: f.succ_topic.value,
       command: f.succ_command.value
     } : null;
     const errorBranch = ["error", "both"].includes(evalMode) ? {
       device_id: +f.err_device.value,
       topic: f.err_topic.value,
       command: f.err_command.value
     } : null;
   
     const payload = {
       name: f.name.value.trim(),
       description: f.description.value.trim(),
       enabled: f.enabled.checked,
       trigger: {
         device_id: +f.trigger_device.value,
         topic: f.trigger_topic.value,
         cmp: f.trigger_cmp?.value || "==",
         value: f.trigger_value?.value || ""
       },
       result: {
         device_id: +f.result_device.value,
         topic: f.result_topic.value,
         command: f.result_command.value,
         ignore_input: ignoreInputChk.checked
       },
       evaluate: {
         mode: evalMode,
         success: successBranch,
         error: errorBranch
       }
     };
   
     const res = await fetch("/actions/", {
       method: "POST",
       headers: { "Content-Type": "application/json" },
       body: JSON.stringify(payload)
     });
   
     if (res.ok) {
       modal.hide();
       await loadRows();
       toast("Saved");
     } else {
       toast((await res.json())?.message || "Error", "danger");
     }
   });
   
   document.addEventListener("DOMContentLoaded", loadRows);
   