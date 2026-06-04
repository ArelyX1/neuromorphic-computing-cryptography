import React, { useState, useEffect, useRef, useCallback } from 'react';

const API = '';

function useSSE(onEvent) {
  useEffect(() => {
    let es = new EventSource(API + '/stream');
    es.onmessage = e => {
      if (!e.data) return;
      try { const m = JSON.parse(e.data); if (m.type !== 'ping') onEvent(m); } catch (_) {}
    };
    es.onerror = () => { es.close(); setTimeout(() => { es = new EventSource(API + '/stream'); }, 2000); };
    return () => es.close();
  }, [onEvent]);
}

export default function App() {
  const [status, setStatus] = useState({
    authenticated: false, gps_lat: -16.409, gps_lon: -71.537,
    altitude: 100, speed: 15, battery: 100, heading: 0,
    signal_strength: 70, packets_sent: 0, challenge: '', response: '',
    attack_detected: false, spike_levels: [0.5,0.5,0.5,0.5,0.5],
    conductance_mean: 0.5, conductance_std: 0.15,
    membrane_levels: [0.5,0.5,0.5,0.5], stdp_lr: 0.005, t_window: 10
  });
  const [crypto, setCrypto] = useState({
    ciphertext: '', iv: '', nonce_ctr: '', iv_cbc: '',
    chacha_iv: '', drone_id: '', size: 0, spike_permutation: ''
  });
  const [attackResult, setAttackResult] = useState(null);
  const [attackCount, setAttackCount] = useState(0);
  const [logs, setLogs] = useState([]);
  const [packets, setPackets] = useState(0);
  const startTime = useRef(Date.now());
  const logEndRef = useRef(null);

  const addLog = useCallback((severity, action, detail) => {
    const entry = {
      id: Date.now() + Math.random(),
      ts: new Date().toLocaleTimeString('es-PE', { hour12: false }),
      severity, action, detail
    };
    setLogs(prev => [...prev, entry].slice(-200));
  }, []);

  useEffect(() => {
    if (logEndRef.current) {
      logEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [logs]);

  const handleEvent = useCallback((msg) => {
    if (msg.type === 'status') {
      setStatus(msg.data);
      if (msg.data.crypto) {
        setCrypto(msg.data.crypto);
        addLog('INFO', 'CIPHER', `AES-CBC+AES-CTR+Spike+ChaCha20 — ${msg.data.crypto.size || 0} B`);
      }
      if (msg.data.authenticated) setPackets(p => msg.data.packets_sent || p);
    } else if (msg.type === 'auth') {
      if (msg.status === 'success') addLog('OK', 'AUTH', 'NeuroPUF authentication successful');
    } else if (msg.type === 'attack') {
      setAttackResult(msg);
      setAttackCount(c => c + 1);
      addLog('WARN', 'ATTACK', `seed=${msg.seed} ${msg.detected ? 'DETECTED' : 'NOT DETECTED'}`);
    } else if (msg.type === 'error') {
      addLog('ERROR', 'SERVER', msg.message);
    }
  }, [addLog]);

  useSSE(handleEvent);

  const simulateAttack = async (seed) => {
    setAttackResult(null);
    const r = await fetch(API + '/api/attack/' + seed).then(r => r.json());
    setAttackResult(r);
    setAttackCount(c => c + 1);
  };

  const resetDrone = async () => {
    await fetch(API + '/api/reset');
    setAttackResult(null);
    setLogs([]);
    setPackets(0);
    startTime.current = Date.now();
    addLog('INFO', 'RESET', 'System reset requested');
  };

  const elapsed = Math.floor((Date.now() - startTime.current) / 1000);
  const tps = elapsed > 0 ? (packets / elapsed).toFixed(1) : '--';

  return (
    <div className="container">
      <header>
        <div className="logo">
          <svg className="logo-icon" viewBox="0 0 32 32" width="24" height="24">
            <circle cx="16" cy="16" r="14" fill="none" stroke="#00d4ff" strokeWidth="1.5" opacity="0.3"/>
            <circle cx="16" cy="16" r="8" fill="none" stroke="#00d4ff" strokeWidth="1" opacity="0.5"/>
            <circle cx="16" cy="16" r="3" fill="#00d4ff"/>
          </svg>
          <div>
            <h1>NEUROPUF DRONE CONSOLE</h1>
            <div className="subtitle">AES-256-CBC &middot; AES-256-CTR &middot; Spike Permutation &middot; ChaCha20 &middot; Memristor Crossbar</div>
          </div>
        </div>
        <div className="header-status">
          <span className={`badge ${status.authenticated ? 'badge-success' : 'badge-danger'}`}>
            {status.authenticated ? 'AUTHENTICATED' : 'UNAUTHENTICATED'}
          </span>
          <span className="badge badge-neuro">STDP / LIF</span>
        </div>
      </header>

      <div className="stats">
        <Stat label="PACKETS" value={packets} />
        <Stat label="BATTERY" value={status.battery.toFixed(0) + '%'} />
        <Stat label="THROUGHPUT" value={tps + '/s'} />
        <Stat label="ATTACKS" value={attackCount} />
        <Stat label="UPTIME" value={`${Math.floor(elapsed/60)}m ${elapsed%60}s`} />
      </div>

      <div className="grid">
        <TelemetryCard status={status} />
        <PUFCard status={status} />
        <CryptoCard crypto={crypto} />
        <MapCard status={status} />
        <AttackCard onAttack={simulateAttack} onReset={resetDrone} result={attackResult} count={attackCount} />
        <LogCard logs={logs} logEndRef={logEndRef} />
      </div>

      <footer>NeuroPUF v3.0 &mdash; Hexagonal Architecture + GraphQL &mdash; 2026</footer>
    </div>
  );
}

/* ── Stat ─────────────────────────────────────── */
function Stat({ label, value }) {
  return (
    <div className="stat-card">
      <div className="stat-value">{value}</div>
      <div className="stat-label">{label}</div>
    </div>
  );
}

/* ── Telemetry ────────────────────────────────── */
function TelemetryCard({ status }) {
  const bat = Math.max(0, status.battery);
  const sig = Math.min(100, Math.max(0, status.signal_strength));
  const activeBars = Math.ceil(sig / 20);

  return (
    <div className="card">
      <div className="card-h">TELEMETRY <span className="live-dot" /></div>
      <div className="card-b">
        <div className="t-grid">
          <TItem label="Drone ID" value="NEURO-DRON-01" />
          <TItem label="GPS" value={`${status.gps_lat.toFixed(4)}, ${status.gps_lon.toFixed(4)}`} />
          <TItem label="Altitude" value={`${status.altitude.toFixed(1)} m`} />
          <TItem label="Speed" value={`${status.speed.toFixed(1)} m/s`} />
          <TItem label="Heading" value={`${status.heading.toFixed(0)} deg`} />
          <TItem label="Battery" value={
            <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <div className="battery">
                <div className="battery-fill" style={{ width: bat + '%' }} />
              </div>
              {bat.toFixed(0)}%
            </span>
          } />
          <TItem label="Signal" value={
            <div className="signal">
              {[4,8,12,16,20].map((h,i) => (
                <span key={i} style={{
                  height: i < activeBars ? h + 'px' : '2px',
                  background: i < activeBars
                    ? (i < 2 ? '#ff9100' : i < 3 ? '#ffab00' : '#00c853')
                    : 'rgba(255,255,255,0.06)'
                }} />
              ))}
            </div>
          } />
          <TItem label="Status" value={
            <span style={{ color: bat > 20 ? '#69f0ae' : '#ff9100' }}>
              {bat > 20 ? 'EN ROUTE' : 'RETURNING'}
            </span>
          } />
        </div>
      </div>
    </div>
  );
}

function TItem({ label, value }) {
  return (
    <div className="t-item">
      <div className="t-lbl">{label}</div>
      <div className="t-val">{value}</div>
    </div>
  );
}

/* ── PUF Core ─────────────────────────────────── */
function PUFCard({ status }) {
  const condMean = status.conductance_mean || 0.5;
  const condStd = status.conductance_std || 0.15;
  const bars = (status.spike_levels || []).map(v => Math.round(v * 100));
  const matrix = status.conductance_matrix || null;
  const r = status.response !== undefined && status.response !== null ? Number(status.response) : null;
  const bits = r !== null ? r.toString(2).padStart(4, '0').split('').map(Number) : [0,0,0,0];

  const canvasRef = useRef(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    const w = canvas.width, h = canvas.height;

    ctx.clearRect(0, 0, w, h);

    if (matrix && matrix.length) {
      const rows = matrix.length;
      const cols = matrix[0].length;
      const cw = w / cols, ch = h / rows;

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
          const red = Math.floor(20 + norm * 235);
          const green = Math.floor(80 + norm * 175);
          const blue = Math.floor(200 - norm * 55);
          ctx.fillStyle = `rgb(${red},${green},${blue})`;
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
  }, [matrix]);

  return (
    <div className="card">
      <div className="card-h">NEUROMORPHIC PUF CORE</div>
      <div className="card-b">
        <div style={{ display: 'flex', gap: 12, marginBottom: 14, alignItems: 'center' }}>
          <div style={{ flex: '0.7', textAlign: 'center' }}>
            <div className="t-lbl">Spike Encoder</div>
            <div className="puf-bars">
              {bars.map((h,i) => <div key={i} style={{ height: h + '%' }} />)}
            </div>
            <div className="t-lbl" style={{ marginTop: 4 }}>challenge</div>
            <div className="puf-val">{(status.challenge || '').substring(0, 16) || '--'}</div>
          </div>
          <div className="puf-arrow">&rarr;</div>
          <div style={{ flex: '1', textAlign: 'center' }}>
            <div className="t-lbl">4 &times; LIF Neurons</div>
            <div style={{ display: 'flex', justifyContent: 'center', gap: 10, margin: '8px 0' }}>
              {bits.map((bit, i) => (
                <div key={i} style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 3 }}>
                  <div style={{
                    width: 14, height: 14, borderRadius: '50%',
                    background: bit ? '#00c853' : '#1a2a40',
                    border: '1px solid rgba(255,255,255,0.08)',
                    boxShadow: bit ? '0 0 8px rgba(0,200,83,0.6)' : 'none',
                    transition: 'background 0.3s, box-shadow 0.3s'
                  }} />
                  <span style={{ fontSize: 9, color: 'var(--text-secondary)', fontFamily: "'JetBrains Mono',monospace" }}>{bit}</span>
                </div>
              ))}
            </div>
          </div>
          <div className="puf-arrow">&rarr;</div>
          <div style={{ flex: '0.7', textAlign: 'center' }}>
            <div className="t-lbl">PUF Response</div>
            <div className="puf-val" style={{ fontSize: 16 }}>{r !== null ? r : '--'}</div>
            <div className="t-lbl" style={{ marginTop: 2 }}>{r !== null ? bits.join('') : '----'}</div>
          </div>
        </div>
        <div style={{ width: '100%', marginBottom: 10 }}>
          <canvas ref={canvasRef} width="640" height="80"
            style={{ width: '100%', height: 'auto', border: '1px solid rgba(123,47,247,0.2)', borderRadius: 4, display: 'block' }} />
        </div>
        <div className="puf-stats">
          <div className="puf-stat">
            <span className="stat-label">Conductance &mu;</span>
            <span className="stat-value">{condMean.toFixed(3)}</span>
            <span className="stat-unit">S</span>
          </div>
          <div className="puf-stat">
            <span className="stat-label">&sigma; (deviation)</span>
            <span className="stat-value">{condStd.toFixed(3)}</span>
            <span className="stat-unit">S</span>
          </div>
          <div className="puf-stat">
            <span className="stat-label">STDP rate</span>
            <span className="stat-value">{status.stdp_lr !== undefined ? status.stdp_lr.toFixed(3) : '--'}</span>
          </div>
          <div className="puf-stat">
            <span className="stat-label">Time window</span>
            <span className="stat-value">{status.t_window !== undefined ? status.t_window : '--'}</span>
            <span className="stat-unit">steps</span>
          </div>
        </div>
      </div>
    </div>
  );
}

