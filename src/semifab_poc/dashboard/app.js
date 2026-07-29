/* ═══════════════════ app.js — PowerUPCMP Dashboard ═══════════════════ */

const STAKEHOLDER_TRACE = 'stakeholder-demo-predictive-hold.json';
const MRR_TO_NM_PER_S = 1.0e9;
const state = { stream: null, data: { truth_rows: [], predictions: [], actions: [], safety_decisions: [] }, held: false };
const $ = (id) => document.getElementById(id);

const descriptions = {
  PUMP_TRIP:              'UPW pump trip — hydraulic support degrades during polishing, creating visible MRR and protection response.',
  VOLTAGE_SAG:            'Grid voltage sag — a brownout starves the VFD, reducing motor speed and water flow.',
  VALVE_RESTRICTION:      'UPW valve restriction — a partially closed valve reduces hydraulic support to the CMP tool.',
  GRID_INTERRUPTION:      'Short grid interruption — a brief power cut tests UPS transfer and recovery.',
  NORMAL:                 'Normal operation — healthy baseline. MRR should plateau cleanly and the supervisor stays quiet.'
};

/* ─── Preset defaults for physics parameters ─── */
const presetDefaults = {
  PUMP_TRIP:              { grid: '1.0',  valve: '1.0',  bias: '0' },
  VOLTAGE_SAG:            { grid: '0.75', valve: '1.0',  bias: '0' },
  VALVE_RESTRICTION:      { grid: '1.0',  valve: '0.25', bias: '0' },
  GRID_INTERRUPTION:      { grid: '1.0',  valve: '1.0',  bias: '0' },
  NORMAL:                 { grid: '1.0',  valve: '1.0',  bias: '0' }
};

/* ─── Boot ─── */
document.addEventListener('DOMContentLoaded', () => {
  $('sim-controller').value = 'UTILITY_THRESHOLD';
  $('sim-event-start').value = '7.2';
  $('sim-event-duration').value = '4.0';
  $('sim-duration').value = '16';

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
      $('trace-selector').value,
      'REPLAY'
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
      if (payload.traces.includes(STAKEHOLDER_TRACE)) {
        $('trace-selector').value = STAKEHOLDER_TRACE;
        $('stream-btn').textContent = 'Replay stakeholder demo';
        setConnection('Stakeholder demo artifact ready');
      }
    })
    .catch(() => {
      $('trace-selector').innerHTML = '<option value="">Artifacts unavailable</option>';
    });

  renderDashboard(state.data);
});

$('trace-selector')?.addEventListener('change', () => {
  $('stream-btn').textContent =
    $('trace-selector').value === STAKEHOLDER_TRACE
      ? 'Replay stakeholder demo'
      : 'Replay artifact';
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
    $('scenario-preset').value,
    $('sim-controller').value
  );
}

