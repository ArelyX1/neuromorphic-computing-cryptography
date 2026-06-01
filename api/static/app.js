let dronePoints = [];
let eventSource = null;
let attackHistory = [];
let pufCrpCount = 0;
let packetsSent = 0;
let startTime = Date.now();

/* ===== BACKGROUND ANIMATION ===== */
(function initBg() {
  const c = document.getElementById('bg-canvas');
  if (!c) return;
  const ctx = c.getContext('2d');
  let w, h, particles = [];

  function resize() {
    w = c.width = window.innerWidth;
    h = c.height = window.innerHeight;
  }
  resize();
  window.addEventListener('resize', resize);

  for (let i = 0; i < 60; i++) {
    particles.push({
      x: Math.random() * w, y: Math.random() * h,
      vx: (Math.random() - 0.5) * 0.3,
      vy: (Math.random() - 0.5) * 0.3,
      r: Math.random() * 1.5 + 0.5,
    });
  }

  function draw() {
    ctx.clearRect(0, 0, w, h);
    particles.forEach(p => {
      p.x += p.vx; p.y += p.vy;
      if (p.x < 0) p.x = w; if (p.x > w) p.x = 0;
      if (p.y < 0) p.y = h; if (p.y > h) p.y = 0;
      ctx.beginPath();
      ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
      ctx.fillStyle = 'rgba(0, 212, 255, 0.08)';
      ctx.fill();
    });

    for (let i = 0; i < particles.length; i++) {
      for (let j = i + 1; j < particles.length; j++) {
        const dx = particles[i].x - particles[j].x;
        const dy = particles[i].y - particles[j].y;
        const dist = Math.sqrt(dx * dx + dy * dy);
        if (dist < 120) {
          ctx.beginPath();
          ctx.moveTo(particles[i].x, particles[i].y);
          ctx.lineTo(particles[j].x, particles[j].y);
          ctx.strokeStyle = `rgba(0, 212, 255, ${0.04 * (1 - dist / 120)})`;
          ctx.lineWidth = 0.5;
          ctx.stroke();
        }
      }
    }
    requestAnimationFrame(draw);
  }
  draw();
})();

/* ===== SSE ===== */
function connectSSE() {
  if (eventSource) eventSource.close();
  eventSource = new EventSource('/stream');

  eventSource.onmessage = function(e) {
    if (e.data === '') return;
    try {
      const msg = JSON.parse(e.data);
      if (msg.type === 'ping') return;
      handleEvent(msg);
    } catch (err) {}
  };

  eventSource.onerror = function() {
    setTimeout(connectSSE, 2000);
  };
}

function handleEvent(msg) {
  switch (msg.type) {
    case 'status':
      updateTelemetry(msg.data);
      break;
    case 'telemetry':
      updateCryptoPanel(msg.packet);
      break;
    case 'auth':
      updateAuth(msg.status);
      break;
    case 'attack':
      showAttackResult(msg);
      break;
    case 'error':
      addLogEntry('ERR', 'ERROR', msg.message, '#ff1744');
      break;
  }
}

