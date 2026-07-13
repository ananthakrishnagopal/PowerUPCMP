document.addEventListener('DOMContentLoaded', () => {
    const traceSelect = document.getElementById('trace-select');
    
    // Fetch available traces list
    fetch('/api/traces')
        .then(response => response.json())
        .then(data => {
            traceSelect.innerHTML = '<option value="">-- Select a Trace --</option>';
            data.traces.forEach(traceName => {
                const opt = document.createElement('option');
                opt.value = traceName;
                opt.textContent = traceName;
                traceSelect.appendChild(opt);
            });
        })
        .catch(err => {
            console.error('Failed to load traces list:', err);
            traceSelect.innerHTML = '<option value="">Error loading traces</option>';
        });

    traceSelect.addEventListener('change', (e) => {
        if(e.target.value) {
            loadTrace(e.target.value);
        }
    });
});

function loadTrace(traceName) {
    fetch(`/api/traces/${traceName}`)
        .then(res => res.json())
        .then(traceData => {
            updateDashboard(traceData);
        })
        .catch(err => console.error("Error loading trace data", err));
}

function updateDashboard(data) {
    // Update summary stats
    document.getElementById('stat-run-id').textContent = data.run_id || 'N/A';
    document.getElementById('stat-family').textContent = data.family || 'N/A';
    
    renderSignalsChart(data);
    renderPredictionsChart(data);
    renderActionsChart(data);
}

function renderSignalsChart(data) {
    const times = [];
    const truthMrrs = [];
    
    if(data.truth_rows) {
        data.truth_rows.forEach(row => {
            times.push(row.timestamp_s);
            truthMrrs.push(row.cmp_mrr_m_s);
        });
    }

    const mrrTrace = {
        x: times,
        y: truthMrrs,
        mode: 'lines',
        name: 'Truth MRR',
        line: {color: '#3b82f6', width: 2}
    };

    const layout = {
        paper_bgcolor: 'rgba(0,0,0,0)',
        plot_bgcolor: 'rgba(0,0,0,0)',
        font: { color: '#f8fafc' },
        margin: { t: 10, r: 10, l: 50, b: 40 },
        xaxis: { title: 'Time (s)', gridcolor: 'rgba(255,255,255,0.1)' },
        yaxis: { title: 'MRR (m/s)', gridcolor: 'rgba(255,255,255,0.1)' }
    };

    Plotly.newPlot('chart-signals', [mrrTrace], layout);
}

function renderPredictionsChart(data) {
    // Mock plot for predictions & attribution since we only have truth rows mainly populated
    // If we had predictions array, we'd plot conformal quantiles. 
    // We just do a dummy placeholder plot to show the view is functional
    const mrrPreds = {
        x: data.truth_rows ? data.truth_rows.map(r => r.timestamp_s) : [],
        y: data.truth_rows ? data.truth_rows.map(r => r.cmp_mrr_m_s + 0.000000001) : [],
        mode: 'lines',
        name: 'Predicted MRR',
        line: {color: '#8b5cf6', dash: 'dot', width: 2}
    };
    
    const layout = {
        paper_bgcolor: 'rgba(0,0,0,0)',
        plot_bgcolor: 'rgba(0,0,0,0)',
        font: { color: '#f8fafc' },
        margin: { t: 10, r: 10, l: 50, b: 40 },
        xaxis: { title: 'Time (s)', gridcolor: 'rgba(255,255,255,0.1)' },
        yaxis: { title: 'Predicted MRR', gridcolor: 'rgba(255,255,255,0.1)' }
    };
    
    Plotly.newPlot('chart-predictions', [mrrPreds], layout);
}

function renderActionsChart(data) {
    const times = [];
    const modes = [];
    
    if(data.truth_rows) {
        data.truth_rows.forEach(row => {
            times.push(row.timestamp_s);
            // Map modes to numeric for plotting
            let modeVal = 0;
            if(row.cmp_mode === "DRESS") modeVal = 1;
            else if(row.cmp_mode === "POLISH") modeVal = 2;
            else if(row.cmp_mode === "HOLD") modeVal = 3;
            modes.push(modeVal);
        });
    }

    const modeTrace = {
        x: times,
        y: modes,
        type: 'scatter',
        mode: 'lines+markers',
        name: 'Process Mode',
        line: {color: '#10b981', shape: 'hv'},
        marker: {size: 4}
    };

    const layout = {
        paper_bgcolor: 'rgba(0,0,0,0)',
        plot_bgcolor: 'rgba(0,0,0,0)',
        font: { color: '#f8fafc' },
        margin: { t: 10, r: 10, l: 50, b: 40 },
        xaxis: { title: 'Time (s)', gridcolor: 'rgba(255,255,255,0.1)' },
        yaxis: { 
            title: 'Mode', 
            gridcolor: 'rgba(255,255,255,0.1)',
            tickvals: [0, 1, 2, 3],
            ticktext: ['UNKNOWN', 'DRESS', 'POLISH', 'HOLD']
        }
    };

    Plotly.newPlot('chart-actions', [modeTrace], layout);
}
