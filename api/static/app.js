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
let _pendingUpdate = null;
let _animFrame = null;

function connectSSE() {
  if (eventSource) eventSource.close();
  eventSource = new EventSource('/stream');

  eventSource.onmessage = function(e) {
    if (e.data === '') return;
    try {
      const msg = JSON.parse(e.data);
      if (msg.type === 'ping') return;
      if (msg.type === 'status') { _pendingUpdate = msg.data; return; }
      handleEvent(msg);
    } catch (err) {}
  };

  eventSource.onerror = function() {
    setTimeout(connectSSE, 2000);
  };
}

/* Batch all DOM updates into a single rAF frame */
function _renderFrame() {
  if (_pendingUpdate) {
    const d = _pendingUpdate;
    _pendingUpdate = null;
    updateTelemetry(d);
    if (d.crypto) {
      updateCryptoPanel(d.crypto);
      addLogEntry('--', 'ENCRYPT', 'Cifrado ' + (d.crypto.size || 0) + ' B');
    }
  }
  _animFrame = requestAnimationFrame(_renderFrame);
}
_animFrame = requestAnimationFrame(_renderFrame);

function handleEvent(msg) {
  switch (msg.type) {
    case 'status':
      updateTelemetry(msg.data);
      if (msg.data.crypto) {
        updateCryptoPanel(msg.data.crypto);
        addLogEntry('--', 'ENCRYPT', 'Cifrado ' + (msg.data.crypto.size || 0) + ' B');
      }
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

  const setText = (id, val) => { const el = document.getElementById(id); if (el) el.textContent = val; };
  const setHTML = (id, val) => { const el = document.getElementById(id); if (el) el.innerHTML = val; };

  setText('t-gps', (data.gps_lat || 0).toFixed(6) + ', ' + (data.gps_lon || 0).toFixed(6));
  setHTML('t-alt', (data.altitude || 0).toFixed(1) + ' <span class="unit">m</span>');
  setHTML('t-speed', (data.speed || 0).toFixed(1) + ' <span class="unit">m/s</span>');
  setHTML('t-heading', (data.heading || 0).toFixed(0) + '&deg;');

  const bat = Math.max(0, data.battery || 0);
  const fill = document.getElementById('battery-fill');
  if (fill) {
    fill.style.width = bat + '%';
    fill.style.background = bat < 20
      ? 'linear-gradient(90deg, #ff1744, #ff5252)'
      : bat < 50
        ? 'linear-gradient(90deg, #ff9100, #ffab40)'
        : 'linear-gradient(90deg, #00c853, #69f0ae)';
  }
  setText('battery-text', bat.toFixed(0) + '%');

  const sig = Math.min(100, Math.max(0, data.signal_strength || 50));
  const sigBars = document.querySelectorAll('.signal-bars span');
  const activeBars = Math.ceil(sig / 20);
  sigBars.forEach((bar, i) => {
    const h = parseInt(bar.dataset.h);
    bar.style.height = (i < activeBars ? h : 2) + 'px';
    bar.style.background = i < activeBars
      ? (i < 2 ? '#ff9100' : i < 4 ? '#00c853' : '#2979ff')
      : 'rgba(255,255,255,0.06)';
  });

  setText('t-status', bat > 20 ? 'EN RUTA' : 'REGRESANDO');
  const statusEl = document.getElementById('t-status');
  if (statusEl) statusEl.style.color = bat > 20 ? '#69f0ae' : '#ff9100';

  setText('s-packets', packetsSent);
  setText('s-battery', bat.toFixed(0) + '%');

  const elapsed = Math.floor((Date.now() - startTime) / 1000);
  const mins = Math.floor(elapsed / 60);
  const secs = elapsed % 60;
  setText('s-age', mins + 'm ' + secs + 's');
  if (elapsed > 0) setText('s-throughput', (packetsSent / elapsed).toFixed(1) + '/s');

  /* Auth badge */
  const authBadge = document.getElementById('auth-badge');
  if (authBadge) {
    if (data.authenticated) {
      authBadge.textContent = 'AUTH OK';
      authBadge.className = 'badge badge-success';
    } else {
      authBadge.textContent = 'NO AUTH';
      authBadge.className = 'badge badge-danger';
    }
  }

  /* PUF signals */
  if (data.challenge) {
    const bits = data.challenge.substring(0, 5);
    setText('puf-challenge', bits.length >= 5 ? bits + '...' : bits);

    const spikeBars = document.querySelectorAll('.puf-voltage-bars div');
    if (data.spike_levels) {
      spikeBars.forEach((bar, i) => {
        if (i < data.spike_levels.length) {
          bar.style.height = (data.spike_levels[i] * 100) + '%';
        }
      });
    }
  }
  /* STDP params from server */
  if (data.stdp_lr !== undefined) setText('puf-stdp-lr', data.stdp_lr.toFixed(3));
  if (data.t_window !== undefined) setText('puf-t-window', data.t_window);

  /* Membrane levels for LIF neurons */
  if (data.membrane_levels) {
    for (let i = 0; i < 4 && i < data.membrane_levels.length; i++) {
      const memBar = document.getElementById('lif-mem-' + i);
      if (memBar) memBar.style.height = (data.membrane_levels[i] * 100) + '%';
    }
  }

  if (data.response !== undefined) {
    const r = Number(data.response);
    const bits = r.toString(2).padStart(4, '0');
    setText('puf-response', r);
    setText('puf-response-binary', bits);

    for (let i = 0; i < 4; i++) {
      const bitVal = (r >> (3 - i)) & 1;
      const dot = document.getElementById('lif-dot-' + i);
      const label = document.getElementById('lif-bit-' + i);
      if (dot) dot.className = 'lif-dot' + (bitVal ? ' active' : '');
      if (label) label.textContent = bitVal;
    }
  }

  /* Crossbar viz */
  if (data.conductance_matrix) {
    setText('puf-cond-mean', (data.conductance_mean || 0).toFixed(3));
    setText('puf-cond-std', (data.conductance_std || 0).toFixed(3));
    drawCrossbar(data.conductance_matrix, data.response);

    /* Feed real conductance mean to chart */
    if (window.__neuroChartFeed && data.conductance_mean !== undefined) {
      window.__neuroChartFeed(data.conductance_mean);
    }
  }

  /* Map */
  updateMap(data.gps_lat, data.gps_lon);
  setText('map-coords', (data.gps_lat || 0).toFixed(6) + ', ' + (data.gps_lon || 0).toFixed(6));

  /* Attack card glow */
  const attackCard = document.getElementById('attack-card');
  if (attackCard) {
    attackCard.style.borderColor =
      data.attack_detected ? 'rgba(255,23,68,0.4)' : 'rgba(255,255,255,0.06)';
  }
}

/* ===== CROSSBAR VISUALIZATION ===== */
function drawCrossbar(matrix, response) {
  const canvas = document.getElementById('crossbar-canvas');
  if (!canvas || !matrix || !matrix.length) return;
  const ctx = canvas.getContext('2d');
  const w = canvas.width, h = canvas.height;
  const rows = matrix.length;
  const cols = matrix[0].length;
  const cw = w / cols, ch = h / rows;

  ctx.clearRect(0, 0, w, h);

  let gmin = Infinity, gmax = -Infinity;
  for (let i = 0; i < rows; i++)
    for (let j = 0; j < cols; j++) {
      const v = matrix[i][j];
      if (v < gmin) gmin = v;
      if (v > gmax) gmax = v;
    }
  const range = gmax - gmin || 1;

  for (let i = 0; i < rows; i++) {
    for (let j = 0; j < cols; j++) {
      const norm = (matrix[i][j] - gmin) / range;
      const r = Math.floor(20 + norm * 235);
      const g = Math.floor(80 + norm * 175);
      const b = Math.floor(200 - norm * 55);
      ctx.fillStyle = `rgb(${r},${g},${b})`;
      ctx.fillRect(j * cw, i * ch, Math.ceil(cw), Math.ceil(ch));
    }
  }

  ctx.strokeStyle = 'rgba(255,255,255,0.04)';
  ctx.lineWidth = 0.5;
  for (let i = 0; i <= rows; i++) {
    ctx.beginPath(); ctx.moveTo(0, i * ch); ctx.lineTo(w, i * ch); ctx.stroke();
  }
  for (let j = 0; j <= cols; j++) {
    ctx.beginPath(); ctx.moveTo(j * cw, 0); ctx.lineTo(j * cw, h); ctx.stroke();
  }
}

/* ===== CRYPTO PANEL ===== */
function updateCryptoPanel(packet) {
  if (!packet) return;
  const s = (id, val) => { const el = document.getElementById(id); if (el) el.textContent = val; };
  s('c-cbc', 'IV: ' + (packet.iv_cbc ? packet.iv_cbc.substring(0, 10) + '...' : '--'));
  s('c-ctr', 'Nonce: ' + (packet.nonce_ctr ? packet.nonce_ctr.substring(0, 10) + '...' : '--'));
  s('c-spike', 'Patr\u00f3n: ' + (packet.spike_permutation || 'PUF'));
  s('c-chacha', 'IV: ' + (packet.chacha_iv ? packet.chacha_iv.substring(0, 10) + '...' : '--'));

  const ct = packet.ciphertext || '';
  const display = ct.substring(0, 28);
  s('c-result', display ? display + '...' : '---');
  const sz = document.getElementById('crypto-size');
  if (sz) sz.textContent = 'Tama\u00f1o cifrado: ' + (packet.size || Math.ceil((ct.length || 0) / 2)) + ' bytes';
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
let _mapW = 0, _mapH = 0;
function _resizeMap(canvas) {
  const pw = canvas.parentElement.clientWidth;
  const ph = canvas.parentElement.clientHeight;
  if (pw !== _mapW || ph !== _mapH) {
    _mapW = canvas.width = pw || 400;
    _mapH = canvas.height = ph || 280;
  }
}

function updateMap(lat, lon) {
  const canvas = document.getElementById('map-canvas');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  _resizeMap(canvas);

  const w = _mapW, h = _mapH;
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
    const pw = canvas.parentElement.clientWidth;
    const ph = canvas.parentElement.clientHeight;
    canvas.width = pw || 400;
    canvas.height = ph || 180;
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
        if (data.challenge) resultEl.innerHTML += ' <span class="unit">challenge: ' + data.challenge + '</span>';
        addLogEntry('!!', 'ATTACK', 'Falso drone detectado (seed=' + seed + ')', '#ff1744');
      } else {
        resultEl.className = 'attack-result danger';
        resultEl.style.display = 'block';
        resultEl.innerHTML = '&#9888; ATAQUE NO DETECTADO (coincidencia fortuita)';
        if (data.challenge) resultEl.innerHTML += ' <span class="unit">challenge: ' + data.challenge + '</span>';
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
  _mapW = 0; _mapH = 0;
});
