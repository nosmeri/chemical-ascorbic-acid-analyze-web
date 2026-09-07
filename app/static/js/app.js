/**
 * ChemTitrate Pro - Frontend Application Logic
 * Asynchronous Potentiometric Titration Analysis & Plotly Visualization
 */

// Application State
const state = {
  currentFileId: null,
  filename: '',
  runs: [],
  runDetails: {},
  activeRun: '실행 1',
  latestAnalysis: null,
  isProcessing: false,
};

// DOM Element References
const elements = {
  // Navigation & Status
  serverStatus: document.getElementById('server-status'),

  // Upload Section
  dropZone: document.getElementById('drop-zone'),
  fileInput: document.getElementById('file-input'),
  fileInfoBox: document.getElementById('file-info-box'),
  activeFilename: document.getElementById('active-filename'),

  // Control Form
  paramForm: document.getElementById('param-form'),
  targetRunSelect: document.getElementById('target-run-select'),
  detectedRunsCount: document.getElementById('detected-runs-count'),
  startTimeInput: document.getElementById('start-time-input'),
  endTimeInput: document.getElementById('end-time-input'),
  btnResetTimeRange: document.getElementById('btn-reset-time-range'),
  dataTimeRangeHint: document.getElementById('data-time-range-hint'),
  windowLenInput: document.getElementById('window-len-input'),
  polyOrderInput: document.getElementById('poly-order-input'),
  evenWarningBox: document.getElementById('even-warning-box'),
  suggestedOddVal: document.getElementById('suggested-odd-val'),
  btnFixToOdd: document.getElementById('btn-fix-to-odd'),
  toggleWhyOdd: document.getElementById('toggle-why-odd'),
  whyOddCard: document.querySelector('.info-card'),
  btnRunAnalysis: document.getElementById('btn-run-analysis'),

  // Dashboard Area
  emptyState: document.getElementById('empty-state'),
  resultsContainer: document.getElementById('results-container'),

  // Metrics
  metricEndpointTime: document.getElementById('metric-endpoint-time'),
  metricEndpointVoltage: document.getElementById('metric-endpoint-voltage'),
  metricEndpointSlope: document.getElementById('metric-endpoint-slope'),
  metricElapsed: document.getElementById('metric-elapsed'),
  metricPtsInfo: document.getElementById('metric-pts-info'),

  // Charts
  chartMainTitle: document.getElementById('chart-main-title'),
  chartTitration: document.getElementById('chart-titration'),
  chartDerivative: document.getElementById('chart-derivative'),
  btnChartResetZoom: document.getElementById('btn-chart-reset-zoom'),
  btnExportTitrationPng: document.getElementById('btn-export-titration-png'),
  btnExportDerivPng: document.getElementById('btn-export-deriv-png'),
  btnExportFullPng: document.getElementById('btn-export-full-png'),
  btnExportCsv: document.getElementById('btn-export-csv'),
  summaryTableBody: document.getElementById('summary-table-body'),

  // Loader
  loadingOverlay: document.getElementById('loading-overlay'),
  loadingText: document.getElementById('loading-text'),
};

// ============================================================================
// Initialization & Event Listeners
// ============================================================================
document.addEventListener('DOMContentLoaded', () => {
  initEventListeners();
  validateWindowLength();
});

