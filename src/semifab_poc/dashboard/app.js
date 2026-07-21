/* ═══════════════════ app.js — PowerUPCMP Dashboard ═══════════════════ */

const state = { stream: null, data: { truth_rows: [], predictions: [] }, held: false };
const $ = (id) => document.getElementById(id);

const descriptions = {
  PUMP_TRIP:              'UPW pump trip — the pump loses power and water pressure collapses, threatening pad glazing and wafer damage.',
  VOLTAGE_SAG:            'Grid voltage sag — a brownout starves the VFD, reducing motor speed and water flow.',
  VALVE_RESTRICTION:      'UPW valve restriction — a partially closed valve reduces hydraulic support to the CMP tool.',
  PRESSURE_SENSOR_FAULT:  'Pressure sensor bias — a degraded sensor injects a constant offset into readings.',
  GRID_INTERRUPTION:      'Short grid interruption — a brief power cut tests UPS transfer and recovery.',
  NORMAL:                 'Normal operation — healthy baseline. MRR should plateau cleanly and the AI stays quiet.'
};

/* ─── Preset defaults for physics parameters ─── */
const presetDefaults = {
  PUMP_TRIP:              { grid: '1.0',  valve: '1.0',  bias: '0' },
  VOLTAGE_SAG:            { grid: '0.75', valve: '1.0',  bias: '0' },
  VALVE_RESTRICTION:      { grid: '1.0',  valve: '0.25', bias: '0' },
  PRESSURE_SENSOR_FAULT:  { grid: '1.0',  valve: '1.0',  bias: '-100000' },
  GRID_INTERRUPTION:      { grid: '1.0',  valve: '1.0',  bias: '0' },
  NORMAL:                 { grid: '1.0',  valve: '1.0',  bias: '0' }
};

/* ─── Boot ─── */
document.addEventListener('DOMContentLoaded', () => {
  $('scenario-preset').addEventListener('change', (e) => {
    $('scenario-description').textContent = descriptions[e.target.value] || '';
    const d = presetDefaults[e.target.value] || presetDefaults.NORMAL;
    $('sim-grid-voltage').value = d.grid;
    $('sim-valve-pos').value    = d.valve;
    $('sim-sensor-bias').value  = d.bias;
  });

  $('advanced-toggle').addEventListener('click', () => {
    const box = $('advanced-parameters');
    const open = box.hidden;
    box.hidden = !open;
    $('advanced-toggle').textContent = open ? '−' : '+';
    $('advanced-toggle').setAttribute('aria-expanded', String(open));
  });

  $('stream-btn').addEventListener('click', () => {
    if (!$('trace-selector').value) return setConnection('Select an artifact first', true);
    startStream(
      `/api/stream/${encodeURIComponent($('trace-selector').value)}`,
      'REPLAY',
      $('trace-selector').value
    );
  });

  $('live-sim-btn').addEventListener('click', runScenario);
  $('stop-sim-btn').addEventListener('click', stopStream);

  fetch('/api/traces')
    .then(r => r.json())
    .then(payload => {
      $('trace-selector').innerHTML = '<option value="">Select a validated artifact</option>';
      payload.traces.forEach(name => {
        const opt = document.createElement('option');
        opt.value = name;
        opt.textContent = name.replace('.json', '').replaceAll('-', ' ');
        $('trace-selector').appendChild(opt);
      });
    })
    .catch(() => {
      $('trace-selector').innerHTML = '<option value="">Artifacts unavailable</option>';
    });

  renderDashboard(state.data);
});

/* ─── Run a live scenario ─── */
function runScenario() {
  const query = new URLSearchParams({
    family:      $('scenario-preset').value,
    controller:  $('sim-controller').value,
    seed:        $('sim-seed').value,
    duration:    $('sim-duration').value,
    grid_volt:   $('sim-grid-voltage').value,
    valve_pos:   $('sim-valve-pos').value,
    sensor_bias: $('sim-sensor-bias').value,
    ev_start:    $('sim-event-start').value,
    ev_dur:      $('sim-event-duration').value,
  });
  startStream(
    `/api/simulate?${query}`,
    `SIM-${$('sim-seed').value}`,
    $('scenario-preset').value
  );
}

