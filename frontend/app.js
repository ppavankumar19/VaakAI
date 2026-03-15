'use strict';

// ─── CONFIG ──────────────────────────────────────────────────────────────────
const API_BASE = 'http://localhost:8523';
const POLL_INTERVAL_MS = 3000;

// ─── STATE ────────────────────────────────────────────────────────────────────
const state = {
  sessionId: null,
  videoFile: null,
  sourceUrl: null,
  uploadMode: 'file',   // 'file' | 'url'
  transcript: [],
  analysis: null,
  pollTimer: null,
  fillerSet: new Set(),
  techSet: new Set(),
  radarChart: null,
  fillerChart: null,
  paceChart: null,
};

// ─── DOM HELPERS ──────────────────────────────────────────────────────────────
const $ = id => document.getElementById(id);
const show = id => $(id).classList.remove('hidden');
const hide = id => $(id).classList.add('hidden');

function showScreen(name) {
  // Use inline styles — avoids conflicts with CSS class specificity
  ['upload', 'processing', 'results'].forEach(s => {
    $(`screen-${s}`).style.display = 'none';
  });
  $(`screen-${name}`).style.display = (name === 'results') ? 'block' : 'flex';
}

function formatTime(ms) {
  const s = Math.floor(ms / 1000);
  const m = Math.floor(s / 60);
  const sec = s % 60;
  return `${m}:${String(sec).padStart(2, '0')}`;
}

