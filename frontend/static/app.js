let dronePoints = [];
let eventSource = null;
let attackHistory = [];

function connectSSE() {
  if (eventSource) eventSource.close();
  eventSource = new EventSource("/stream");

  eventSource.onmessage = function(e) {
    if (e.data === '') return;
    try {
      const msg = JSON.parse(e.data);
      if (msg.type === "ping") return;
      handleEvent(msg);
    } catch (err) {}
  };

  eventSource.onerror = function() {
    setTimeout(connectSSE, 2000);
  };
}

function handleEvent(msg) {
  switch (msg.type) {
    case "status":
      updateTelemetry(msg.data);
      break;
    case "telemetry":
      updateCryptoPanel(msg.packet);
      break;
    case "auth":
      updateAuth(msg.status);
      break;
    case "attack":
      showAttackResult(msg);
      break;
    case "error":
      addLogEntry("ERROR", msg.message, "#ff1744");
      break;
  }
}

function updateTelemetry(data) {
  document.getElementById("t-lat").textContent = data.gps_lat.toFixed(6);
  document.getElementById("t-lon").textContent = data.gps_lon.toFixed(6);
  document.getElementById("t-alt").innerHTML = data.altitude.toFixed(1) + ' <span class="unit">m</span>';
  document.getElementById("t-speed").innerHTML = data.speed.toFixed(1) + ' <span class="unit">m/s</span>';
  document.getElementById("t-heading").innerHTML = data.heading.toFixed(0) + '&deg;';

  const bat = Math.max(0, data.battery);
  document.getElementById("battery-fill").style.width = bat + "%";
  document.getElementById("battery-text").textContent = bat.toFixed(0) + "%";

  if (bat < 20) {
    document.getElementById("battery-fill").style.background = "linear-gradient(90deg, #ff1744, #ff5252)";
  } else if (bat < 50) {
    document.getElementById("battery-fill").style.background = "linear-gradient(90deg, #ff9100, #ffab40)";
  } else {
    document.getElementById("battery-fill").style.background = "linear-gradient(90deg, #00c853, #69f0ae)";
  }

  const sig = Math.min(100, Math.max(0, data.signal_strength));
  const bars = document.querySelectorAll(".signal-bars span");
  const barHeights = [4, 8, 12, 16, 20];
  const activeBars = Math.ceil(sig / 20);
  bars.forEach((bar, i) => {
    bar.style.height = barHeights[i] + "px";
    bar.style.background = i < activeBars ? (i < 2 ? "#ff9100" : i < 4 ? "#00c853" : "#2979ff") : "#1e3a5f";
  });

  document.getElementById("t-packets").textContent = data.packets_sent;

  const statusEl = document.getElementById("t-status");
  if (data.battery > 20) {
    statusEl.textContent = "EN RUTA";
    statusEl.style.color = "#69f0ae";
  } else {
    statusEl.textContent = "REGRESANDO";
    statusEl.style.color = "#ff9100";
  }

  if (data.authenticated) {
    document.getElementById("auth-badge").textContent = "AUTH OK";
    document.getElementById("auth-badge").className = "badge badge-success";
  } else {
    document.getElementById("auth-badge").textContent = "AUTH FAIL";
    document.getElementById("auth-badge").className = "badge badge-danger";
  }

  if (data.challenge) {
    document.getElementById("puf-challenge").textContent = data.challenge;
  }
  if (data.response) {
    document.getElementById("puf-response").textContent = data.response;
  }

  updateMap(data.gps_lat, data.gps_lon);

  if (data.attack_detected) {
    document.getElementById("attack-card").style.borderColor = "#ff1744";
  } else {
    document.getElementById("attack-card").style.borderColor = "#1e3a5f";
  }
}

function updateCryptoPanel(packet) {
  document.getElementById("c-caesar").textContent = "Shift: " + (packet.shift || "?");
  document.getElementById("c-vigenere").textContent = "Key: " + (packet.vigenere_key || "?");
  document.getElementById("c-chacha").textContent = "IV: " + (packet.iv ? packet.iv.substring(0, 8) + "..." : "?");
  const ct = packet.ciphertext || "";
  const display = ct.substring(0, 32);
  document.getElementById("c-result").textContent = display ? display + "..." : "---";
  const size = packet.size || (ct.length / 2);
  document.getElementById("crypto-size").textContent = "Tamaño cifrado: " + size + " bytes";
}

function updateAuth(status) {
  if (status === "success") {
    document.getElementById("auth-badge").textContent = "AUTH OK";
    document.getElementById("auth-badge").className = "badge badge-success";
    addLogEntry("\u2713", "AUTH_OK", "Autenticaci\u00f3n PUF exitosa");
  }
}

function addLogEntry(step, action, detail) {
  const log = document.getElementById("log-entries");
  const entry = document.createElement("div");
  entry.className = "log-entry";
  const color = action.includes("AUTH") ? "#69f0ae" :
                action.includes("ENCRYPT") ? "#2979ff" : "#7a8ba8";
  entry.innerHTML = '<span class="log-step" style="color:'+color+'">' + step + '</span>' +
                    '<span class="log-action">' + action + '</span>' +
                    '<span class="log-detail">' + (detail || "") + '</span>';
  log.insertBefore(entry, log.firstChild);
  while (log.children.length > 100) {
    log.removeChild(log.lastChild);
  }
}