/* ===== TELEMETRY ===== */
function updateTelemetry(data) {
  packetsSent = data.packets_sent || 0;

  document.getElementById('t-gps').textContent =
    (data.gps_lat || 0).toFixed(6) + ', ' + (data.gps_lon || 0).toFixed(6);
  document.getElementById('t-alt').innerHTML =
    (data.altitude || 0).toFixed(1) + ' <span class="unit">m</span>';
  document.getElementById('t-speed').innerHTML =
    (data.speed || 0).toFixed(1) + ' <span class="unit">m/s</span>';
  document.getElementById('t-heading').innerHTML =
    (data.heading || 0).toFixed(0) + '&deg;';

  const bat = Math.max(0, data.battery || 0);
  const fill = document.getElementById('battery-fill');
  fill.style.width = bat + '%';
  document.getElementById('battery-text').textContent = bat.toFixed(0) + '%';

  if (bat < 20) fill.style.background = 'linear-gradient(90deg, #ff1744, #ff5252)';
  else if (bat < 50) fill.style.background = 'linear-gradient(90deg, #ff9100, #ffab40)';
  else fill.style.background = 'linear-gradient(90deg, #00c853, #69f0ae)';

  const sig = Math.min(100, Math.max(0, data.signal_strength || 50));
  const bars = document.querySelectorAll('.signal-bars span');
  const activeBars = Math.ceil(sig / 20);
  bars.forEach((bar, i) => {
    const h = parseInt(bar.dataset.h);
    bar.style.height = (i < activeBars ? h : 2) + 'px';
    bar.style.background = i < activeBars
      ? (i < 2 ? '#ff9100' : i < 4 ? '#00c853' : '#2979ff')
      : 'rgba(255,255,255,0.06)';
  });

  document.getElementById('t-status').textContent =
    bat > 20 ? 'EN RUTA' : 'REGRESANDO';
  document.getElementById('t-status').style.color =
    bat > 20 ? '#69f0ae' : '#ff9100';

  /* Dashboard summary */
  document.getElementById('s-packets').textContent = packetsSent;
  document.getElementById('s-battery').textContent = bat.toFixed(0) + '%';

  const elapsed = Math.floor((Date.now() - startTime) / 1000);
  const mins = Math.floor(elapsed / 60);
  const secs = elapsed % 60;
  document.getElementById('s-age').textContent = mins + 'm ' + secs + 's';

  if (elapsed > 0) {
    const tps = (packetsSent / elapsed).toFixed(1);
    document.getElementById('s-throughput').textContent = tps + '/s';
  }

  /* Auth badge */
  const authBadge = document.getElementById('auth-badge');
  if (data.authenticated) {
    authBadge.textContent = 'AUTH OK';
    authBadge.className = 'badge badge-success';
  } else {
    authBadge.textContent = 'NO AUTH';
    authBadge.className = 'badge badge-danger';
  }

  /* PUF signals */
  if (data.challenge) {
    const bits = data.challenge.substring(0, 5);
    document.getElementById('puf-challenge').textContent = bits.length >= 5 ? bits + '...' : bits;

    /* Spike bars */
    const spikeBars = document.querySelectorAll('.puf-voltage-bars div');
    if (data.spike_levels) {
      spikeBars.forEach((bar, i) => {
        if (i < data.spike_levels.length) {
          bar.style.height = (data.spike_levels[i] * 100) + '%';
        }
      });
    }
  }
  if (data.response !== undefined) {
    document.getElementById('puf-response').textContent =
      (data.response === 1 ? '+1' : '-1') + ' / ' + (data.response === 1 ? '-1' : '+1');
  }

  /* Crossbar viz */
  if (data.conductance_mean !== undefined) {
    document.getElementById('puf-cond-mean').textContent =
      data.conductance_mean.toFixed(3);
    drawCrossbar(data.conductance_mean, data.conductance_std || 0.15);
  }

  /* Map */
  updateMap(data.gps_lat, data.gps_lon);

  /* Map coords */
  document.getElementById('map-coords').textContent =
    (data.gps_lat || 0).toFixed(6) + ', ' + (data.gps_lon || 0).toFixed(6);

  /* Attack card glow */
  document.getElementById('attack-card').style.borderColor =
    data.attack_detected ? 'rgba(255,23,68,0.4)' : 'rgba(255,255,255,0.06)';
}

/* ===== CROSSBAR VISUALIZATION ===== */
function drawCrossbar(mean, std) {
  const canvas = document.getElementById('crossbar-canvas');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  const w = canvas.width, h = canvas.height;
  const row = 4, col = 8;
  const cw = w / col, ch = h / row;

  ctx.clearRect(0, 0, w, h);

  for (let i = 0; i < row; i++) {
    for (let j = 0; j < col; j++) {
      const val = Math.max(0, Math.min(1, mean + (Math.random() - 0.5) * std * 2));
      const r = Math.floor(20 + val * 60);
      const g = Math.floor(100 + val * 80);
      const b = Math.floor(200 - val * 100);
      ctx.fillStyle = `rgb(${r},${g},${b})`;
      ctx.fillRect(j * cw + 1, i * ch + 1, cw - 2, ch - 2);
      ctx.fillStyle = 'rgba(255,255,255,0.08)';
      ctx.fillRect(j * cw, i * ch, 1, ch);
      ctx.fillRect(j * cw, i * ch, cw, 1);
    }
  }

  /* LIF neuron firing effect */
  const neuronDot = document.getElementById('neuron-dot');
  if (neuronDot) {
    const active = mean > 0.5;
    neuronDot.setAttribute('fill', active ? '#00c853' : '#1a2a40');
    if (active) {
      neuronDot.parentElement.parentElement.style.filter =
        'drop-shadow(0 0 6px rgba(0,200,83,0.5))';
    } else {
      neuronDot.parentElement.parentElement.style.filter = 'none';
    }
  }
}