/* ── Crypto Layers ────────────────────────────── */
function CryptoCard({ crypto }) {
  const step = (n, name, val) => (
    <React.Fragment key={n}>
      <div className="layer">
        <span className="layer-num">{String(n+1).padStart(2, '0')}</span>
        <span className="layer-name">{name}</span>
        <span className="layer-val">{val || '--'}</span>
      </div>
      {n < 4 && <div className="layer-arrow">&darr;</div>}
    </React.Fragment>
  );

  return (
    <div className="card">
      <div className="card-h">CIPHER PIPELINE</div>
      <div className="card-b">
        {step(0, 'AES-256-CBC', crypto.iv_cbc ? `IV ${crypto.iv_cbc.substring(0, 8)}...` : '--')}
        {step(1, 'AES-256-CTR', crypto.nonce_ctr ? `Nonce ${crypto.nonce_ctr.substring(0, 8)}...` : '--')}
        {step(2, 'Spike Permutation', crypto.spike_permutation || 'PUF')}
        {step(3, 'ChaCha20', crypto.chacha_iv ? `IV ${crypto.chacha_iv.substring(0, 8)}...` : '--')}
        {step(4, 'CIPHERTEXT', crypto.ciphertext ? crypto.ciphertext.substring(0, 16) + '...' : '---')}
        <div className="t-lbl" style={{ textAlign: 'center', marginTop: 8, padding: '4px 0' }}>
          encrypted size: {crypto.size || 0} bytes
        </div>
      </div>
    </div>
  );
}