/* ─── SSE streaming ─── */
function startStream(url, runId, family) {
  stopStream();
  state.data = { run_id: runId, family, truth_rows: [], predictions: [] };
  state.held = false;
  $('live-sim-btn').disabled = true;
  $('stream-btn').disabled = true;
  $('stop-sim-btn').hidden = false;
  setConnection('Streaming run…');
  renderDashboard(state.data);

  state.stream = new EventSource(url);

  state.stream.onmessage = (event) => {
    const chunk = JSON.parse(event.data);
    if (chunk.error) { setConnection(chunk.error, true); stopStream(false); return; }
    if (chunk.truth)      state.data.truth_rows.push(chunk.truth);
    if (chunk.prediction)  state.data.predictions.push(chunk.prediction);
    renderDashboard(state.data);
  };

  state.stream.addEventListener('end', () => {
    setConnection('Run complete');
    stopStream(false);
  });

  state.stream.onerror = () => {
    if (state.stream && state.stream.readyState === EventSource.CLOSED) {
      setConnection('Run complete');
    } else {
      setConnection('Stream interrupted', true);
    }
    stopStream(false);
  };
}

function stopStream(close = true) {
  if (close && state.stream) state.stream.close();
  state.stream = null;
  if ($('live-sim-btn'))  $('live-sim-btn').disabled = false;
  if ($('stream-btn'))    $('stream-btn').disabled = false;
  if ($('stop-sim-btn'))  $('stop-sim-btn').hidden = true;
}

function setConnection(message, error = false) {
  $('connection-status').textContent = message;
  $('connection-status').classList.toggle('error-text', error);
}

/* ═══════════════════ DASHBOARD RENDER ═══════════════════ */

function renderDashboard(data) {
  const truth = data.truth_rows || [];
  const predictions = data.predictions || [];
  const family = data.family || '';

  // ─── KPIs ───
  const peak = predictions.reduce(
    (best, p) => (p.warning_probability > best.warning_probability ? p : best),
    { warning_probability: 0 }
  );
  const hold = truth.find(row => row.cmp_mode === 'HOLD');
  const isNormal = family === 'NORMAL';
  const isFault = !isNormal && truth.length > 0;

  $('kpi-status').textContent = hold ? 'Shield Active' : peak.warning_probability > 0.5 ? 'Warning' : truth.length ? 'Nominal' : 'Ready';
  $('kpi-status-detail').textContent = truth.length ? `Last mode: ${truth[truth.length - 1].cmp_mode || 'unknown'}` : 'Choose a scenario';

  $('kpi-confidence').textContent = predictions.length ? `${(peak.warning_probability * 100).toFixed(1)}%` : '--';
  $('kpi-warning-time').textContent = predictions.length ? `Peak at ${Number(peak.timestamp_s).toFixed(1)} s` : 'No run loaded';

  $('kpi-action').textContent = hold ? 'SAFE HOLD' : truth.length ? 'NO HOLD' : '--';
  $('kpi-action-detail').textContent = hold ? `Entered hold at ${Number(hold.timestamp_s).toFixed(1)} s` : truth.length ? 'No intervention triggered' : 'No decision yet';

  // Business outcome
  if (!truth.length) {
    $('kpi-outcome').textContent = '--';
    $('kpi-outcome-detail').textContent = 'Run a scenario to see impact';
  } else if (isNormal) {
    $('kpi-outcome').textContent = '✓ Wafer OK';
    $('kpi-outcome-detail').textContent = 'No fault — polishing completed normally';
  } else if (hold) {
    $('kpi-outcome').textContent = '✓ Wafer Saved';
    $('kpi-outcome-detail').textContent = 'AI intervened before pad glazing damage';
  } else if (isFault && !hold) {
    $('kpi-outcome').textContent = '✗ Wafer Damaged';
    $('kpi-outcome-detail').textContent = 'No protection — continued polishing during fault';
  }

  // Decision banner
  if (hold) {
    $('decision-title').textContent = 'AI Supervisor triggered a safe hold — wafer protected';
    $('decision-copy').textContent = `The predictive shield detected cascading facility degradation (confidence ≥50%) and paused polishing at ${Number(hold.timestamp_s).toFixed(1)} s. Estimated $50k wafer saved.`;
    $('decision-chip').textContent = 'WAFER SAVED';
    $('decision-chip').className = 'decision-chip chip-blue';
  } else if (isFault && !hold) {
    $('decision-title').textContent = 'No protection — wafer exposed to fault damage';
    $('decision-copy').textContent = 'Without the AI shield, the polishing continued during the facility fault. The pad glazed and the wafer surface was damaged.';
    $('decision-chip').textContent = 'DAMAGE';
    $('decision-chip').className = 'decision-chip chip-red';
  } else if (isNormal && truth.length) {
    $('decision-title').textContent = 'Normal operation — no intervention required';
    $('decision-copy').textContent = 'Facility conditions were nominal throughout. The AI correctly stayed silent and did not raise false alarms.';
    $('decision-chip').textContent = 'BASELINE';
    $('decision-chip').className = 'decision-chip';
  } else {
    $('decision-title').textContent = 'No scenario running';
    $('decision-copy').textContent = 'The decision summary will update as the simulated process evolves.';
    $('decision-chip').textContent = 'READY';
    $('decision-chip').className = 'decision-chip';
  }

  renderSignals(data);
  renderPredictions(data);
  renderModes(data);
  renderTimeline(data);
}

