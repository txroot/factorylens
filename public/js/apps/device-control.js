(function() {
    document.addEventListener("DOMContentLoaded", () => {
  
      // Fetch & update one card
      async function refreshCard(card) {
        const id = card.dataset.devId;
        try {
          const res = await fetch(`/apps/device-control/state/${id}`);
          if (!res.ok) throw new Error(res.statusText);
          const st = await res.json();
  
          // === Relays ===
          card.querySelectorAll(".relay-toggle").forEach(el => {
            const ch = el.dataset.channel;
            el.checked = st.relay?.[ch]?.state === "on";
          });
  
          // === Inputs (bulb on/off) ===
          [0,1].forEach(idx => {
            const val = st.input?.[idx] ?? 0;
            const icon = document.getElementById(`input-icon-${id}-${idx}`);
            if (!icon) return;
            if (val) {
              icon.classList.replace("ti-bulb-off", "ti-bulb");
              icon.classList.replace("text-secondary", "text-warning");
            } else {
              icon.classList.replace("ti-bulb", "ti-bulb-off");
              icon.classList.replace("text-warning", "text-secondary");
            }
          });
  
          // === Temperature ===
          const tEl = document.getElementById(`temp-${id}`);
          if (tEl) tEl.textContent = `${st.temperature ?? "—"}°C`;
  
          // === Wattage ===
          const pEl = document.getElementById(`power-${id}`);
          if (pEl) pEl.textContent = `${st.relay?.["0"]?.power ?? "—"} W`;
  
        } catch (e) {
          console.warn("State refresh failed", e);
        }
      }
  
      // Initialize & poll every 5s
      const cards = Array.from(document.querySelectorAll("[data-dev-id]"));
      cards.forEach(refreshCard);
      setInterval(() => cards.forEach(refreshCard), 5000);
  
      // Handle relay toggles
      document.body.addEventListener("change", async e => {
        if (!e.target.matches(".relay-toggle")) return;
        const el = e.target;
        const card = el.closest("[data-dev-id]");
        const id = card.dataset.devId;
        const ch = el.dataset.channel;
        const turnOn = el.checked;
  
        el.disabled = true;
        try {
          await fetch(`/apps/device-control/relay/${id}/${ch}`, {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({on: turnOn})
          });
        } catch (err) {
          console.error(err);
        }
        el.disabled = false;
      });
  
    });
  })();
  