/* global fetch */
document.addEventListener("DOMContentLoaded", () => {
  const cards = Array.from(document.querySelectorAll("[data-dev-id]"));

  // ── Pull in state for one card and update its UI ──────────────────
  async function refresh(card) {
    const id = card.dataset.devId;
    try {
      const res = await fetch(`/apps/device-control/state/${id}`);
      if (!res.ok) throw new Error(res.statusText);
      const st = await res.json();

      console.log("State for", id, st);

      // ── INPUT BADGES ─────────────────────────────────────────────
      for (let idx of [0,1]) {
        const isOn = Boolean(st.input?.[idx]);
        const badge = card.querySelector(`#input-badge-${id}-${idx}`);
        if (!badge) continue;
        badge.classList.toggle("bg-primary", isOn);
        badge.classList.toggle("bg-light",   !isOn);
        badge.classList.toggle("text-white",  isOn);
        badge.classList.toggle("text-muted",  !isOn);
      }

      // ── RELAYS ────────────────────────────────────────────────────
      card.querySelectorAll(".relay-toggle").forEach(sw => {
        const ch = sw.dataset.channel;
        sw.checked = st.relay?.[ch]?.state === "on";
      });

      // ── TEMPERATURE ───────────────────────────────────────────────
      const tC = st.temperature, tF = st.temperature_f;
      card.querySelector(`#temp-${id}`).textContent =
        tC != null ? `${tC}°C` : "—°C";
      const tempFEl = card.querySelector(`#temp-f-${id}`);
      if (tempFEl) {
        tempFEl.textContent = tF != null ? `${tF}°F` : "—°F";
      }

      // ── POWER & ENERGY ────────────────────────────────────────────
      const p = st.relay?.["0"]?.power?.power
              ?? st.relay?.["0"]?.power
              ?? null;
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
      const rssi   = st.info?.wifi_sta?.rssi;

      // ── ONLINE / OFFLINE ─────────────────────────────────────────
      const online = st.online === true || st.online === "true";
      const dot    = card.querySelector(`#status-dot-${id}`);
      const txt    = card.querySelector(`#status-text-${id}`);
      const live   = card.querySelector(".body-content");
      const offp   = card.querySelector(".body-offline");

      if (dot && txt) {
        dot.classList.remove("text-success", "text-danger", "text-secondary");
        txt.classList.remove("text-success", "text-danger", "text-secondary");
        if (online) {
          dot.classList.add("text-success");
          txt.classList.add("text-success");
          txt.textContent = "online";
        } else {
          dot.classList.add("text-danger");
          txt.classList.add("text-danger");
          txt.textContent = "offline";
        }
      }

      // swap views + clear RSSI when offline
      if (live && offp) {
        if (online) {
          live.classList.remove("d-none");
          offp.classList.add("d-none");
          if (rssiEl)
            rssiEl.textContent = rssi != null ? `${rssi} dBm` : "— dBm";
        } else {
          live.classList.add("d-none");
          offp.classList.remove("d-none");
          if (rssiEl) rssiEl.textContent = "— dBm";
        }
      }

    } catch (err) {
      console.warn("refresh failed", err);
    }
  }

  // ── Fire all initial refreshes in parallel, then start interval ───
  async function initialAndPoll() {
    await Promise.all(cards.map(refresh));
    setInterval(() => cards.forEach(refresh), 333);
  }
  initialAndPoll();

  // ── Relay toggle handler ────────────────────────────────────────
  document.body.addEventListener("change", e => {
    if (!e.target.matches(".relay-toggle")) return;
    const sw   = e.target;
    const card = sw.closest("[data-dev-id]");
    fetch(
      `/apps/device-control/relay/${card.dataset.devId}/${sw.dataset.channel}`,
      {
        method:  "POST",
        headers: {"Content-Type":"application/json"},
        body:    JSON.stringify({ on: sw.checked })
      }
    ).catch(console.error);
  });
});