/* Compatibility alias */
function updateDashboard(data) { renderDashboard(data); }

/* ═══════════════════ PLOTLY CHARTS ═══════════════════ */

const layoutBase = {
  paper_bgcolor: 'transparent',
  plot_bgcolor: 'transparent',
  font: { color: '#9ba8b8', family: 'Inter, sans-serif', size: 11 },
  margin: { t: 8, r: 16, l: 48, b: 36 },
  hovermode: 'x unified',
  xaxis: { title: 'Time (s)', gridcolor: '#263342', zeroline: false },
  legend: { orientation: 'h', y: 1.12, x: 0 },
};

function plot(id, traces, layout) {
  if (!window.Plotly) {
    const chart = $(id);
    chart.textContent = 'Charts unavailable: Plotly could not be loaded.';
    chart.classList.add('chart-fallback');
    return;
  }
  Plotly.react(id, traces, { ...layoutBase, ...layout }, {
    responsive: true,
    displaylogo: false,
    modeBarButtonsToRemove: ['lasso2d', 'select2d'],
  });
}

function renderSignals(data) {
  const rows = data.truth_rows || [];
  plot('chart-signals', [
    {
      x: rows.map(r => r.timestamp_s), y: rows.map(r => r.cmp_mrr_m_s),
      name: 'MRR', mode: 'lines+markers',
      line: { color: '#4b9cff', width: 2 }, marker: { size: 3 },
    },
    {
      x: rows.map(r => r.timestamp_s), y: rows.map(r => r.grid_voltage_pu),
      name: 'Grid voltage', mode: 'lines',
      line: { color: '#e8b45c', width: 2 }, yaxis: 'y2',
    },
  ], {
    yaxis: { title: 'MRR (m/s)', gridcolor: '#263342', zeroline: false },
    yaxis2: { title: 'Grid (pu)', overlaying: 'y', side: 'right', range: [0, 1.1], gridcolor: 'transparent' },
  });
}