function formatBytes(bytes) {
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

// ─── TAB SWITCHING ────────────────────────────────────────────────────────────
function setupTabs() {
  $('tab-file').addEventListener('click', () => setUploadMode('file'));
  $('tab-url').addEventListener('click', () => setUploadMode('url'));

  $('url-input').addEventListener('input', e => {
    if (state.uploadMode !== 'url') return;
    const valid = isValidYouTubeUrl(e.target.value.trim());
    $('upload-btn').disabled = !valid;
    if (valid) hide('upload-error');
  });
}

function setUploadMode(mode) {
  state.uploadMode = mode;
  $('tab-file').classList.toggle('active', mode === 'file');
  $('tab-url').classList.toggle('active', mode === 'url');

  if (mode === 'file') {
    show('section-file');
    hide('section-url');
    $('upload-btn').disabled = !state.videoFile;
  } else {
    hide('section-file');
    show('section-url');
    $('upload-btn').disabled = !isValidYouTubeUrl($('url-input').value.trim());
  }
  hide('upload-error');
}

function isValidYouTubeUrl(url) {
  try {
    const u = new URL(url);
    return ['youtube.com', 'www.youtube.com', 'youtu.be', 'm.youtube.com'].includes(u.hostname);
  } catch {
    return false;
  }
}

// ─── DROP ZONE SETUP ─────────────────────────────────────────────────────────
function setupDropZone() {
  const zone = $('drop-zone');
  const input = $('file-input');

  zone.addEventListener('click', () => input.click());
  zone.addEventListener('keydown', e => { if (e.key === 'Enter' || e.key === ' ') input.click(); });

  zone.addEventListener('dragover', e => { e.preventDefault(); zone.classList.add('drag-over'); });
  zone.addEventListener('dragleave', () => zone.classList.remove('drag-over'));
  zone.addEventListener('drop', e => {
    e.preventDefault();
    zone.classList.remove('drag-over');
    const file = e.dataTransfer.files[0];
    if (file) handleFileSelect(file);
  });

  input.addEventListener('change', () => {
    if (input.files[0]) handleFileSelect(input.files[0]);
  });

  $('clear-file').addEventListener('click', clearFile);
  $('upload-btn').addEventListener('click', () => {
    if (state.uploadMode === 'url') startUrlUpload();
    else startUpload();
  });
}

function handleFileSelect(file) {
  const ALLOWED = ['.mp4', '.mov', '.webm', '.avi', '.mkv'];
  const ext = file.name.slice(file.name.lastIndexOf('.')).toLowerCase();

  if (!ALLOWED.includes(ext)) {
    showUploadError(`Unsupported file type "${ext}". Please upload: ${ALLOWED.join(', ')}`);
    return;
  }
  if (file.size > 500 * 1024 * 1024) {
    showUploadError('File is larger than 500 MB. Please trim or compress the video first.');
    return;
  }

  state.videoFile = file;
  hide('upload-error');

  $('file-name-label').textContent = file.name;
  $('file-size-label').textContent = formatBytes(file.size);
  show('file-preview');
  $('upload-btn').disabled = false;
}

function clearFile() {
  state.videoFile = null;
  $('file-input').value = '';
  hide('file-preview');
  $('upload-btn').disabled = true;
  hide('upload-error');
}

function showUploadError(msg) {
  const el = $('upload-error');
  el.textContent = msg;
  show('upload-error');
}

// ─── UPLOAD ───────────────────────────────────────────────────────────────────
function startUpload() {
  if (!state.videoFile) return;

  const language = $('language-select').value;
  const formData = new FormData();
  formData.append('file', state.videoFile);
  formData.append('language', language);

  show('upload-progress');
  $('upload-btn').disabled = true;

  const xhr = new XMLHttpRequest();

  xhr.upload.addEventListener('progress', e => {
    if (!e.lengthComputable) return;
    const pct = Math.round(e.loaded / e.total * 100);
    $('upload-bar').style.width = pct + '%';
    $('upload-pct').textContent = `Uploading… ${pct}%`;
  });

  xhr.addEventListener('load', () => {
    if (xhr.status === 202) {
      const data = JSON.parse(xhr.responseText);
      state.sessionId = data.session_id;
      showScreen('processing');
      pollSession();
    } else {
      let msg = 'Upload failed.';
      try { msg = JSON.parse(xhr.responseText).detail || msg; } catch (_) {}
      hide('upload-progress');
      $('upload-btn').disabled = false;
      showUploadError(msg);
    }
  });

  xhr.addEventListener('error', () => {
    hide('upload-progress');
    $('upload-btn').disabled = false;
    showUploadError('Network error. Is the backend running at ' + API_BASE + '?');
  });

  xhr.open('POST', `${API_BASE}/api/upload`);
  xhr.send(formData);
}

function startUrlUpload() {
  const url = $('url-input').value.trim();
  if (!isValidYouTubeUrl(url)) return;

  const language = $('language-select').value;
  hide('upload-error');
  $('upload-btn').disabled = true;
  show('upload-progress');
  $('upload-bar').style.width = '100%';
  $('upload-pct').textContent = 'Submitting…';

  fetch(`${API_BASE}/api/upload-url`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ url, language }),
  })
    .then(r => r.json().then(data => ({ ok: r.ok, data })))
    .then(({ ok, data }) => {
      if (ok) {
        state.sessionId = data.session_id;
        showScreen('processing');
        pollSession();
      } else {
        hide('upload-progress');
        $('upload-btn').disabled = false;
        showUploadError(data.detail || 'Failed to submit URL.');
      }
    })
    .catch(() => {
      hide('upload-progress');
      $('upload-btn').disabled = false;
      showUploadError('Network error. Is the backend running at ' + API_BASE + '?');
    });
}

// ─── POLLING ──────────────────────────────────────────────────────────────────
const STAGE_LABELS = {
  downloading:      'Downloading from YouTube…',
  uploading:        'Saving your video…',
  extracting_audio: 'Extracting audio with FFmpeg…',
  transcribing:     'Transcribing speech via Sarvam.ai (this takes a minute)…',
  analyzing:        'Running AI analysis…',
  embedding:        'Finalizing and indexing results…',
  complete:         'Done!',
};