function initEventListeners() {
  // File Upload Handlers
  elements.dropZone.addEventListener('click', () => elements.fileInput.click());
  elements.fileInput.addEventListener('change', handleFileSelect);

  ['dragenter', 'dragover'].forEach(event => {
    elements.dropZone.addEventListener(event, (e) => {
      e.preventDefault();
      e.stopPropagation();
      elements.dropZone.classList.add('dragover');
    });
  });

  ['dragleave', 'drop'].forEach(event => {
    elements.dropZone.addEventListener(event, (e) => {
      e.preventDefault();
      e.stopPropagation();
      elements.dropZone.classList.remove('dragover');
    });
  });

  elements.dropZone.addEventListener('drop', (e) => {
    const files = e.dataTransfer.files;
    if (files.length > 0) {
      uploadFile(files[0]);
    }
  });

  // Run Select Change
  elements.targetRunSelect.addEventListener('change', (e) => {
    state.activeRun = e.target.value;
    updateRunParameterPresets();
  });

  // Window Length Odd Validation
  elements.windowLenInput.addEventListener('input', validateWindowLength);
  elements.btnFixToOdd.addEventListener('click', fixWindowLengthToOdd);

  // Toggle Why Odd Explanation Card
  elements.toggleWhyOdd.addEventListener('click', () => {
    elements.whyOddCard.classList.toggle('open');
  });

  // Reset Time Range to Run Defaults
  elements.btnResetTimeRange.addEventListener('click', resetTimeRangeToDefaults);

  // Run Analysis Button
  elements.btnRunAnalysis.addEventListener('click', triggerAnalysis);

  // Chart Export Actions
  elements.btnChartResetZoom.addEventListener('click', resetChartZoom);
  elements.btnExportTitrationPng.addEventListener('click', exportTitrationChartPng);
  elements.btnExportDerivPng.addEventListener('click', exportDerivativeChartPng);
  elements.btnExportFullPng.addEventListener('click', exportFullDualChartPng);
  elements.btnExportCsv.addEventListener('click', exportAnalysisCsv);
}

// ============================================================================
// File Upload & Data Management
// ============================================================================
function handleFileSelect(e) {
  const file = e.target.files[0];
  if (file) {
    uploadFile(file);
  }
}

async function uploadFile(file) {
  if (!file.name.toLowerCase().endsWith('.csv')) {
    alert('CSV 형식(.csv)의 파일만 업로드할 수 있습니다.');
    return;
  }

  showLoader(`CSV 파일 분석 중: ${file.name}`);
  const formData = new FormData();
  formData.append('file', file);

  try {
    const res = await fetch('/api/upload', {
      method: 'POST',
      body: formData,
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || '파일 업로드에 실패했습니다.');
    }

    const data = await res.json();
    populateUploadedData(data);
    hideLoader();

    // 자동으로 분석 실행
    triggerAnalysis();
  } catch (err) {
    hideLoader();
    alert(`오류: ${err.message}`);
  }
}

async function loadSampleData() {
  showLoader('내장된 전위차 적정 샘플(data2.csv)을 로드하고 있습니다...');
  try {
    const res = await fetch('/api/sample');
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || '샘플 데이터 로드 실패');
    }
    const data = await res.json();
    populateUploadedData(data);
    hideLoader();

    // 샘플 로드 후 즉시 첫 분석 실행
    triggerAnalysis();
  } catch (err) {
    hideLoader();
    alert(`샘플 데이터 로드 중 오류가 발생했습니다: ${err.message}`);
  }
}

function populateUploadedData(data) {
  state.currentFileId = data.file_id;
  state.filename = data.filename;
  state.runs = data.runs;
  state.runDetails = data.run_details;

  // 파일 정보 박스 갱신
  elements.activeFilename.textContent = data.filename;
  elements.fileInfoBox.classList.remove('hidden');

  // 실행 목록 드롭다운 채우기
  elements.targetRunSelect.innerHTML = '';
  data.runs.forEach(run => {
    const opt = document.createElement('option');
    opt.value = run;
    opt.textContent = run;
    elements.targetRunSelect.appendChild(opt);
  });

  state.activeRun = data.runs[0] || '실행 1';
  elements.targetRunSelect.value = state.activeRun;
  elements.detectedRunsCount.textContent = `감지된 실행: ${data.runs.length}개`;

  // 실행 파라미터 기본값 설정
  updateRunParameterPresets();
}

function updateRunParameterPresets() {
  const detail = state.runDetails[state.activeRun];
  if (!detail) return;

  elements.dataTimeRangeHint.textContent = `전체 데이터 범위: ${detail.min_time}s ~ ${detail.max_time}s (${detail.total_points.toLocaleString()}개 측정점)`;

  // 시작시간 및 종료시간 기본 권장값 (기존 스크립트: 60s ~ 400s)
  const defaultStart = Math.max(detail.min_time, 60.0);
  const defaultEnd = Math.min(detail.max_time, 400.0);

  elements.startTimeInput.value = defaultStart;
  elements.endTimeInput.value = defaultEnd;

  // 기본 윈도우 크기는 3501로 고정
  elements.windowLenInput.value = detail.recommended_window || 3501;
  validateWindowLength();
}

