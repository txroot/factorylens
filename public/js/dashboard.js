// dashboard.js
(() => {
    document.addEventListener('DOMContentLoaded', () => {
      /* ---------------------- Fake chart data ---------------------- */
      const labels = Array.from({ length: 24 }, (_, i) => `${i}:00`);
      const eventCounts = [
        3, 5, 2, 1, 0, 0, 4, 6, 9, 11, 10, 7,
        8, 12, 14, 9, 6, 5, 7, 4, 3, 2, 1, 0
      ];
  
      /* ------------------ Chart.js line chart ---------------------- */
      const ctx = document.getElementById('eventsChart');
  
      new Chart(ctx, {
        type: 'line',
        data: {
          labels,
          datasets: [{
            label: 'Events',
            data: eventCounts,
            fill: true,
            tension: 0.3
          }]
        },
        options: {
          scales: {
            y: { beginAtZero: true, ticks: { stepSize: 5 } }
          },
          plugins: {
            legend: { display: false },
            tooltip: { mode: 'index', intersect: false }
          }
        }
      });
    });
  })();
  