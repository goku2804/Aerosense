import { initializeApp } from "https://www.gstatic.com/firebasejs/10.7.1/firebase-app.js";
import {
  getDatabase,
  ref,
  onValue,
  set,
} from "https://www.gstatic.com/firebasejs/10.7.1/firebase-database.js";

/* ================= FIREBASE ================= */
const firebaseConfig = {
  apiKey: "AIzaSyAtVR0yen_xAtvHtAqiGG1hZIp-BrGMhIk",
  authDomain: "air-quality226.firebaseapp.com",
  databaseURL: "https://air-quality226-default-rtdb.firebaseio.com",
  projectId: "air-quality226",
  storageBucket: "air-quality226.firebasestorage.app",
  messagingSenderId: "362215390108",
  appId: "1:362215390108:web:8f035a1af8f5dc27846659",
};

const app = initializeApp(firebaseConfig);
const db = getDatabase(app);

/* ================= REFERENCES ================= */
const sensorRef = ref(db, "sensor");
const fanRef = ref(db, "actuator/fan");
const modeRef = ref(db, "actuator/mode");
const predRef = ref(db, "prediction");

/* ================= ELEMENTS ================= */
const temp = document.getElementById("temp");
const hum = document.getElementById("hum");
const co = document.getElementById("co");
const pm10 = document.getElementById("pm10");
const pm25 = document.getElementById("pm25");

const fanState = document.getElementById("fanState");
const fanMode = document.getElementById("fanMode");

const autoBtn = document.getElementById("autoBtn");
const onBtn = document.getElementById("onBtn");
const offBtn = document.getElementById("offBtn");

/* ================= LIVE SENSOR ================= */
onValue(sensorRef, (snap) => {
  const d = snap.val();
  if (!d) return;

  temp.textContent = d.temp;
  hum.textContent = d.hum;
  co.textContent = d.co_ppm;
  pm10.textContent = d.pm10;
  pm25.textContent = d.pm25;
});

/* ================= FAN STATUS ================= */
onValue(fanRef, (s) => {
  fanState.textContent = s.val() ? "ON" : "OFF";
});

onValue(modeRef, (s) => {
  fanMode.textContent = s.val() || "AUTO";
});

/* ================= BUTTON ACTIONS (FIXED ONLY HERE) ================= */
autoBtn.onclick = () => {
  set(ref(db, "actuator"), {
    mode: "AUTO",
    fan: 0,
    reason: "AUTO MODE",
  });
};

onBtn.onclick = () => {
  set(ref(db, "actuator"), {
    mode: "EMERGENCY",
    fan: 1,
    reason: "MANUAL ON",
  });
};

offBtn.onclick = () => {
  set(ref(db, "actuator"), {
    mode: "FORCE_OFF",
    fan: 0,
    reason: "MANUAL OFF",
  });
};

/* ================= CHART COMMON CONFIG ================= */
const labels = ["Now", "+1 hr", "+2 hr", "+3 hr"];

function createBarChart(canvasId, title) {
  const canvas = document.getElementById(canvasId);

  if (!canvas) {
    console.error(`Canvas not found: ${canvasId}`);
    return null;
  }

  const ctx = canvas.getContext("2d");

  return new Chart(ctx, {
    type: "bar",
    data: {
      labels,
      datasets: [
        {
          label: title,
          data: [0, 0, 0, 0],
          backgroundColor: "#fb923c",
          borderRadius: 10,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      animation: false,
      plugins: {
        legend: { labels: { color: "#ffffff" } },
      },
      scales: {
        y: {
          beginAtZero: true,
          ticks: { color: "#cbd5f5" },
          grid: { color: "#1e293b" },
        },
        x: {
          ticks: { color: "#cbd5f5" },
          grid: { display: false },
        },
      },
    },
  });
}

/* ================= CREATE 3 SEPARATE CHARTS ================= */
const pm25Chart = createBarChart("pm25Chart", "PM2.5 Forecast");
const pm10Chart = createBarChart("pm10Chart", "PM10 Forecast");
const coChart = createBarChart("coChart", "CO Forecast");

/* ================= UPDATE ALL CHARTS ================= */
function updateAllCharts(p) {
  if (!p) return;

  const pm25Data = p.pm25 || [0, 0, 0, 0];
  const pm10Data = p.pm10 || [0, 0, 0, 0];
  const coData = p.co || [0, 0, 0, 0];

  if (pm25Chart) {
    pm25Chart.data.datasets[0].data = pm25Data;
    pm25Chart.update();
  }

  if (pm10Chart) {
    pm10Chart.data.datasets[0].data = pm10Data;
    pm10Chart.update();
  }

  if (coChart) {
    coChart.data.datasets[0].data = coData;
    coChart.update();
  }
}

/* ================= LIVE FORECAST ================= */
onValue(predRef, (snap) => {
  const prediction = snap.val();
  updateAllCharts(prediction);
});
