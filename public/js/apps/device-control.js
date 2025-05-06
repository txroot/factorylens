(async function() {
  document.addEventListener("DOMContentLoaded", () => {

    async function refreshCard(card) {
      const id = card.dataset.devId;
      try {
        const res = await fetch(`/apps/device-control/state/${id}`);
        if (!res.ok) throw new Error(res.statusText);
        const st = await res.json();

        // — Inputs (radio buttons) —
        card.querySelectorAll(".input-radio").forEach(radio => {
          // id is "input-<devId>-<idx>"
          const parts = radio.id.split("-");
          const idx   = parts[parts.length - 1];
          radio.checked = Boolean(st.input?.[idx]);
        });

        // — Outputs (switches) —
        card.querySelectorAll(".relay-toggle").forEach(el => {
          const ch = el.dataset.channel;
          el.checked = st.relay?.[ch]?.state === "on";
        });

        // — Temperature, Wattage, Voltage etc. — (unchanged)
        const tEl = card.querySelector(`#temp-${id}`);
        if (tEl) tEl.textContent = `${st.temperature ?? "—"}°C`;

        const pEl = card.querySelector(`#power-${id}`);
        if (pEl) {
          let raw   = st.relay?.["0"]?.power;
          let watts = "—";
          if (raw != null) {
            if (typeof raw === "object") {
              const nums = Object.values(raw)
                                 .filter(v => !isNaN(parseFloat(v)));
              if (nums.length) watts = nums[0];
            } else {
              watts = raw;
            }
          }
          pEl.textContent = `${watts} W`;
        }

        const vEl = card.querySelector(`#voltage-${id}`);
        if (vEl) vEl.textContent = `${st.voltage ?? "—"} V`;

      } catch (e) {
        console.warn("State refresh failed", e);
      }
    }

    const cards = Array.from(document.querySelectorAll("[data-dev-id]"));
    cards.forEach(refreshCard);
    setInterval(() => cards.forEach(refreshCard), 5000);

    // relay toggle handler: unchanged
    document.body.addEventListener("change", async e => {
      if (!e.target.matches(".relay-toggle")) return;
      const el   = e.target;
      const card = el.closest("[data-dev-id]");
      const id   = card.dataset.devId;
      const ch   = el.dataset.channel;
      const on   = el.checked;
      el.disabled = true;
      try {
        await fetch(`/apps/device-control/relay/${id}/${ch}`, {
          method: "POST",
          headers: {"Content-Type":"application/json"},
          body: JSON.stringify({on})
        });
      } catch {}
      el.disabled = false;
    });

  });
})();