function resetTimeRangeToDefaults() {
  const detail = state.runDetails[state.activeRun];
  if (detail) {
    elements.startTimeInput.value = detail.min_time;
    elements.endTimeInput.value = detail.max_time;
  }
}

// ============================================================================
// Window Length Validation (Must be Odd)
// ============================================================================
function validateWindowLength() {
  let val = parseInt(elements.windowLenInput.value, 10);
  if (isNaN(val) || val < 3) {
    elements.evenWarningBox.classList.add('hidden');
    return false;
  }

  if (val % 2 === 0) {
    // 짝수일 경우 경고 박스 및 추천 홀수 제시
    const suggested = val + 1;
    elements.suggestedOddVal.textContent = suggested;
    elements.evenWarningBox.classList.remove('hidden');
    return false;
  } else {
    elements.evenWarningBox.classList.add('hidden');
    return true;
  }
}

function fixWindowLengthToOdd() {
  let val = parseInt(elements.windowLenInput.value, 10);
  if (!isNaN(val)) {
    elements.windowLenInput.value = (val % 2 === 0) ? val + 1 : val;
    validateWindowLength();
  }
}

// ============================================================================
// Asynchronous Analysis
// ============================================================================
async function triggerAnalysis() {
  if (!state.currentFileId) {
    alert('분석할 CSV 파일을 먼저 업로드해 주세요.');
    return;
  }

  // 윈도우 크기 검증 및 필요 시 자동 홀수 보정
  let winLen = parseInt(elements.windowLenInput.value, 10);
  if (isNaN(winLen) || winLen < 3) {
    winLen = 3501;
    elements.windowLenInput.value = winLen;
  }
  if (winLen % 2 === 0) {
    winLen += 1;
    elements.windowLenInput.value = winLen;
    validateWindowLength();
  }

  const startTime = parseFloat(elements.startTimeInput.value);
  const endTime = parseFloat(elements.endTimeInput.value);
  const polyOrder = parseInt(elements.polyOrderInput.value, 10) || 3;

  if (startTime >= endTime) {
    alert('시작 시간은 종료 시간보다 작아야 합니다.');
    return;
  }

  const payload = {
    file_id: state.currentFileId,
    target_run: state.activeRun,
    start_time: startTime,
    end_time: endTime,
    window_len: winLen,
    poly_order: polyOrder,
    downsample_points: 3000,
  };

  showLoader(`FastAPI 비동기 워커에서 '${state.activeRun}' 적정 분석 중...`);

  try {
    const res = await fetch('/api/analyze', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || '분석 중 오류가 발생했습니다.');
    }

    const data = await res.json();
    state.latestAnalysis = data;
    renderAnalysisResults(data);
    hideLoader();
  } catch (err) {
    hideLoader();
    alert(`분석 오류: ${err.message}`);
  }
}

// ============================================================================
// Result Rendering & Plotly Charts
// ============================================================================
function renderAnalysisResults(data) {
  // Empty State 숨기고 결과 화면 표시
  elements.emptyState.classList.add('hidden');
  elements.resultsContainer.classList.remove('hidden');

  const m = data.metrics;
  const c = data.chart_data;

  // 1. Metric Cards Update
  elements.metricEndpointTime.textContent = m.endpoint_time.toFixed(2);
  elements.metricEndpointVoltage.textContent = m.endpoint_voltage.toFixed(2);
  elements.metricEndpointSlope.textContent = m.endpoint_slope.toFixed(4);
  elements.metricElapsed.textContent = m.elapsed_ms.toFixed(1);
  elements.metricPtsInfo.textContent = `총 ${m.total_points.toLocaleString()} 측정점 (Savitzky-Golay 완료)`;

  elements.chartMainTitle.textContent = `전위차 적정 곡선 & 1차 도함수 분석 (${data.target_run})`;

  // 2. Render Plotly Charts
  renderTitrationPlot(c, m, data.target_run);
  renderDerivativePlot(c, m);

  // 3. Render Summary Table
  renderSummaryTable(data);
}

