/* global fetch */
document.addEventListener("DOMContentLoaded", () => {

  const cards = Array.from(document.querySelectorAll("[data-dev-id]"));

  async function refresh(card) {
    const id = card.dataset.devId;
    try {
      const st = await (await fetch(`/apps/device-control/state/${id}`)).json();

      // inputs
      card.querySelectorAll(".input-radio").forEach(radio => {
        const idx = radio.id.split("-").pop();
        radio.checked = !!st.input?.[idx];
      });

      // relays
      card.querySelectorAll(".relay-toggle").forEach(sw => {
        const ch = sw.dataset.channel;
        sw.checked = !!st.relay?.[ch]?.state;
      });

      // temperature / voltage / power
      card.querySelector(`#temp-${id}`).textContent =
        st.temperature != null ? `${st.temperature}°C` : "—°C";
      card.querySelector(`#voltage-${id}`).textContent =
        st.voltage != null ? `${st.voltage} V` : "— V";
      card.querySelector(`#power-${id}`).textContent =
        st.relay?.["0"]?.power != null ? `${st.relay["0"].power} W` : "— W";

    } catch (err) {
      console.warn("refresh failed", err);
    }
  }

  cards.forEach(refresh);
  setInterval(() => cards.forEach(refresh), 3000);   // faster refresh

  // toggle relay
  document.body.addEventListener("change", e => {
    if (!e.target.matches(".relay-toggle")) return;
    const sw   = e.target;
    const card = sw.closest("[data-dev-id]");
    fetch(`/apps/device-control/relay/${card.dataset.devId}/${sw.dataset.channel}`, {
      method : "POST",
      headers: {"Content-Type":"application/json"},
      body   : JSON.stringify({on: sw.checked})
    }).catch(console.error);
  });
});