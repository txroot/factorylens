// static/js/apps/device-control.js
/* global fetch */
document.addEventListener("DOMContentLoaded", () => {
  const cards = Array.from(document.querySelectorAll("[data-dev-id]"));

  async function refresh(card) {
    const id = card.dataset.devId;
    try {
      const st = await (await fetch(`/apps/device-control/state/${id}`)).json();

      // ── INPUTS + EVENT COUNT ──────────────────────────────────────
      card.querySelectorAll(".input-radio").forEach(radio => {
        const idx = radio.id.split("-").pop();
        radio.checked = Boolean(st.input?.[idx]);
        const cnt = st.input_event?.[idx]?.event_cnt ?? 0;
        const evtLabel = card.querySelector(`#input-evt-${id}-${idx}`);
        if (evtLabel) evtLabel.textContent = `(${cnt})`;
      });

      // ── RELAYS ────────────────────────────────────────────────────
      card.querySelectorAll(".relay-toggle").forEach(sw => {
        const ch = sw.dataset.channel;
        sw.checked = st.relay?.[ch]?.state === "on";
      });

      // ── TEMPERATURES ─────────────────────────────────────────────
      const tC = st.temperature, tF = st.temperature_f;
      card.querySelector(`#temp-${id}`).textContent =
        tC != null ? `${tC}°C` : "—°C";
      card.querySelector(`#temp-f-${id}`).textContent =
        tF != null ? `${tF}°F` : "—°F";

      // ── POWER & ENERGY ───────────────────────────────────────────
      const p = st.relay?.["0"]?.power?.power ?? null;
      card.querySelector(`#power-${id}`).textContent =
        p != null ? `${p} W` : "— W";
      const e = st.relay?.["0"]?.energy;
      card.querySelector(`#energy-${id}`).textContent =
        e != null ? `${e} kWh` : "— kWh";

      // ── VOLTAGE ──────────────────────────────────────────────────
      const v = st.voltage;
      card.querySelector(`#voltage-${id}`).textContent =
        v != null ? `${v} V` : "— V";

      // ── RSSI ──────────────────────────────────────────────────────
      const rssiEl = card.querySelector(`#rssi-${id}`);
      const r = st.info?.wifi_sta?.rssi;
      if (rssiEl) rssiEl.textContent = r != null ? `${r} dBm` : "— dBm";

      // ── ONLINE / OFFLINE ─────────────────────────────────────────
      const online = Boolean(st.online);
      const dot = card.querySelector(`#status-dot-${id}`);
      const txt = card.querySelector(`#status-text-${id}`);
      const live = card.querySelector(".body-content");
      const offp = card.querySelector(".body-offline");

      if (dot && txt) {
        dot.classList.toggle("text-success",  online);
        dot.classList.toggle("text-secondary", !online);
        txt.textContent = online ? "online" : "offline";
        txt.classList.toggle("text-success",  online);
        txt.classList.toggle("text-danger", !online);
      }

      // swap live vs offline view
      if (live && offp) {
        if (online) {
          live.classList.remove("d-none");
          offp.classList.add("d-none");
        } else {
          live.classList.add("d-none");
          offp.classList.remove("d-none");
        }
      }
    } catch (err) {
      console.warn("refresh failed", err);
    }
  }

  // initial + periodic refresh
  cards.forEach(refresh);
  setInterval(() => cards.forEach(refresh), 3000);

  // relay toggle handler
  document.body.addEventListener("change", e => {
    if (!e.target.matches(".relay-toggle")) return;
    const sw   = e.target;
    const card = sw.closest("[data-dev-id]");
    fetch(`/apps/device-control/relay/${card.dataset.devId}/${sw.dataset.channel}`, {
      method:  "POST",
      headers: {"Content-Type":"application/json"},
      body:    JSON.stringify({ on: sw.checked })
    }).catch(console.error);
  });
});