function renderTitrationPlot(c, m, runName) {
  const traceRaw = {
    x: c.raw_x,
    y: c.raw_y,
    mode: 'markers',
    name: 'Raw Data (측정 원본)',
    marker: {
      color: '#4ade80',
      size: 3,
      opacity: 0.45,
    },
    hoverinfo: 'x+y',
  };

  const traceSmooth = {
    x: c.smooth_x,
    y: c.smooth_y,
    mode: 'lines',
    name: `Smoothed (Win=${m.window_len})`,
    line: {
      color: '#10b981',
      width: 2.5,
    },
    hoverinfo: 'x+y',
  };

  const traceEndpoint = {
    x: [m.endpoint_time],
    y: [m.endpoint_voltage],
    mode: 'markers',
    name: `종말점 (${m.endpoint_time}s, ${m.endpoint_voltage}mV)`,
    marker: {
      color: '#f59e0b',
      size: 11,
      symbol: 'circle',
      line: { color: '#ffffff', width: 2 },
    },
    hoverinfo: 'text',
    text: [`적정 종말점<br>시간: ${m.endpoint_time}s<br>전위: ${m.endpoint_voltage}mV`],
  };

  const layout = {
    paper_bgcolor: 'rgba(0,0,0,0)',
    plot_bgcolor: 'rgba(6, 10, 18, 0.75)',
    margin: { l: 60, r: 30, t: 30, b: 40 },
    xaxis: {
      title: { text: '시간 (Time, s)', font: { color: '#94a3b8', size: 12 } },
      color: '#94a3b8',
      gridcolor: 'rgba(255, 255, 255, 0.06)',
      zerolinecolor: 'rgba(255, 255, 255, 0.1)',
    },
    yaxis: {
      title: { text: '전압 (Voltage, mV)', font: { color: '#94a3b8', size: 12 } },
      color: '#94a3b8',
      gridcolor: 'rgba(255, 255, 255, 0.06)',
      zerolinecolor: 'rgba(255, 255, 255, 0.1)',
    },
    shapes: [
      {
        type: 'line',
        x0: m.endpoint_time,
        x1: m.endpoint_time,
        y0: 0,
        y1: 1,
        yref: 'paper',
        line: {
          color: '#f59e0b',
          width: 1.5,
          dash: 'dash',
        },
      },
    ],
    annotations: [
      {
        x: m.endpoint_time,
        y: m.endpoint_voltage,
        text: `Endpoint: ${m.endpoint_time}s`,
        showarrow: true,
        arrowhead: 2,
        arrowcolor: '#f59e0b',
        arrowsize: 1,
        arrowwidth: 1.5,
        ax: 40,
        ay: -40,
        bgcolor: 'rgba(245, 158, 11, 0.15)',
        bordercolor: '#f59e0b',
        borderwidth: 1,
        borderpad: 4,
        font: { color: '#f59e0b', size: 11, family: 'Inter' },
      },
    ],
    legend: {
      font: { color: '#cbd5e1', size: 11 },
      bgcolor: 'rgba(15, 23, 42, 0.7)',
      bordercolor: 'rgba(255,255,255,0.1)',
      borderwidth: 1,
      x: 0.01,
      y: 0.99,
    },
    hovermode: 'closest',
  };

  const config = {
    responsive: true,
    displayModeBar: false,
  };

  Plotly.react(elements.chartTitration, [traceRaw, traceSmooth, traceEndpoint], layout, config);
}