/* ── Map ──────────────────────────────────────── */
function MapCard({ status }) {
  const canvasRef = useRef(null);
  const points = useRef([]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    const rect = canvas.parentElement.getBoundingClientRect();
    canvas.width = rect.width;
    canvas.height = rect.height;

    const w = canvas.width, h = canvas.height;
    const cx = w / 2, cy = h / 2;
    const scale = 8000;
    const x = cx + (status.gps_lon - (-71.537)) * scale;
    const y = cy - (status.gps_lat - (-16.409)) * scale;

    points.current.push({ x, y });
    if (points.current.length > 200) points.current.shift();

    ctx.clearRect(0, 0, w, h);

    ctx.strokeStyle = 'rgba(255,255,255,0.02)';
    ctx.lineWidth = 0.5;
    for (let i = 0; i < w; i += 30) { ctx.beginPath(); ctx.moveTo(i, 0); ctx.lineTo(i, h); ctx.stroke(); }
    for (let i = 0; i < h; i += 30) { ctx.beginPath(); ctx.moveTo(0, i); ctx.lineTo(w, i); ctx.stroke(); }

    if (points.current.length > 1) {
      for (let i = 0; i < points.current.length; i++) {
        const t = i / points.current.length;
        ctx.beginPath();
        ctx.arc(points.current[i].x, points.current[i].y, 1.8, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(0, 212, 255, ${0.08 + t * 0.2})`;
        ctx.fill();
      }
    }

    const last = points.current[points.current.length - 1] || { x, y };
    const g = ctx.createRadialGradient(last.x, last.y, 2, last.x, last.y, 28);
    g.addColorStop(0, 'rgba(0, 212, 255, 0.55)');
    g.addColorStop(1, 'rgba(0, 212, 255, 0)');
    ctx.fillStyle = g;
    ctx.beginPath(); ctx.arc(last.x, last.y, 28, 0, Math.PI * 2); ctx.fill();

    ctx.fillStyle = '#00d4ff';
    ctx.beginPath(); ctx.arc(last.x, last.y, 4, 0, Math.PI * 2); ctx.fill();

    ctx.strokeStyle = 'rgba(41, 121, 255, 0.15)';
    ctx.setLineDash([3, 6]);
    ctx.beginPath(); ctx.arc(cx, cy, 30, 0, Math.PI * 2); ctx.stroke();
    ctx.setLineDash([]);
    ctx.fillStyle = '#7a8ba8';
    ctx.font = '9px monospace';
    ctx.fillText('BASE', cx - 15, cy + 38);
    ctx.fillStyle = 'rgba(0, 212, 255, 0.6)';
    ctx.fillText('NEURO-DRON', last.x + 12, last.y + 3);
  }, [status.gps_lat, status.gps_lon]);

  return (
    <div className="card">
      <div className="card-h">FLIGHT MAP <span className="badge badge-neuro" style={{ marginLeft: 'auto' }}>LIVE</span></div>
      <div style={{ padding: 0, height: 200, position: 'relative' }}>
        <canvas ref={canvasRef} style={{ width: '100%', height: '100%', display: 'block' }} />
        <div className="coords-overlay">
          {status.gps_lat.toFixed(4)}, {status.gps_lon.toFixed(4)}
        </div>
      </div>
    </div>
  );
}

/* ── Attack ───────────────────────────────────── */
function AttackCard({ onAttack, onReset, result, count }) {
  return (
    <div className="card">
      <div className="card-h">ATTACK SIMULATOR</div>
      <div className="card-b">
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 10 }}>
          <button className="btn btn-attack" onClick={() => onAttack(111)}>spoof 111</button>
          <button className="btn btn-attack" onClick={() => onAttack(222)}>spoof 222</button>
          <button className="btn btn-attack" onClick={() => onAttack(333)}>spoof 333</button>
          <button className="btn btn-reset" onClick={onReset}>reset</button>
        </div>
        {result && (
          <div className={`attack-result ${result.detected ? 'success' : 'danger'}`}>
            {result.detected
              ? `DETECTED — seed=${result.fake_seed} fake_resp=${result.fake_response} real_resp=${result.real_response}`
              : `NOT DETECTED — seed=${result.fake_seed}`}
            {result.challenge && <div className="t-lbl" style={{marginTop:4}}>challenge: {result.challenge}</div>}
          </div>
        )}
        {!result && (
          <div className="t-lbl" style={{ padding: '4px 0' }}>
            spoofed drone count: {count}
          </div>
        )}
      </div>
    </div>
  );
}

/* ── Log ──────────────────────────────────────── */
function LogCard({ logs, logEndRef }) {
  const severityColor = (s) => {
    if (s === 'ERROR') return '#ff5252';
    if (s === 'WARN') return '#ffab40';
    if (s === 'OK') return '#69f0ae';
    return '#82b1ff';
  };

  return (
    <div className="card">
      <div className="card-h">EVENT LOG</div>
      <div className="log">
        {logs.length === 0 && (
          <div className="t-lbl" style={{ padding: 8 }}>no events yet</div>
        )}
        {logs.map(l => (
          <div key={l.id} className="log-entry">
            <span style={{ color: 'var(--text-secondary)', minWidth: 50 }}>{l.ts}</span>
            <span style={{ color: severityColor(l.severity), minWidth: 50, fontWeight: 700 }}>{l.severity}</span>
            <span style={{ color: '#2979ff', fontWeight: 600, minWidth: 60 }}>{l.action}</span>
            <span style={{ color: 'var(--text-secondary)', flex: 1 }}>{l.detail}</span>
          </div>
        ))}
        <div ref={logEndRef} />
      </div>
    </div>
  );
}