/* ─── SSE streaming ─── */
function startStream(url, runId, family, controller = '') {
  stopStream();
  state.data = { run_id: runId, family, controller, truth_rows: [], predictions: [], actions: [], safety_decisions: [] };
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
    if (chunk.metadata) state.data.metadata = chunk.metadata;
    if (chunk.scenario) state.data.scenario = chunk.scenario;
    if (chunk.summary) state.data.summary = chunk.summary;
    if (chunk.actions) {
      state.data.actions = chunk.truth
        ? state.data.actions.concat(chunk.actions)
        : chunk.actions;
    }
    if (chunk.safety_decisions) {
      state.data.safety_decisions = chunk.truth
        ? state.data.safety_decisions.concat(chunk.safety_decisions)
        : chunk.safety_decisions;
    }
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
  const controller = data.controller || '';
  const summary = data.summary || {};

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
  $('kpi-action-detail').textContent = hold
    ? `Entered hold at ${Number(summary.hold_time_s ?? hold.timestamp_s).toFixed(1)} s`
    : truth.length ? 'No intervention triggered' : 'No decision yet';

  // Business outcome
  if (!truth.length) {
    $('kpi-outcome').textContent = '--';
    $('kpi-outcome-detail').textContent = 'Run a scenario to see impact';
  } else if (isNormal) {
    $('kpi-outcome').textContent = 'Stable baseline';
    $('kpi-outcome-detail').textContent = 'No fault — polishing completed normally';
  } else if (hold) {
    $('kpi-outcome').textContent = 'Safe hold';
    $('kpi-outcome-detail').textContent = summary.final_status || 'Supervisor paused until utility recovery';
  } else if (isFault && !hold && controller === 'PREDICTIVE') {
    $('kpi-outcome').textContent = 'No intervention';
    $('kpi-outcome-detail').textContent = 'Predictive supervisor stayed below its hold threshold in this live run';
  } else if (isFault && !hold) {
    $('kpi-outcome').textContent = 'Risk exposure';
    $('kpi-outcome-detail').textContent = 'No hold — polishing continued during the synthetic fault';
  }

  // Decision banner
  if (hold) {
    const isPredictive = controller === 'PREDICTIVE' || controller === 'REPLAY';
    $('decision-title').textContent = isPredictive
      ? 'Predictive supervisor triggered a safe hold'
      : 'Live protection triggered a safe hold';
    $('decision-copy').textContent = isPredictive
      ? `The warning crossed the 50% hold threshold and the safety filter approved a bounded hold at ${Number(summary.hold_time_s ?? hold.timestamp_s).toFixed(1)} s. This is a synthetic demonstration, not a real-fab yield claim.`
      : `The utility threshold controller detected degraded facility support and the safety filter approved a bounded hold at ${Number(summary.hold_time_s ?? hold.timestamp_s).toFixed(1)} s. This is a synthetic live-control demonstration.`;
    $('decision-chip').textContent = 'SAFE HOLD';
    $('decision-chip').className = 'decision-chip chip-blue';
  } else if (isFault && !hold && controller === 'PREDICTIVE') {
    $('decision-title').textContent = 'Predictive supervisor did not intervene';
    $('decision-copy').textContent = 'The live classifier stayed below the configured hold gate after the synthetic fault evidence arrived. Use the validated stakeholder replay for the predictive-hold screen recording.';
    $('decision-chip').textContent = 'NO HOLD';
    $('decision-chip').className = 'decision-chip';
  } else if (isFault && !hold) {
    $('decision-title').textContent = 'No protection — process remained exposed';
    $('decision-copy').textContent = 'The baseline controller continued the recipe during the synthetic facility fault. This is a risk-exposure comparison, not a measured defect claim.';
    $('decision-chip').textContent = 'EXPOSURE';
    $('decision-chip').className = 'decision-chip chip-red';
  } else if (isNormal && truth.length) {
    $('decision-title').textContent = 'Normal operation — no intervention required';
    $('decision-copy').textContent = 'Facility conditions were nominal throughout. The supervisor correctly stayed silent and did not raise false alarms.';
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

function eventWindowShapes(rows) {
  const shapes = [];
  let start = null;
  rows.forEach((row, index) => {
    if (row.event_active && start === null) start = row.timestamp_s;
    const next = rows[index + 1];
    if (start !== null && (!next || !next.event_active)) {
      shapes.push({
        type: 'rect',
        xref: 'x',
        yref: 'paper',
        x0: start,
        x1: row.timestamp_s,
        y0: 0,
        y1: 1,
        fillcolor: 'rgba(232,180,92,.16)',
        line: { width: 0 },
        layer: 'below',
      });
      start = null;
    }
  });
  return shapes;
}

function renderSignals(data) {
  const rows = data.truth_rows || [];
  const mrrNmPerS = rows.map(r => (r.cmp_mrr_m_s || 0) * MRR_TO_NM_PER_S);
  plot('chart-signals', [
    {
      x: rows.map(r => r.timestamp_s), y: mrrNmPerS,
      name: 'MRR (nm/s)', mode: 'lines+markers',
      line: { color: '#4b9cff', width: 2 }, marker: { size: 3 },
    },
    {
      x: rows.map(r => r.timestamp_s), y: rows.map(r => r.grid_voltage_pu),
      name: 'Grid voltage', mode: 'lines',
      line: { color: '#e8b45c', width: 2 }, yaxis: 'y2',
    },
    {
      x: rows.map(r => r.timestamp_s), y: rows.map(r => (r.upw_supply_pressure_pa || 0) / 300000),
      name: 'UPW pressure health', mode: 'lines',
      line: { color: '#55c99b', width: 2 }, yaxis: 'y2',
    },
    {
      x: rows.map(r => r.timestamp_s), y: rows.map(r => (r.pump_flow_m3_s || 0) / 0.0002),
      name: 'Pump flow health', mode: 'lines',
      line: { color: '#c084fc', width: 2 }, yaxis: 'y2',
    },
  ], {
    yaxis: { title: 'MRR (nm/s)', gridcolor: '#263342', zeroline: false, rangemode: 'tozero' },
    yaxis2: { title: 'Utility health', overlaying: 'y', side: 'right', range: [0, 1.1], gridcolor: 'transparent' },
    shapes: eventWindowShapes(rows),
  });
}

function renderPredictions(data) {
  const rows = data.predictions || [];
  const truth = data.truth_rows || [];
  const useUtilityRisk = data.controller === 'UTILITY_THRESHOLD';
  const signalRows = useUtilityRisk ? truth : rows;
  const trueMrrNmPerS = truth.map(r => (r.cmp_mrr_m_s || 0) * MRR_TO_NM_PER_S);
  const predictedMrrNmPerS = rows.map(r => (r.predicted_mrr || 0) * MRR_TO_NM_PER_S);
  const protectionSignal = useUtilityRisk
    ? signalRows.map(r => 1 - Math.max(0, Math.min(1, r.effective_availability ?? 1)))
    : signalRows.map(r => r.warning_probability);
  plot('chart-predictions', [
    {
      x: truth.map(r => r.timestamp_s), y: trueMrrNmPerS,
      name: 'True MRR (nm/s)', mode: 'lines',
      line: { color: '#4b9cff', width: 2 },
    },
    {
      x: rows.map(r => r.timestamp_s), y: predictedMrrNmPerS,
      name: 'MRR reference (nm/s)', mode: 'lines',
      line: { color: '#c084fc', width: 2, dash: 'dot' },
    },
    {
      x: signalRows.map(r => r.timestamp_s), y: protectionSignal,
      name: useUtilityRisk ? 'Utility risk' : 'Warning probability',
      mode: 'lines',
      line: { color: '#f06464', width: 2 },
      fill: 'tozeroy', fillcolor: 'rgba(240,100,100,.12)', yaxis: 'y2',
    },
  ], {
    yaxis: { title: 'MRR (nm/s)', gridcolor: '#263342', zeroline: false, rangemode: 'tozero' },
    yaxis2: { title: useUtilityRisk ? 'Utility risk' : 'Warning probability', overlaying: 'y', side: 'right', range: [0, 1], gridcolor: 'transparent', tickformat: '.0%' },
    shapes: eventWindowShapes(truth),
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
    shapes: eventWindowShapes(rows),
    yaxis: {
      title: 'Mode',
      tickvals: [1, 2, 3, 4, 5, 6],
      ticktext: ['PREPARE', 'DRESS', 'POLISH', 'HOLD', 'RECOVER', 'COMPLETE'],
      range: [0.5, 6.5],
      gridcolor: '#263342', zeroline: false,
    },
  });
}

function renderTimeline(data) {
  const truth = data.truth_rows || [];
  const predictions = data.predictions || [];
  const actions = data.actions || [];
  const safetyDecisions = data.safety_decisions || [];
  const summary = data.summary || {};
  const latestVisibleTime = truth.length ? Number(truth[truth.length - 1].timestamp_s) : 0;
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
    events.push({ time: peak.timestamp_s, title: 'Warning probability peaked', copy: `${(peak.warning_probability * 100).toFixed(1)}% probability` });
  }

  const holdProposal = actions.find(a => a.action_type === 'SAFE_HOLD');
  if (holdProposal) {
    events.push({
      time: holdProposal.timestamp_s,
      title: 'Supervisor proposed hold',
      copy: holdProposal.rationale || 'Risk crossed the configured hold gate',
    });
  }

  const holdApproval = safetyDecisions.find(d => d.final_action_type === 'SAFE_HOLD');
  if (holdApproval) {
    events.push({
      time: holdApproval.timestamp_s,
      title: 'Safety filter approved hold',
      copy: `Outcome: ${holdApproval.outcome}`,
    });
  }

  // Hold
  const hold = truth.find(r => r.cmp_mode === 'HOLD');
  if (hold) events.push({ time: summary.hold_time_s ?? hold.timestamp_s, title: 'Process entered hold', copy: 'CMP recipe progress paused during utility recovery' });

  const resume = actions.find(a => a.action_type === 'CONTROLLED_RESUME');
  if (resume) {
    events.push({
      time: resume.timestamp_s,
      title: 'Controlled resume proposed',
      copy: resume.rationale || 'Risk cleared and utility service recovered',
    });
  }

  events.push({ time: truth[truth.length - 1].timestamp_s, title: 'Trace complete', copy: `Final mode: ${truth[truth.length - 1].cmp_mode}` });

  const visibleEvents = events
    .filter(event => Number(event.time) <= latestVisibleTime + 1.0e-12)
    .sort((a, b) => a.time - b.time);

  visibleEvents.forEach((event, index) => {
    const li = document.createElement('li');
    li.className = index === visibleEvents.length - 1 ? 'timeline-last' : '';
    const time = document.createElement('time');
    time.textContent = `${Number(event.time).toFixed(1)} s`;
    const body = document.createElement('div');
    const title = document.createElement('strong');
    title.textContent = event.title;
    const copy = document.createElement('span');
    copy.textContent = event.copy;
    body.append(title, copy);
    li.append(time, body);
    list.appendChild(li);
  });

  $('timeline-caption').textContent = `${visibleEvents.length} milestones · ${data.family || 'artifact'}`;
}