function renderDerivativePlot(c, m) {
  const traceDeriv = {
    x: c.deriv_x,
    y: c.deriv_y,
    mode: 'lines',
    name: '1st Derivative (dV/dt)',
    line: {
      color: '#06b6d4',
      width: 2,
    },
    hoverinfo: 'x+y',
  };

  const tracePeak = {
    x: [m.endpoint_time],
    y: [m.endpoint_slope],
    mode: 'markers',
    name: `Max dV/dt (${m.endpoint_time}s, ${m.endpoint_slope}mV/s)`,
    marker: {
      color: '#f59e0b',
      size: 10,
      symbol: 'diamond',
      line: { color: '#ffffff', width: 1.5 },
    },
    hoverinfo: 'text',
    text: [`최대 기울기 (종말점 피크)<br>시간: ${m.endpoint_time}s<br>기울기: ${m.endpoint_slope} mV/s`],
  };

  const layout = {
    paper_bgcolor: 'rgba(0,0,0,0)',
    plot_bgcolor: 'rgba(6, 10, 18, 0.75)',
    margin: { l: 60, r: 30, t: 25, b: 45 },
    xaxis: {
      title: { text: '시간 (Time, s)', font: { color: '#94a3b8', size: 12 } },
      color: '#94a3b8',
      gridcolor: 'rgba(255, 255, 255, 0.06)',
      zerolinecolor: 'rgba(255, 255, 255, 0.1)',
    },
    yaxis: {
      title: { text: 'dV/dt (mV/s)', font: { color: '#94a3b8', size: 12 } },
      color: '#94a3b8',
      gridcolor: 'rgba(255, 255, 255, 0.06)',
      zerolinecolor: 'rgba(255, 255, 255, 0.1)',
    },
    shapes: [
      {
        type: 'line',
        x0: m.endpoint_time,
        x1: m.endpoint_time,
        y0: 0,
        y1: 1,
        yref: 'paper',
        line: {
          color: '#f59e0b',
          width: 1.5,
          dash: 'dash',
        },
      },
    ],
    annotations: [
      {
        x: m.endpoint_time,
        y: m.endpoint_slope,
        text: `Peak Slope: ${m.endpoint_slope} mV/s`,
        showarrow: true,
        arrowhead: 2,
        arrowcolor: '#f59e0b',
        arrowsize: 1,
        arrowwidth: 1.5,
        ax: -40,
        ay: -35,
        bgcolor: 'rgba(245, 158, 11, 0.15)',
        bordercolor: '#f59e0b',
        borderwidth: 1,
        borderpad: 4,
        font: { color: '#f59e0b', size: 11, family: 'Inter' },
      },
    ],
    legend: {
      font: { color: '#cbd5e1', size: 11 },
      bgcolor: 'rgba(15, 23, 42, 0.7)',
      bordercolor: 'rgba(255,255,255,0.1)',
      borderwidth: 1,
      x: 0.01,
      y: 0.99,
    },
    hovermode: 'closest',
  };

  const config = {
    responsive: true,
    displayModeBar: false,
  };

  Plotly.react(elements.chartDerivative, [traceDeriv, tracePeak], layout, config);
}

function renderSummaryTable(data) {
  const m = data.metrics;
  const rows = [
    { item: '분석 대상 실행', val: data.target_run, unit: '-', desc: '선택된 적정 시험 식별자' },
    { item: '적정 종말점 (Time)', val: `${m.endpoint_time.toFixed(2)}`, unit: 's', desc: '1차 도함수 최댓값(피크) 발생 시점' },
    { item: '종말점 전위 (Voltage)', val: `${m.endpoint_voltage.toFixed(2)}`, unit: 'mV', desc: '종말점에서의 평활화 측정 전위' },
    { item: '최대 미분 기울기 (dV/dt)', val: `${m.endpoint_slope.toFixed(4)}`, unit: 'mV/s', desc: '화학적 당량점에서의 최대 순간 반응 속도' },
    { item: '적용 시간 구간', val: `${m.start_time.toFixed(1)} ~ ${m.end_time.toFixed(1)}`, unit: 's', desc: '노이즈 제거 및 피크 탐색 유효 시간대' },
    { item: 'Savitzky-Golay 윈도우 (window_len)', val: `${m.window_len}`, unit: 'pts', desc: '대칭성 유지를 위한 홀수 윈도우 포인트 수' },
    { item: '다항식 차수 (poly_order)', val: `${m.poly_order}`, unit: '차', desc: '국소 회귀 피팅 다항식 차수' },
    { item: '분석 측정점 총수', val: `${m.total_points.toLocaleString()}`, unit: '개', desc: '필터링 구간 내 실제 처리된 데이터 포인트' },
    { item: '비동기 연산 소요 시간', val: `${m.elapsed_ms.toFixed(1)}`, unit: 'ms', desc: 'FastAPI asyncio.to_thread 처리 시간' },
  ];

  elements.summaryTableBody.innerHTML = rows.map(r => `
    <tr>
      <td>${r.item}</td>
      <td>${r.val}</td>
      <td>${r.unit}</td>
      <td style="color: var(--text-sub);">${r.desc}</td>
    </tr>
  `).join('');
}