function pollSession() {
  if (!state.sessionId) return;

  fetch(`${API_BASE}/api/session/${state.sessionId}`)
    .then(r => r.json())
    .then(data => {
      if (data.status === 'complete') {
        clearTimeout(state.pollTimer);
        renderResults(data);
        showScreen('results');
      } else if (data.status === 'failed') {
        clearTimeout(state.pollTimer);
        showProcessingError(data.error || 'Processing failed. Please try again.');
      } else {
        // still processing
        const pct = data.progress_percent || 5;
        $('processing-bar').style.width = pct + '%';
        $('processing-pct').textContent = pct + '%';
        $('processing-stage-label').textContent =
          STAGE_LABELS[data.stage] || 'Processing…';

        state.pollTimer = setTimeout(pollSession, POLL_INTERVAL_MS);
      }
    })
    .catch(() => {
      state.pollTimer = setTimeout(pollSession, POLL_INTERVAL_MS);
    });
}

function showProcessingError(msg) {
  $('processing-error-msg').textContent = msg;
  show('processing-error');
  $('retry-btn').onclick = () => { showScreen('upload'); resetState(); };
}

// ─── RESULTS ──────────────────────────────────────────────────────────────────
function extractYouTubeId(url) {
  try {
    const u = new URL(url);
    if (u.hostname === 'youtu.be') return u.pathname.slice(1).split('?')[0];
    return u.searchParams.get('v');
  } catch {
    return null;
  }
}

function renderResults(data) {
  state.transcript = data.transcript || [];
  state.analysis = data.analysis || {};
  state.sourceUrl = data.source_url || null;

  const a = state.analysis;

  // Build lookup sets for highlighting
  state.fillerSet = new Set(
    Object.keys(a.filler_words?.breakdown || {})
  );
  state.techSet = new Set(
    (a.technical_terms || []).map(t => t.toLowerCase())
  );

  // Set up video panel
  const video = $('video-player');
  if (state.videoFile) {
    URL.revokeObjectURL(video.src);
    video.src = URL.createObjectURL(state.videoFile);
    $('video-panel').classList.remove('hidden');
    $('youtube-panel').classList.add('hidden');
  } else if (state.sourceUrl) {
    $('video-panel').classList.add('hidden');
    $('youtube-panel').classList.remove('hidden');
    $('youtube-link').href = state.sourceUrl;
    const ytId = extractYouTubeId(state.sourceUrl);
    if (ytId) {
      $('youtube-iframe').src = `https://www.youtube.com/embed/${ytId}?rel=0`;
    }
  }

  renderTranscript();
  renderMetricCards(a);
  destroyCharts();
  renderCharts(a);
  renderTopics(a.topics);
  renderAnalysisCards(a);
}

// ─── TRANSCRIPT ───────────────────────────────────────────────────────────────
function renderTranscript() {
  const body = $('transcript-body');
  body.innerHTML = '';

  if (!state.transcript.length) {
    body.innerHTML = '<p style="color:var(--muted);padding:16px">No transcript available.</p>';
    return;
  }

  const frag = document.createDocumentFragment();

  state.transcript.forEach((seg, i) => {
    const div = document.createElement('div');
    div.className = 'segment';
    div.dataset.start = seg.start_ms;
    div.dataset.end = seg.end_ms;
    div.dataset.index = i;
    div.innerHTML = `
      <span class="ts">${formatTime(seg.start_ms)}</span>
      <span class="seg-text">${highlightText(seg.text)}</span>
    `;
    div.addEventListener('click', () => seekVideo(seg.start_ms));
    frag.appendChild(div);
  });

  body.appendChild(frag);
}

function highlightText(text) {
  // Escape HTML first
  let out = text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');

  // Tech terms (blue) — sort longer phrases first to avoid partial matches
  const techSorted = [...state.techSet].sort((a, b) => b.length - a.length);
  for (const term of techSorted) {
    const re = new RegExp(`\\b${escapeRe(term)}\\b`, 'gi');
    out = out.replace(re, m => `<span class="tech-term">${m}</span>`);
  }

  // Filler words (red)
  const fillerSorted = [...state.fillerSet].sort((a, b) => b.length - a.length);
  for (const filler of fillerSorted) {
    const re = new RegExp(`\\b${escapeRe(filler)}\\b`, 'gi');
    out = out.replace(re, m => `<span class="filler">${m}</span>`);
  }

  return out;
}