/* ===== CRYPTO PANEL ===== */
function updateCryptoPanel(packet) {
  if (!packet) return;
  document.getElementById('c-caesar').textContent = 'Shift: ' + (packet.shift || '--');
  document.getElementById('c-vigenere').textContent = 'Key: ' + (packet.vigenere_key || '--');
  document.getElementById('c-spike').textContent = 'Pattern: NEURO-' + (packet.shift || '?');
  document.getElementById('c-chacha').textContent = 'IV: ' + (packet.iv ? packet.iv.substring(0, 10) + '...' : '--');

  const ct = packet.ciphertext || '';
  const display = ct.substring(0, 28);
  document.getElementById('c-result').textContent = display ? display + '...' : '---';
  document.getElementById('crypto-size').textContent =
    'Tamaño cifrado: ' + (packet.size || Math.ceil((ct.length || 0) / 2)) + ' bytes';
}

/* ===== AUTH ===== */
function updateAuth(status) {
  if (status === 'success') {
    const badge = document.getElementById('auth-badge');
    badge.textContent = 'AUTH OK';
    badge.className = 'badge badge-success';
    addLogEntry('\u2713', 'AUTH_OK', 'Autenticaci\u00f3n NeuroPUF exitosa');
    pufCrpCount++;
    document.getElementById('puf-crp-count').textContent = pufCrpCount;
  }
}

/* ===== LOG ===== */
function addLogEntry(step, action, detail, color) {
  const log = document.getElementById('log-entries');
  const entry = document.createElement('div');
  entry.className = 'log-entry';
  const c = color || (action.includes('AUTH') ? '#69f0ae'
    : action.includes('ENCRYPT') ? '#2979ff'
    : action.includes('ATTACK') ? '#ff1744'
    : action.includes('RESET') ? '#ff9100' : '#7a8ba8');
  entry.innerHTML =
    '<span class="log-step" style="color:' + c + '">' + step + '</span>' +
    '<span class="log-action">' + action + '</span>' +
    '<span class="log-detail">' + (detail || '') + '</span>';
  log.insertBefore(entry, log.firstChild);
  while (log.children.length > 100) log.removeChild(log.lastChild);
}