function resetChartZoom() {
  if (elements.chartTitration && elements.chartTitration.data) {
    Plotly.relayout(elements.chartTitration, { 'xaxis.autorange': true, 'yaxis.autorange': true });
  }
  if (elements.chartDerivative && elements.chartDerivative.data) {
    Plotly.relayout(elements.chartDerivative, { 'xaxis.autorange': true, 'yaxis.autorange': true });
  }
}

// 1) 상단 적정 곡선 단독 PNG 저장
function exportTitrationChartPng() {
  if (elements.chartTitration && elements.chartTitration.data) {
    Plotly.downloadImage(elements.chartTitration, {
      format: 'png',
      width: 1400,
      height: 550,
      filename: `titration_curve_${state.activeRun}`,
    });
  }
}

// 2) 하단 1차 도함수(dV/dt) 곡선 단독 PNG 저장
function exportDerivativeChartPng() {
  if (elements.chartDerivative && elements.chartDerivative.data) {
    Plotly.downloadImage(elements.chartDerivative, {
      format: 'png',
      width: 1400,
      height: 500,
      filename: `1st_derivative_${state.activeRun}`,
    });
  }
}

// 3) 2단 전체 차트(적정 곡선 + 1차 도함수) 고해상도 결합 PNG 저장
async function exportFullDualChartPng() {
  if (!elements.chartTitration || !elements.chartDerivative) return;
  showLoader('2단 고해상도 종합 차트 이미지를 생성하고 있습니다...');

  try {
    const [imgTitration, imgDeriv] = await Promise.all([
      Plotly.toImage(elements.chartTitration, { format: 'png', width: 1400, height: 550 }),
      Plotly.toImage(elements.chartDerivative, { format: 'png', width: 1400, height: 500 }),
    ]);

    const canvas = document.createElement('canvas');
    canvas.width = 1400;
    canvas.height = 1070;
    const ctx = canvas.getContext('2d');

    // 다크 테마 배경 채우기
    ctx.fillStyle = '#080c14';
    ctx.fillRect(0, 0, canvas.width, canvas.height);

    const loadImg = (src) =>
      new Promise((resolve, reject) => {
        const img = new Image();
        img.onload = () => resolve(img);
        img.onerror = reject;
        img.src = src;
      });

    const [loadedTitration, loadedDeriv] = await Promise.all([
      loadImg(imgTitration),
      loadImg(imgDeriv),
    ]);

    // 상단 적정 곡선 & 하단 1차 도함수 곡선 세로 합성
    ctx.drawImage(loadedTitration, 0, 10);
    ctx.drawImage(loadedDeriv, 0, 565);

    const a = document.createElement('a');
    a.download = `titration_full_analysis_${state.activeRun}.png`;
    a.href = canvas.toDataURL('image/png');
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    hideLoader();
  } catch (err) {
    hideLoader();
    alert(`차트 이미지 생성 중 오류가 발생했습니다: ${err.message}`);
  }
}

function exportAnalysisCsv() {
  if (!state.latestAnalysis) return;
  const c = state.latestAnalysis.chart_data;
  const m = state.latestAnalysis.metrics;

  let csv = `Time (s),Raw Voltage (mV),Smoothed Voltage (mV),1st Derivative dV/dt (mV/s)\n`;
  for (let i = 0; i < c.raw_x.length; i++) {
    csv += `${c.raw_x[i]},${c.raw_y[i]},${c.smooth_y[i]},${c.deriv_y[i]}\n`;
  }

  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `analysis_result_${state.activeRun}_win${m.window_len}.csv`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

// ============================================================================
// UI Helper Utilities
// ============================================================================
function showLoader(msg = '데이터를 처리하고 있습니다...') {
  elements.loadingText.textContent = msg;
  elements.loadingOverlay.classList.remove('hidden');
}

function hideLoader() {
  elements.loadingOverlay.classList.add('hidden');
}