function escapeRe(str) {
  return str.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

// ─── VIDEO SYNC ───────────────────────────────────────────────────────────────
function setupVideoSync() {
  const video = $('video-player');

  video.addEventListener('timeupdate', () => {
    const currentMs = video.currentTime * 1000;
    let activeEl = null;

    document.querySelectorAll('.segment').forEach(el => {
      const start = parseInt(el.dataset.start, 10);
      const end = parseInt(el.dataset.end, 10);
      if (currentMs >= start && currentMs < end) {
        el.classList.add('active');
        activeEl = el;
      } else {
        el.classList.remove('active');
      }
    });

    if (activeEl) {
      activeEl.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }
  });

  $('speed-select').addEventListener('change', e => {
    video.playbackRate = parseFloat(e.target.value);
  });
}

function seekVideo(startMs) {
  if (state.sourceUrl) {
    const ytId = extractYouTubeId(state.sourceUrl);
    if (ytId) {
      const sec = Math.floor(startMs / 1000);
      $('youtube-iframe').src = `https://www.youtube.com/embed/${ytId}?start=${sec}&autoplay=1&rel=0`;
    }
    return;
  }
  const video = $('video-player');
  video.currentTime = startMs / 1000;
  video.play();
}

// ─── TRANSCRIPT SEARCH ────────────────────────────────────────────────────────
function setupTranscriptSearch() {
  $('transcript-search').addEventListener('input', e => {
    const q = e.target.value.trim().toLowerCase();
    document.querySelectorAll('.segment').forEach(el => {
      if (!q) {
        el.classList.remove('hidden-search');
        return;
      }
      const text = el.querySelector('.seg-text').textContent.toLowerCase();
      el.classList.toggle('hidden-search', !text.includes(q));
    });
  });
}

// ─── METRIC CARDS ─────────────────────────────────────────────────────────────
function renderMetricCards(a) {
  const vr = a.vocabulary_richness || {};
  const pace = a.pace || {};
  const fw = a.filler_words || {};

  const sentiment = a.sentiment || {};
  const cards = [
    {
      value: vr.total_words?.toLocaleString() ?? '—',
      label: 'Total Words',
      sub: '',
    },
    {
      value: vr.unique_words?.toLocaleString() ?? '—',
      label: 'Unique Words',
      sub: `Richness: ${vr.richness_score ?? '—'}`,
    },
    {
      value: pace.avg_wpm ?? '—',
      label: 'Avg. WPM',
      sub: pace.rating ? pace.rating.replace('_', ' ') : '',
    },
    {
      value: fw.percentage != null ? `${fw.percentage}%` : '—',
      label: 'Filler Word Rate',
      sub: `${fw.total_count ?? 0} occurrences`,
    },
    {
      value: a.grammar_score != null ? `${a.grammar_score}/100` : '—',
      label: 'Grammar Score',
      sub: '',
    },
    {
      value: sentiment.score != null ? `${sentiment.score}/100` : '—',
      label: 'Confidence',
      tone: sentiment.overall || null,
    },
  ];

  const grid = $('metrics-cards');
  grid.innerHTML = cards.map(c => `
    <div class="metric-card">
      <div class="metric-value">${c.value}</div>
      <div class="metric-label">${c.label}</div>
      ${c.sub ? `<div class="metric-sub">${c.sub}</div>` : ''}
      ${c.tone ? `<div class="metric-tone ${c.tone}">${c.tone}</div>` : ''}
    </div>
  `).join('');
}

// ─── CHARTS ───────────────────────────────────────────────────────────────────
const CHART_TEXT_COLOR = '#8892a4';
const CHART_GRID_COLOR = 'rgba(255,255,255,0.07)';

function wpmToScore(wpm) {
  if (!wpm) return 0;
  if (wpm >= 120 && wpm <= 160) return 100;
  if (wpm >= 100 && wpm < 120) return 60 + (wpm - 100) * 2;
  if (wpm > 160 && wpm <= 180) return 60 + (180 - wpm) * 2;
  return Math.max(20, 40);
}

function renderCharts(a) {
  renderRadar(a);
  renderFillerChart(a.filler_words);
  renderPaceChart(a.pace);
}

function destroyCharts() {
  ['radarChart', 'fillerChart', 'paceChart'].forEach(key => {
    if (state[key]) { state[key].destroy(); state[key] = null; }
  });
}

function renderRadar(a) {
  const vr = a.vocabulary_richness || {};
  const fw = a.filler_words || {};
  const pace = a.pace || {};

  const scores = [
    Math.round((vr.richness_score || 0) * 100),
    wpmToScore(pace.avg_wpm),
    a.grammar_score ?? 50,
    a.sentiment?.score ?? 50,
    Math.min(100, (a.technical_terms?.length || 0) * 7),
    Math.max(0, 100 - (fw.percentage || 0) * 8),
  ];

  const ctx = $('chart-radar').getContext('2d');
  state.radarChart = new Chart(ctx, {
    type: 'radar',
    data: {
      labels: ['Vocabulary', 'Pace', 'Grammar', 'Confidence', 'Tech Depth', 'Clarity'],
      datasets: [{
        label: 'Your Score',
        data: scores,
        backgroundColor: 'rgba(108,99,255,0.18)',
        borderColor: '#6c63ff',
        pointBackgroundColor: '#6c63ff',
        pointRadius: 4,
        pointHoverRadius: 6,
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      scales: {
        r: {
          min: 0,
          max: 100,
          ticks: { display: false, stepSize: 25 },
          grid: { color: CHART_GRID_COLOR },
          angleLines: { color: CHART_GRID_COLOR },
          pointLabels: { color: CHART_TEXT_COLOR, font: { size: 12 } },
        },
      },
      plugins: { legend: { display: false } },
    },
  });
}

function renderFillerChart(fw) {
  if (!fw?.breakdown || !Object.keys(fw.breakdown).length) {
    $('chart-fillers').parentElement.innerHTML =
      '<p style="color:var(--muted);text-align:center;padding:40px 0">No filler words detected 🎉</p>';
    return;
  }

  const entries = Object.entries(fw.breakdown).sort((a, b) => b[1] - a[1]);
  const labels = entries.map(([k]) => k);
  const values = entries.map(([, v]) => v);

  const ctx = $('chart-fillers').getContext('2d');
  state.fillerChart = new Chart(ctx, {
    type: 'bar',
    data: {
      labels,
      datasets: [{
        label: 'Count',
        data: values,
        backgroundColor: 'rgba(239,68,68,0.7)',
        borderColor: '#ef4444',
        borderWidth: 1,
        borderRadius: 4,
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      scales: {
        x: { ticks: { color: CHART_TEXT_COLOR }, grid: { color: CHART_GRID_COLOR } },
        y: { ticks: { color: CHART_TEXT_COLOR }, grid: { color: CHART_GRID_COLOR }, beginAtZero: true },
      },
      plugins: { legend: { display: false } },
    },
  });
}

function renderPaceChart(pace) {
  if (!pace?.timeline?.length) {
    $('chart-pace').parentElement.innerHTML =
      '<p style="color:var(--muted);text-align:center;padding:40px 0">Not enough data for pace timeline.</p>';
    return;
  }

  const labels = pace.timeline.map(t => t.segment);
  const values = pace.timeline.map(t => t.wpm);

  const ctx = $('chart-pace').getContext('2d');
  state.paceChart = new Chart(ctx, {
    type: 'line',
    data: {
      labels,
      datasets: [{
        label: 'WPM',
        data: values,
        borderColor: '#00d4aa',
        backgroundColor: 'rgba(0,212,170,0.1)',
        pointBackgroundColor: '#00d4aa',
        pointRadius: 4,
        fill: true,
        tension: 0.4,
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      scales: {
        x: { ticks: { color: CHART_TEXT_COLOR }, grid: { color: CHART_GRID_COLOR } },
        y: {
          ticks: { color: CHART_TEXT_COLOR },
          grid: { color: CHART_GRID_COLOR },
          beginAtZero: false,
          suggestedMin: 60,
        },
      },
      plugins: {
        legend: { display: false },
        annotation: {
          annotations: {
            idealMin: { type: 'line', yMin: 120, yMax: 120, borderColor: 'rgba(34,197,94,0.4)', borderDash: [5, 5] },
            idealMax: { type: 'line', yMin: 160, yMax: 160, borderColor: 'rgba(34,197,94,0.4)', borderDash: [5, 5] },
          },
        },
      },
    },
  });
}

// ─── TOPICS TIMELINE ──────────────────────────────────────────────────────────
function renderTopics(topics) {
  const section = $('section-topics');
  const container = $('topics-timeline');
  container.innerHTML = '';

  if (!topics || !topics.length) {
    section.style.display = 'none';
    return;
  }

  section.style.display = '';
  topics.forEach((t, i) => {
    const block = document.createElement('div');
    block.className = 'topic-block';
    block.innerHTML = `
      <div class="topic-num">Topic ${i + 1}</div>
      <div class="topic-name">${escapeHtml(t.topic)}</div>
      ${t.start ? `<div class="topic-start">${escapeHtml(t.start)}</div>` : ''}
    `;
    if (t.start) {
      block.style.cursor = 'pointer';
      block.title = `Jump to ${t.start}`;
      block.addEventListener('click', () => seekVideo(parseTimestamp(t.start)));
    }
    container.appendChild(block);
  });
}

function parseTimestamp(ts) {
  // Convert "M:SS" string to milliseconds
  const parts = ts.split(':').map(Number);
  if (parts.length === 2) return (parts[0] * 60 + parts[1]) * 1000;
  if (parts.length === 3) return (parts[0] * 3600 + parts[1] * 60 + parts[2]) * 1000;
  return 0;
}

// ─── ANALYSIS CARDS ───────────────────────────────────────────────────────────
function renderAnalysisCards(a) {
  // Summary
  $('summary-text').textContent = a.summary || 'No summary available.';

  // Technical terms
  const tags = $('tech-terms-tags');
  const terms = a.technical_terms || [];
  if (terms.length) {
    tags.innerHTML = terms.map(t => `<span class="tag">${escapeHtml(t)}</span>`).join('');
  } else {
    tags.innerHTML = '<span style="color:var(--muted);font-size:0.85rem">No technical terms detected.</span>';
  }

  // Improvement tips
  const list = $('tips-list');
  const tips = a.improvement_tips || [];
  if (tips.length) {
    list.innerHTML = tips.map(t => `<li>${escapeHtml(t)}</li>`).join('');
  } else {
    list.innerHTML = '<li style="color:var(--muted)">No tips available.</li>';
  }
}

function escapeHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
}

// ─── EXPORT ───────────────────────────────────────────────────────────────────
function exportTxt() {
  if (!state.transcript.length) return;
  const lines = state.transcript.map(s =>
    `[${formatTime(s.start_ms)}] ${s.text}`
  );
  const blob = new Blob([lines.join('\n')], { type: 'text/plain' });
  downloadBlob(blob, 'transcript.txt');
}

function exportPdf() {
  window.print();
}

function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

// ─── RAG Q&A ──────────────────────────────────────────────────────────────────
function setupRagPanel() {
  const input = $('rag-input');
  const sendBtn = $('rag-send-btn');

  // Enable send button when there's text
  input.addEventListener('input', () => {
    sendBtn.disabled = !input.value.trim();
  });

  // Enter key submits
  input.addEventListener('keydown', e => {
    if (e.key === 'Enter' && !sendBtn.disabled) submitRagQuestion(input.value.trim());
  });

  sendBtn.addEventListener('click', () => {
    const q = input.value.trim();
    if (q) submitRagQuestion(q);
  });

  // Suggested chips
  document.querySelectorAll('.rag-chip').forEach(chip => {
    chip.addEventListener('click', () => submitRagQuestion(chip.textContent.trim()));
  });
}

function submitRagQuestion(question) {
  if (!state.sessionId) return;

  const input = $('rag-input');
  const sendBtn = $('rag-send-btn');

  input.value = '';
  sendBtn.disabled = true;
  input.disabled = true;

  // Render question + loading placeholder
  const msgEl = renderRagQuestion(question);
  const answerEl = msgEl.querySelector('.rag-a');

  fetch(`${API_BASE}/api/analyze/ask`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ session_id: state.sessionId, question }),
  })
    .then(r => r.json().then(data => ({ ok: r.ok, data })))
    .then(({ ok, data }) => {
      answerEl.classList.remove('loading');
      if (!ok) {
        answerEl.classList.add('rag-error');
        answerEl.textContent = data.detail || 'Something went wrong.';
        return;
      }
      answerEl.textContent = data.answer || 'No answer returned.';
      if (data.source_segments?.length) {
        renderRagSources(msgEl, data.source_segments);
      }
    })
    .catch(() => {
      answerEl.classList.remove('loading');
      answerEl.classList.add('rag-error');
      answerEl.textContent = 'Network error — is the backend running?';
    })
    .finally(() => {
      input.disabled = false;
      input.focus();
    });
}

function renderRagQuestion(question) {
  const messages = $('rag-messages');

  const msg = document.createElement('div');
  msg.className = 'rag-msg';
  msg.innerHTML = `
    <div class="rag-q">
      <div class="rag-q-icon">Q</div>
      <span>${escapeHtml(question)}</span>
    </div>
    <div class="rag-a loading">Searching transcript…</div>
  `;
  messages.appendChild(msg);
  msg.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  return msg;
}

function renderRagSources(msgEl, sources) {
  const sourcesDiv = document.createElement('div');
  sourcesDiv.className = 'rag-sources';

  sources.forEach(seg => {
    const chip = document.createElement('button');
    chip.className = 'rag-source-chip';
    chip.innerHTML = `
      <svg viewBox="0 0 12 12" fill="none" aria-hidden="true">
        <polygon points="2,2 10,6 2,10" fill="currentColor"/>
      </svg>
      ${formatTime(seg.start_ms)}
    `;
    chip.title = seg.text;
    chip.addEventListener('click', () => seekVideo(seg.start_ms));
    sourcesDiv.appendChild(chip);
  });

  msgEl.appendChild(sourcesDiv);
}

// ─── NEW ANALYSIS ─────────────────────────────────────────────────────────────
function resetState() {
  clearTimeout(state.pollTimer);
  state.sessionId = null;
  state.videoFile = null;
  state.sourceUrl = null;
  state.transcript = [];
  state.analysis = null;
  state.pollTimer = null;
  state.fillerSet.clear();
  state.techSet.clear();

  destroyCharts();

  $('rag-messages').innerHTML = '';
  $('rag-input').value = '';
  $('rag-send-btn').disabled = true;
  $('topics-timeline').innerHTML = '';
  $('section-topics').style.display = 'none';

  $('file-input').value = '';
  $('url-input').value = '';
  hide('file-preview');
  hide('upload-progress');
  hide('upload-error');
  $('upload-btn').disabled = true;
  $('upload-bar').style.width = '0%';
  $('upload-pct').textContent = 'Uploading… 0%';

  const video = $('video-player');
  video.pause();
  URL.revokeObjectURL(video.src);
  video.src = '';

  $('youtube-iframe').src = '';
  $('youtube-panel').classList.add('hidden');
  $('video-panel').classList.remove('hidden');

  setUploadMode('file');
}

// ─── BOOT ────────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  showScreen('upload'); // set initial visible screen

  setupTabs();
  setupDropZone();
  setupTranscriptSearch();
  setupVideoSync(); // register once; reads state.transcript at event time
  setupRagPanel();

  $('export-txt').addEventListener('click', exportTxt);
  $('export-pdf').addEventListener('click', exportPdf);

  $('new-analysis-btn').addEventListener('click', () => {
    resetState();
    showScreen('upload');
  });

  $('retry-btn').addEventListener('click', () => {
    resetState();
    showScreen('upload');
  });
});