function renderPredictions(data) {
  const rows = data.predictions || [];
  const truth = data.truth_rows || [];
  plot('chart-predictions', [
    {
      x: truth.map(r => r.timestamp_s), y: truth.map(r => r.cmp_mrr_m_s),
      name: 'True MRR', mode: 'lines',
      line: { color: '#4b9cff', width: 2 },
    },
    {
      x: rows.map(r => r.timestamp_s), y: rows.map(r => r.predicted_mrr),
      name: 'Predicted MRR', mode: 'lines',
      line: { color: '#c084fc', width: 2, dash: 'dot' },
    },
    {
      x: rows.map(r => r.timestamp_s), y: rows.map(r => r.warning_probability),
      name: 'AI fault confidence', mode: 'lines',
      line: { color: '#f06464', width: 2 },
      fill: 'tozeroy', fillcolor: 'rgba(240,100,100,.12)', yaxis: 'y2',
    },
  ], {
    yaxis: { title: 'MRR (m/s)', gridcolor: '#263342', zeroline: false },
    yaxis2: { title: 'AI Confidence', overlaying: 'y', side: 'right', range: [0, 1], gridcolor: 'transparent', tickformat: '.0%' },
  });
}

function renderModes(data) {
  const rows = data.truth_rows || [];
  const modeMap = { PREPARE: 1, DRESS: 2, POLISH: 3, HOLD: 4, RECOVER: 5, COMPLETE: 6 };
  const values = rows.map(r => modeMap[r.cmp_mode] || 0);
  plot('chart-actions', [
    {
      x: rows.map(r => r.timestamp_s), y: values,
      name: 'Mode', mode: 'lines+markers',
      line: { color: '#55c99b', shape: 'hv' }, marker: { size: 3 },
    },
  ], {
    yaxis: {
      title: 'Mode',
      tickvals: [1, 2, 3, 4, 5, 6],
      ticktext: ['PREPARE', 'DRESS', 'POLISH', 'HOLD', 'RECOVER', 'COMPLETE'],
      gridcolor: '#263342', zeroline: false,
    },
  });
}

function renderTimeline(data) {
  const truth = data.truth_rows || [];
  const predictions = data.predictions || [];
  const list = $('event-timeline');
  list.innerHTML = '';

  if (!truth.length) {
    list.innerHTML = '<li class="empty-state">Run a scenario to see detection and response milestones.</li>';
    $('timeline-caption').textContent = 'No events recorded';
    return;
  }

  const peak = predictions.reduce(
    (best, p) => (p.warning_probability > best.warning_probability ? p : best),
    { warning_probability: 0 }
  );

  const events = [
    { time: truth[0].timestamp_s, title: 'Run initialized', copy: `${data.family || 'Artifact'} · ${truth.length} points` },
  ];

  // Find when polishing starts
  const polishStart = truth.find(r => r.cmp_mode === 'POLISH');
  if (polishStart) events.push({ time: polishStart.timestamp_s, title: 'Polishing started', copy: 'CMP entered POLISH mode' });

  // Event activation
  const eventActive = truth.find(r => r.event_active === true);
  if (eventActive) events.push({ time: eventActive.timestamp_s, title: 'Fault injected', copy: `${data.family} event activated` });

  // Warning threshold
  if (peak.warning_probability > 0.5) {
    events.push({ time: peak.timestamp_s, title: 'AI warning peaked', copy: `${(peak.warning_probability * 100).toFixed(1)}% confidence` });
  }

  // Hold
  const hold = truth.find(r => r.cmp_mode === 'HOLD');
  if (hold) events.push({ time: hold.timestamp_s, title: 'Safe hold triggered', copy: 'AI supervisor paused the process' });

  events.push({ time: truth[truth.length - 1].timestamp_s, title: 'Trace complete', copy: `Final mode: ${truth[truth.length - 1].cmp_mode}` });

  events.sort((a, b) => a.time - b.time);

  events.forEach((event, index) => {
    const li = document.createElement('li');
    li.className = index === events.length - 1 ? 'timeline-last' : '';
    li.innerHTML = `<time>${Number(event.time).toFixed(1)} s</time><div><strong>${event.title}</strong><span>${event.copy}</span></div>`;
    list.appendChild(li);
  });

  $('timeline-caption').textContent = `${events.length} milestones · ${data.family || 'artifact'}`;
}