/* ===== MAP ===== */
function updateMap(lat, lon) {
  const canvas = document.getElementById('map-canvas');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  const rect = canvas.parentElement.getBoundingClientRect();
  canvas.width = canvas.clientWidth || rect.width || 400;
  canvas.height = canvas.clientHeight || rect.height || 280;

  const w = canvas.width, h = canvas.height;
  const centerLat = -16.409, centerLon = -71.537;
  const scale = 8000;
  const x = w / 2 + (lon - centerLon) * scale;
  const y = h / 2 - (lat - centerLat) * scale;

  dronePoints.push({ x, y });
  if (dronePoints.length > 150) dronePoints.shift();

  ctx.clearRect(0, 0, w, h);

  /* Grid */
  ctx.strokeStyle = 'rgba(255,255,255,0.02)';
  ctx.lineWidth = 0.5;
  for (let i = 0; i < w; i += 30) { ctx.beginPath(); ctx.moveTo(i, 0); ctx.lineTo(i, h); ctx.stroke(); }
  for (let i = 0; i < h; i += 30) { ctx.beginPath(); ctx.moveTo(0, i); ctx.lineTo(w, i); ctx.stroke(); }

  /* Trail with glow */
  if (dronePoints.length > 1) {
    const trail = ctx.createLinearGradient(0, 0, 0, h);
    trail.addColorStop(0, 'rgba(0,212,255,0)');
    for (let i = 0; i < dronePoints.length; i++) {
      const t = i / dronePoints.length;
      ctx.beginPath();
      ctx.arc(dronePoints[i].x, dronePoints[i].y, 1.5, 0, Math.PI * 2);
      ctx.fillStyle = `rgba(0,212,255,${t * 0.25})`;
      ctx.fill();
    }
    ctx.beginPath();
    ctx.strokeStyle = 'rgba(0,212,255,0.15)';
    ctx.lineWidth = 2;
    ctx.moveTo(dronePoints[0].x, dronePoints[0].y);
    for (let i = 1; i < dronePoints.length; i++) {
      ctx.lineTo(dronePoints[i].x, dronePoints[i].y);
    }
    ctx.stroke();
  }

  /* Drone glow */
  const px = dronePoints.length > 0 ? dronePoints[dronePoints.length - 1].x : x;
  const py = dronePoints.length > 0 ? dronePoints[dronePoints.length - 1].y : y;
  const g = ctx.createRadialGradient(px, py, 2, px, py, 24);
  g.addColorStop(0, 'rgba(0,212,255,0.5)');
  g.addColorStop(1, 'rgba(0,212,255,0)');
  ctx.fillStyle = g;
  ctx.beginPath(); ctx.arc(px, py, 24, 0, Math.PI * 2); ctx.fill();

  ctx.fillStyle = '#00d4ff';
  ctx.beginPath(); ctx.arc(px, py, 5, 0, Math.PI * 2);
  ctx.fill();
  ctx.shadowBlur = 12;
  ctx.shadowColor = 'rgba(0,212,255,0.4)';
  ctx.beginPath(); ctx.arc(px, py, 3, 0, Math.PI * 2);
  ctx.fill();
  ctx.shadowBlur = 0;

  /* Ring */
  ctx.strokeStyle = 'rgba(0,212,255,0.08)';
  ctx.lineWidth = 0.5;
  ctx.beginPath(); ctx.arc(px, py, 18, 0, Math.PI * 2); ctx.stroke();

  /* Base */
  ctx.strokeStyle = 'rgba(41,121,255,0.15)';
  ctx.setLineDash([3, 6]);
  ctx.beginPath(); ctx.arc(w / 2, h / 2, 30, 0, Math.PI * 2); ctx.stroke();
  ctx.setLineDash([]);

  ctx.fillStyle = '#7a8ba8';
  ctx.font = '9px monospace';
  ctx.fillText('BASE', w / 2 - 18, h / 2 + 42);
  ctx.fillStyle = 'rgba(0,212,255,0.6)';
  ctx.fillText('NEURO-DRONE', px + 14, py + 4);
}