function updateMap(lat, lon) {
  const canvas = document.getElementById("map-canvas");
  if (!canvas) return;
  const ctx = canvas.getContext("2d");

  const rect = canvas.parentElement.getBoundingClientRect();
  canvas.width = canvas.clientWidth || rect.width || 400;
  canvas.height = canvas.clientHeight || rect.height || 280;

  const w = canvas.width, h = canvas.height;
  const centerLat = -16.409, centerLon = -71.537;
  const scale = 8000;

  const x = w/2 + (lon - centerLon) * scale;
  const y = h/2 - (lat - centerLat) * scale;

  dronePoints.push({x, y});
  if (dronePoints.length > 100) dronePoints.shift();

  ctx.clearRect(0, 0, w, h);

  ctx.strokeStyle = "rgba(30,58,95,0.3)";
  ctx.lineWidth = 0.5;
  for (let i = 0; i < w; i += 30) {
    ctx.beginPath(); ctx.moveTo(i, 0); ctx.lineTo(i, h); ctx.stroke();
  }
  for (let i = 0; i < h; i += 30) {
    ctx.beginPath(); ctx.moveTo(0, i); ctx.lineTo(w, i); ctx.stroke();
  }

  if (dronePoints.length > 1) {
    ctx.beginPath();
    ctx.strokeStyle = "rgba(0,212,255,0.4)";
    ctx.lineWidth = 2;
    ctx.moveTo(dronePoints[0].x, dronePoints[0].y);
    for (let i = 1; i < dronePoints.length; i++) {
      ctx.lineTo(dronePoints[i].x, dronePoints[i].y);
    }
    ctx.stroke();
  }

  const px = dronePoints.length > 0 ? dronePoints[dronePoints.length-1].x : x;
  const py = dronePoints.length > 0 ? dronePoints[dronePoints.length-1].y : y;

  const grad = ctx.createRadialGradient(px, py, 2, px, py, 20);
  grad.addColorStop(0, "rgba(0,212,255,0.6)");
  grad.addColorStop(1, "rgba(0,212,255,0)");
  ctx.fillStyle = grad;
  ctx.beginPath(); ctx.arc(px, py, 20, 0, Math.PI*2); ctx.fill();

  ctx.fillStyle = "#00d4ff";
  ctx.beginPath(); ctx.arc(px, py, 5, 0, Math.PI*2); ctx.fill();

  ctx.strokeStyle = "rgba(0,212,255,0.3)";
  ctx.lineWidth = 0.5;
  ctx.beginPath();
  ctx.arc(px, py, 15, 0, Math.PI*2);
  ctx.stroke();

  ctx.strokeStyle = "rgba(41,121,255,0.2)";
  ctx.setLineDash([3,6]);
  ctx.beginPath();
  ctx.arc(w/2, h/2, 30, 0, Math.PI*2);
  ctx.stroke();
  ctx.setLineDash([]);

  ctx.fillStyle = "#7a8ba8";
  ctx.font = "10px monospace";
  ctx.fillText("BASE", w/2 - 15, h/2 + 35);
  ctx.fillStyle = "#00d4ff";
  ctx.fillText("DRONE", px + 12, py + 4);
}

function simulateAttack(seed) {
  const resultEl = document.getElementById("attack-result");
  const logEl = document.getElementById("attack-log");

  resultEl.className = "attack-result";
  resultEl.style.display = "none";

  fetch("/api/attack/" + seed)
    .then(r => r.json())
    .then(data => {
      if (data.detected) {
        resultEl.className = "attack-result success";
        resultEl.style.display = "block";
        resultEl.innerHTML = '&#9989; ATAQUE DETECTADO: Dron falso (seed=' + data.fake_seed +
          ') respondi&oacute; ' + data.fake_response + ' vs esperado ' + data.real_response;
      } else {
        resultEl.className = "attack-result danger";
        resultEl.style.display = "block";
        resultEl.innerHTML = '&#9888; ATAQUE NO DETECTADO (coincidencia fortuita)';
      }
      attackHistory.push(data);
      logEl.textContent = "Historial: " + attackHistory.length + " ataques simulados, " +
        attackHistory.filter(a => a.detected).length + " detectados";
    });
}

function resetDrone() {
  fetch("/api/reset")
    .then(r => r.json())
    .then(data => {
      if (data.status === "reset_ok") {
        dronePoints = [];
        attackHistory = [];
        document.getElementById("attack-result").style.display = "none";
        document.getElementById("attack-log").textContent = "";
        const canvas = document.getElementById("map-canvas");
        if (canvas) {
          const ctx = canvas.getContext("2d");
          ctx.clearRect(0, 0, canvas.width, canvas.height);
        }
        document.getElementById("log-entries").innerHTML = "";
        addLogEntry("RESET", "SISTEMA", "Drone reiniciado");
      }
    });
}

connectSSE();

window.addEventListener("resize", function() {
  const canvas = document.getElementById("map-canvas");
  if (canvas) {
    canvas.width = canvas.clientWidth;
    canvas.height = canvas.clientHeight;
  }
});