/* ===== NEURO CHART ===== */
(function initChart() {
  const canvas = document.getElementById('chart-canvas');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  let data = Array(60).fill(0);
  let idx = 0;

  /* SSE also feeds real PUF conductance */
  window.__neuroChartFeed = function(val) {
    data[idx % 60] = val;
    idx++;
    if (idx > 60) data.shift();
    draw();
  };

  function draw() {
    const rect = canvas.parentElement.getBoundingClientRect();
    canvas.width = canvas.clientWidth || rect.width || 400;
    canvas.height = canvas.clientHeight || rect.height || 180;
    const w = canvas.width, h = canvas.height;

    ctx.clearRect(0, 0, w, h);

    /* Fill area */
    const gradient = ctx.createLinearGradient(0, h, 0, 0);
    gradient.addColorStop(0, 'rgba(0,212,255,0.02)');
    gradient.addColorStop(0.5, 'rgba(123,47,247,0.04)');
    gradient.addColorStop(1, 'rgba(0,200,83,0.03)');
    ctx.fillStyle = gradient;

    if (data.length > 1) {
      ctx.beginPath();
      ctx.moveTo(0, h);
      data.forEach((v, i) => {
        const x = (i / (data.length - 1)) * w;
        const y = h - ((v / 1.2) * h);
        ctx.lineTo(x, y);
      });
      ctx.lineTo(w, h);
      ctx.closePath();
      ctx.fill();

      ctx.beginPath();
      ctx.strokeStyle = '#00d4ff';
      ctx.lineWidth = 1.5;
      data.forEach((v, i) => {
        const x = (i / (data.length - 1)) * w;
        const y = h - ((v / 1.2) * h);
        if (i === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      });
      ctx.stroke();

      /* Threshold line */
      ctx.strokeStyle = 'rgba(255,23,68,0.2)';
      ctx.lineWidth = 0.5;
      ctx.setLineDash([3, 4]);
      const thresh = h - (0.5 / 1.2 * h);
      ctx.beginPath();
      ctx.moveTo(0, thresh);
      ctx.lineTo(w, thresh);
      ctx.stroke();
      ctx.setLineDash([]);
      ctx.fillStyle = 'rgba(255,23,68,0.3)';
      ctx.font = '8px monospace';
      ctx.fillText('STDP threshold', 4, thresh - 3);
    }

    /* Label */
    ctx.fillStyle = 'rgba(255,255,255,0.15)';
    ctx.font = '10px monospace';
    ctx.fillText('conductancia media', w - 130, 14);
  }
  draw();
  window.addEventListener('resize', draw);
})();

/* ===== ATTACK ===== */
function simulateAttack(seed) {
  const resultEl = document.getElementById('attack-result');
  const logEl = document.getElementById('attack-log');

  resultEl.className = 'attack-result';
  resultEl.style.display = 'none';

  fetch('/api/attack/' + seed)
    .then(r => r.json())
    .then(data => {
      if (data.detected) {
        resultEl.className = 'attack-result success';
        resultEl.style.display = 'block';
        resultEl.innerHTML =
          '&#9989; ATAQUE DETECTADO: Dron falso (seed=' + data.fake_seed +
          ') respondi&oacute; ' + data.fake_response + ' vs esperado ' + data.real_response;
        addLogEntry('!!', 'ATTACK', 'Falso drone detectado (seed=' + seed + ')', '#ff1744');
      } else {
        resultEl.className = 'attack-result danger';
        resultEl.style.display = 'block';
        resultEl.innerHTML = '&#9888; ATAQUE NO DETECTADO (coincidencia fortuita)';
        addLogEntry('?!', 'ATTACK', 'Falso drone NO detectado (seed=' + seed + ')', '#ff9100');
      }
      attackHistory.push(data);
      const detected = attackHistory.filter(a => a.detected).length;
      logEl.textContent =
        'Historial: ' + attackHistory.length + ' ataques, ' + detected + ' detectados (' +
        (attackHistory.length ? Math.round(detected / attackHistory.length * 100) : 0) + '%)';
      document.getElementById('s-attacks').textContent = attackHistory.length;
    });
}

function resetDrone() {
  fetch('/api/reset')
    .then(r => r.json())
    .then(data => {
      if (data.status === 'reset_ok') {
        dronePoints = [];
        attackHistory = [];
        document.getElementById('s-attacks').textContent = '0';
        document.getElementById('attack-result').style.display = 'none';
        document.getElementById('attack-log').textContent = '';
        document.getElementById('log-entries').innerHTML = '';
        document.getElementById('s-packets').textContent = '0';
        document.getElementById('s-throughput').textContent = '--';
        startTime = Date.now();

        const canvas = document.getElementById('map-canvas');
        if (canvas) canvas.getContext('2d').clearRect(0, 0, canvas.width, canvas.height);
        addLogEntry('RST', 'RESET', 'Drone reiniciado', '#ff9100');
      }
    });
}

/* ===== START ===== */
connectSSE();

window.addEventListener('resize', function() {
  const mc = document.getElementById('map-canvas');
  if (mc) { mc.width = mc.clientWidth; mc.height = mc.clientHeight; }
  const cc = document.getElementById('chart-canvas');
  if (cc) { cc.width = cc.clientWidth; cc.height = cc.clientHeight; }
});
