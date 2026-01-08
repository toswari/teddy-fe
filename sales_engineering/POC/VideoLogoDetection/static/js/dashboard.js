const projectsEndpoint = '/api/projects';
const metricsEndpoint = '/api/metrics';

const state = {
  activeProject: null,
  videos: new Map(),
  metrics: null,
  palettes: new Map(),
  comparison: {
    videoId: null,
    runId: null,
    modelA: null,
    modelB: null,
    activeToggle: 'A',
    frameIndex: 0,
    frames: [],
    models: [],
  },
};

const elements = {
  activeProject: document.getElementById('active-project'),
  projectDescription: document.getElementById('project-description'),
  videoList: document.getElementById('video-list'),
  costPill: document.getElementById('cost-pill'),
  inferenceCards: document.getElementById('inference-cards'),
  efficiencyRows: document.getElementById('efficiency-rows'),
  benchmarkUpdated: document.getElementById('benchmark-updated'),
  comparisonVideo: document.getElementById('comparison-video'),
  comparisonRun: document.getElementById('comparison-run'),
  comparisonModelA: document.getElementById('comparison-model-a'),
  comparisonModelB: document.getElementById('comparison-model-b'),
  frameSlider: document.getElementById('frame-slider'),
  frameLabel: document.getElementById('frame-label'),
  framePlaceholder: document.getElementById('frame-placeholder'),
  detectionList: document.getElementById('detection-list'),
  overlayLayer: document.getElementById('overlay-layer'),
  modelToggleButtons: document.querySelectorAll('button[data-toggle="model"]'),
};

const socket = window.io ? window.io() : null;

function isDashboardPage() {
  return Boolean(elements.videoList && elements.inferenceCards);
}

function formatSecondsToClock(value) {
  if (!Number.isFinite(value)) {
    return '0:00';
  }
  const total = Math.max(0, Math.floor(value));
  const hours = Math.floor(total / 3600);
  const minutes = Math.floor((total % 3600) / 60);
  const seconds = total % 60;
  if (hours) {
    return `${hours}:${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`;
  }
  return `${minutes}:${String(seconds).padStart(2, '0')}`;
}

function describePreprocessWindow(video) {
  if (!video) {
    return 'Window: full video';
  }
  const metadata = video.video_metadata || {};
  const windowMeta = metadata.last_preprocess_window;
  const totalDuration = Number.isFinite(video.duration_seconds) ? video.duration_seconds : undefined;
  const clipCount = Number.isFinite(windowMeta?.clip_count) ? windowMeta.clip_count : undefined;
  const clipLength = Number.isFinite(windowMeta?.clip_length) ? windowMeta.clip_length : undefined;
  const clipSummaryParts = [];
  if (clipCount !== undefined) {
    clipSummaryParts.push(`${clipCount} clips`);
  }
  if (clipLength !== undefined) {
    clipSummaryParts.push(`@ ${clipLength}s`);
  }
  const clipSummary = clipSummaryParts.length ? ` (${clipSummaryParts.join(' ')})` : '';

  if (!windowMeta) {
    return `Window: full video${clipSummary}`;
  }

  const start = Number.isFinite(windowMeta.start) ? windowMeta.start : 0;
  const duration = Number.isFinite(windowMeta.duration) ? windowMeta.duration : 0;
  const end = Number.isFinite(windowMeta.end) ? windowMeta.end : start + duration;
  const coversFull = start === 0 && totalDuration && Math.abs(totalDuration - duration) <= 1;

  if (coversFull) {
    return `Window: full video${clipSummary}`;
  }

  return `Window: ${formatSecondsToClock(start)} → ${formatSecondsToClock(end)}${clipSummary}`;
}

async function fetchJSON(url, options = {}) {
  const response = await fetch(url, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });
  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(errorText || 'Request failed');
  }
  return response.json();
}

function safeSetText(element, text) {
  if (element) {
    element.textContent = text;
  }
}

function renderActiveProject(project) {
  safeSetText(elements.activeProject, project.name);
  safeSetText(elements.projectDescription, project.description || 'No description provided.');
}

function clearContainer(container) {
  if (!container) return;
  while (container.firstChild) {
    container.removeChild(container.firstChild);
  }
}

function videoLabel(video) {
  if (video.name) {
    return video.name;
  }
  const path = video.storage_path || video.original_path;
  if (!path) {
    return `Video ${video.id}`;
  }
  const segments = path.split(/[\\/]/);
  const leaf = segments.pop();
  return leaf || `Video ${video.id}`;
}

function createVideoCard(video) {
  const li = document.createElement('li');
  li.className = 'rounded-xl border border-slate-200 p-4 transition';
  li.dataset.videoId = video.id;
  if (state.comparison.videoId === video.id) {
    li.classList.add('ring-2', 'ring-slate-400');
  }
  li.addEventListener('click', () => handleVideoCardSelection(video.id));

  const header = document.createElement('div');
  header.className = 'flex items-center justify-between';

  const title = document.createElement('h4');
  title.className = 'text-lg font-semibold';
  title.textContent = videoLabel(video);
  header.appendChild(title);

  const statusPill = document.createElement('span');
  statusPill.className = 'rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold text-slate-700';
  statusPill.textContent = video.status;
  statusPill.dataset.role = 'status-pill';
  header.appendChild(statusPill);

  li.appendChild(header);

  const meta = document.createElement('p');
  meta.className = 'mt-2 text-sm text-slate-500';
  meta.textContent = video.storage_path || video.original_path || 'No path recorded';
  li.appendChild(meta);

  const windowInfo = document.createElement('p');
  windowInfo.className = 'mt-1 text-xs text-slate-500';
  windowInfo.dataset.role = 'window-info';
  windowInfo.textContent = describePreprocessWindow(video);
  li.appendChild(windowInfo);

  const actions = document.createElement('div');
  actions.className = 'mt-4 flex flex-wrap gap-3 text-sm';

  const preprocessButton = document.createElement('button');
  preprocessButton.className = 'rounded-full border border-slate-300 px-3 py-1 hover:bg-slate-100';
  preprocessButton.textContent = 'Preprocess';
  preprocessButton.addEventListener('click', (event) => {
    event.stopPropagation();
    triggerPreprocess(video.id);
  });
  actions.appendChild(preprocessButton);

  const inferenceButton = document.createElement('button');
  inferenceButton.className = 'rounded-full bg-slate-900 px-3 py-1 font-medium text-white hover:bg-slate-700';
  inferenceButton.textContent = 'Run Inference';
  inferenceButton.addEventListener('click', (event) => {
    event.stopPropagation();
    triggerInference(video.id);
  });
  actions.appendChild(inferenceButton);

  const reportButton = document.createElement('button');
  reportButton.className = 'rounded-full border border-emerald-500 px-3 py-1 text-emerald-600 hover:bg-emerald-50';
  reportButton.textContent = 'Generate Report';
  reportButton.addEventListener('click', (event) => {
    event.stopPropagation();
    triggerReport(video.id);
  });
  actions.appendChild(reportButton);

  li.appendChild(actions);

  const runsContainer = document.createElement('div');
  runsContainer.className = 'mt-4 space-y-2 text-sm';
  runsContainer.dataset.role = 'runs-container';
  li.appendChild(runsContainer);

  populateInferenceRuns(li, video.inference_runs || []);

  return li;
}

function populateInferenceRuns(container, runs) {
  const runsContainer = container.querySelector('[data-role="runs-container"]');
  clearContainer(runsContainer);
  if (!runs?.length) {
    const empty = document.createElement('p');
    empty.className = 'text-slate-400';
    empty.textContent = 'No inference runs yet.';
    runsContainer.appendChild(empty);
    return;
  }
  runs.forEach((run) => {
    const card = document.createElement('div');
    card.className = 'rounded-lg bg-slate-50 p-3';
    const detectionsCount = (run.results?.detections || []).length;
    card.innerHTML = `
      <div class="flex items-center justify-between">
        <span class="font-medium">Run #${run.id}</span>
        <span class="text-xs uppercase tracking-wide text-slate-500">${run.status}</span>
      </div>
      <p class="mt-1 text-xs text-slate-500">Models: ${(run.model_ids || []).join(', ') || '—'}</p>
      <p class="mt-1 text-xs text-slate-500">Detections: ${detectionsCount}</p>
    `;
    runsContainer.appendChild(card);
  });
}

function updateSelectedVideoHighlight() {
  if (!elements.videoList) return;
  document.querySelectorAll('#video-list li').forEach((item) => {
    const isSelected = Number(item.dataset.videoId) === state.comparison.videoId;
    item.classList.toggle('ring-2', isSelected);
    item.classList.toggle('ring-slate-400', isSelected);
  });
}

function renderInferenceCards(metrics) {
  if (!elements.inferenceCards) return;
  clearContainer(elements.inferenceCards);
  const entries = Object.entries(metrics.models || {});
  if (!entries.length) {
    const placeholder = document.createElement('div');
    placeholder.className = 'rounded-xl border border-dashed border-slate-200 p-6 text-center text-sm text-slate-400';
    placeholder.textContent = 'No inference metrics yet. Run an inference to populate this section.';
    elements.inferenceCards.appendChild(placeholder);
    return;
  }
  entries
    .sort(([, a], [, b]) => (b.detections || 0) - (a.detections || 0))
    .forEach(([modelId, data]) => {
      const card = document.createElement('div');
      card.className = 'rounded-xl border border-slate-200 p-4';
      card.innerHTML = `
        <div class="flex items-center justify-between">
          <h4 class="text-base font-semibold">${modelId}</h4>
          <span class="text-xs text-slate-500">${data.detections} detections</span>
        </div>
        <dl class="mt-3 grid grid-cols-2 gap-2 text-xs text-slate-600">
          <div><dt class="uppercase tracking-wide">Avg Confidence</dt><dd class="font-medium">${Number(data.avg_confidence || 0).toFixed(3)}</dd></div>
          <div><dt class="uppercase tracking-wide">Hit Frequency</dt><dd class="font-medium">${Number(data.hit_frequency || 0).toFixed(2)}</dd></div>
          <div><dt class="uppercase tracking-wide">Cost (Actual)</dt><dd class="font-medium">$${Number(data.cost_actual || 0).toFixed(2)}</dd></div>
          <div><dt class="uppercase tracking-wide">Density</dt><dd class="font-medium">${Number(data.detection_density || 0).toFixed(4)}</dd></div>
        </dl>
      `;
      elements.inferenceCards.appendChild(card);
    });
}

function renderEfficiencyMatrix(metrics) {
  if (!elements.efficiencyRows) return;
  clearContainer(elements.efficiencyRows);
  const entries = Object.entries(metrics.models || {});
  if (!entries.length) {
    const row = document.createElement('tr');
    const cell = document.createElement('td');
    cell.colSpan = 7;
    cell.className = 'py-4 text-sm text-slate-400';
    cell.textContent = 'No benchmark data yet.';
    row.appendChild(cell);
    elements.efficiencyRows.appendChild(row);
    if (elements.benchmarkUpdated) {
      elements.benchmarkUpdated.textContent = '';
    }
    return;
  }

  entries
    .sort(([, a], [, b]) => (b.detection_density || 0) - (a.detection_density || 0))
    .forEach(([modelId, data]) => {
      const row = document.createElement('tr');
      row.className = 'text-sm';
      row.innerHTML = `
        <td class="py-3 pr-3 font-semibold text-slate-700">${modelId}</td>
        <td class="py-3">${data.detections}</td>
        <td class="py-3">${Number(data.avg_confidence || 0).toFixed(3)}</td>
        <td class="py-3">${Number(data.hit_frequency || 0).toFixed(2)}</td>
        <td class="py-3">${Number(data.detection_density || 0).toFixed(4)}</td>
        <td class="py-3">$${Number(data.cost_actual || 0).toFixed(2)}</td>
        <td class="py-3">$${Number(data.cost_projected || 0).toFixed(2)}</td>
      `;
      elements.efficiencyRows.appendChild(row);
    });

  if (elements.benchmarkUpdated) {
    elements.benchmarkUpdated.textContent = `Updated ${new Date().toLocaleTimeString()}`;
  }
}

function updateCostPill(metrics) {
  if (!elements.costPill) return;
  const total = Object.values(metrics.models || {}).reduce((acc, value) => acc + (value.cost_projected || 0), 0);
  elements.costPill.textContent = `$${total.toFixed(2)} projected`;
}

function getVideosArray() {
  return Array.from(state.videos.values());
}

async function loadVideos(projectId) {
  const videos = await fetchJSON(`/api/projects/${projectId}/videos`);
  state.videos.clear();
  if (!elements.videoList) {
    return;
  }
  clearContainer(elements.videoList);
  videos.forEach((video) => {
    state.videos.set(video.id, video);
    elements.videoList.appendChild(createVideoCard(video));
  });
  updateSelectedVideoHighlight();
  updateComparisonVideoOptions(state.comparison.videoId === null);
}

async function loadInferenceSummary(projectId) {
  try {
    const metrics = await fetchJSON(`${metricsEndpoint}/projects/${projectId}`);
    state.metrics = metrics;
    updateCostPill(metrics);
    renderInferenceCards(metrics);
    renderEfficiencyMatrix(metrics);
  } catch (error) {
    console.warn('Metrics not available yet', error);
    state.metrics = { project_id: projectId, models: {} };
    updateCostPill(state.metrics);
    renderInferenceCards(state.metrics);
    renderEfficiencyMatrix(state.metrics);
  }
}

async function loadProjects() {
  const projects = await fetchJSON(projectsEndpoint);
  if (!projects.length) {
    safeSetText(elements.activeProject, 'No projects yet');
    resetComparisonDisplay('Create a project to begin');
    return;
  }
  state.activeProject = projects[0];
  renderActiveProject(state.activeProject);
  await loadVideos(state.activeProject.id);
  await loadInferenceSummary(state.activeProject.id);
}

async function triggerPreprocess(videoId) {
  const projectId = state.activeProject?.id;
  if (!projectId) return;
  const promptMessage = 'Enter preprocess window as start,duration[,clip] in seconds (e.g., "120,1800" or "60,600,30"). Leave blank for full video.';
  const input = window.prompt(promptMessage, '');
  if (input === null) {
    return;
  }
  const payload = {};
  if (input.trim() !== '') {
    const parts = input.split(',').map((part) => part.trim());
    if (parts[0]) {
      const startValue = Number(parts[0]);
      if (!Number.isFinite(startValue) || startValue < 0) {
        window.alert('Start time must be a non-negative number.');
        return;
      }
      payload.start_seconds = startValue;
    }
    if (parts.length >= 2 && parts[1]) {
      const durationValue = Number(parts[1]);
      if (!Number.isFinite(durationValue) || durationValue <= 0) {
        window.alert('Duration must be a positive number.');
        return;
      }
      payload.duration_seconds = durationValue;
    }
    if (parts.length >= 3 && parts[2]) {
      const clipLengthValue = Number(parts[2]);
      if (!Number.isFinite(clipLengthValue) || clipLengthValue <= 0) {
        window.alert('Clip length must be a positive number.');
        return;
      }
      payload.clip_length = Math.round(clipLengthValue);
    }
  }
  try {
    await fetchJSON(`/api/projects/${projectId}/videos/${videoId}/preprocess`, {
      method: 'POST',
      body: JSON.stringify(payload),
    });
    await refreshVideo(videoId);
  } catch (error) {
    window.alert(`Preprocess failed: ${error.message}`);
  }
}

async function triggerInference(videoId) {
  const projectId = state.activeProject?.id;
  if (!projectId) return;
  const modelInput = window.prompt('Enter Clarifai model IDs (comma separated)', 'general-image-recognition');
  const modelIds = modelInput ? modelInput.split(',').map((m) => m.trim()).filter(Boolean) : undefined;
  try {
    const payload = modelIds ? { model_ids: modelIds } : {};
    await fetchJSON(`/api/projects/${projectId}/videos/${videoId}/multi-inference`, {
      method: 'POST',
      body: JSON.stringify(payload),
    });
    await refreshVideo(videoId);
    await loadInferenceSummary(projectId);
  } catch (error) {
    window.alert(`Inference failed: ${error.message}`);
  }
}

async function triggerReport(videoId) {
  const projectId = state.activeProject?.id;
  if (!projectId) return;
  try {
    const response = await fetchJSON(`/api/projects/${projectId}/videos/${videoId}/report`, {
      method: 'POST',
    });
    window.alert(`Report created: ${response.report_path}`);
  } catch (error) {
    window.alert(`Report failed: ${error.message}`);
  }
}

async function refreshVideo(videoId) {
  const projectId = state.activeProject?.id;
  if (!projectId) return;
  const status = await fetchJSON(`/api/projects/${projectId}/videos/${videoId}/status`);
  const existing = state.videos.get(videoId) || {};
  const updated = {
    ...existing,
    status: status.status,
    metadata: status.video_metadata ?? existing.video_metadata,
    duration_seconds: status.duration_seconds ?? existing.duration_seconds,
    resolution: status.resolution ?? existing.resolution,
    inference_runs: status.inference_runs,
  };
  state.videos.set(videoId, updated);

  const card = document.querySelector(`[data-video-id="${videoId}"]`);
  if (card) {
    const pill = card.querySelector('[data-role="status-pill"]');
    if (pill) {
      pill.textContent = status.status;
    }
    populateInferenceRuns(card, status.inference_runs || []);
    const windowInfo = card.querySelector('[data-role="window-info"]');
    if (windowInfo) {
      windowInfo.textContent = describePreprocessWindow(updated);
    }
  }
  updateSelectedVideoHighlight();
  updateComparisonVideoOptions(false);
  if (state.comparison.videoId === videoId) {
    void handleVideoSelection(videoId, { preserveRun: true, preserveModels: true });
  }
}

function updateComparisonVideoOptions(initial = false) {
  if (!elements.comparisonVideo) return;
  const videos = getVideosArray();
  const placeholderText = elements.comparisonVideo.dataset.placeholder || 'Select video';
  clearContainer(elements.comparisonVideo);
  const placeholder = document.createElement('option');
  placeholder.value = '';
  placeholder.textContent = placeholderText;
  elements.comparisonVideo.appendChild(placeholder);

  videos.forEach((video) => {
    const option = document.createElement('option');
    option.value = String(video.id);
    option.textContent = videoLabel(video);
    elements.comparisonVideo.appendChild(option);
  });

  elements.comparisonVideo.disabled = videos.length === 0;

  if (!videos.length) {
    elements.comparisonVideo.value = '';
    state.comparison.videoId = null;
    resetComparisonDisplay('Register a video to view detections');
    return;
  }

  if (state.comparison.videoId && videos.some((video) => video.id === state.comparison.videoId)) {
    elements.comparisonVideo.value = String(state.comparison.videoId);
  } else if (initial) {
    const defaultVideo = videos.find((video) => (video.inference_runs || []).length) || videos[0];
    if (defaultVideo) {
      state.comparison.videoId = defaultVideo.id;
      elements.comparisonVideo.value = String(defaultVideo.id);
      void handleVideoSelection(defaultVideo.id);
    }
  } else {
    elements.comparisonVideo.value = '';
  }
}

function handleVideoCardSelection(videoId) {
  if (state.comparison.videoId === videoId) {
    return;
  }
  state.comparison.videoId = videoId;
  updateSelectedVideoHighlight();
  if (elements.comparisonVideo) {
    elements.comparisonVideo.value = String(videoId);
  }
  void handleVideoSelection(videoId);
}

async function handleVideoSelection(videoId, { preserveRun = false, preserveModels = false } = {}) {
  if (!elements.comparisonRun) return;
  if (!videoId) {
    state.comparison.videoId = null;
    populateRunSelect([]);
    resetComparisonDisplay('Select a video to inspect detections');
    return;
  }

  state.comparison.videoId = Number(videoId);
  updateSelectedVideoHighlight();

  const selectedRunId = await loadComparisonRuns(state.comparison.videoId, { preserveSelection: preserveRun });
  if (selectedRunId) {
    await handleRunSelection(selectedRunId, { preserveModels });
  } else {
    populateModelSelects([]);
    resetComparisonDisplay('No inference runs yet');
  }
}

async function loadComparisonRuns(videoId, { preserveSelection = false } = {}) {
  const projectId = state.activeProject?.id;
  if (!projectId) return null;
  const status = await fetchJSON(`/api/projects/${projectId}/videos/${videoId}/status`);
  const existing = state.videos.get(videoId) || {};
  state.videos.set(videoId, { ...existing, status: status.status, inference_runs: status.inference_runs });

  return populateRunSelect(status.inference_runs || [], { preserveSelection });
}

function populateRunSelect(runs, { preserveSelection = false } = {}) {
  if (!elements.comparisonRun) return null;
  const placeholderText = elements.comparisonRun.dataset.placeholder || 'Select run';
  clearContainer(elements.comparisonRun);
  const placeholder = document.createElement('option');
  placeholder.value = '';
  placeholder.textContent = placeholderText;
  elements.comparisonRun.appendChild(placeholder);

  let selectedRunId = null;
  if (preserveSelection && runs.some((run) => run.id === state.comparison.runId)) {
    selectedRunId = state.comparison.runId;
  } else {
    const completed = runs.find((run) => run.status === 'completed');
    selectedRunId = completed ? completed.id : runs[0]?.id ?? null;
  }

  runs.forEach((run) => {
    const option = document.createElement('option');
    option.value = String(run.id);
    const createdAt = run.created_at ? new Date(run.created_at).toLocaleString() : '';
    option.textContent = `Run #${run.id} – ${run.status}${createdAt ? ` · ${createdAt}` : ''}`;
    elements.comparisonRun.appendChild(option);
  });

  elements.comparisonRun.disabled = runs.length === 0;

  if (selectedRunId) {
    elements.comparisonRun.value = String(selectedRunId);
    state.comparison.runId = selectedRunId;
  } else {
    elements.comparisonRun.value = '';
    state.comparison.runId = null;
  }

  return selectedRunId;
}

async function handleRunSelection(runId, { preserveModels = false } = {}) {
  if (!runId) {
    state.comparison.runId = null;
    populateModelSelects([]);
    resetComparisonDisplay('Select an inference run');
    return;
  }
  const projectId = state.activeProject?.id;
  const videoId = state.comparison.videoId;
  if (!projectId || !videoId) return;

  const payload = await fetchJSON(`/api/projects/${projectId}/videos/${videoId}/runs/${runId}/detections`);
  const frames = enrichFrames(payload);

  state.comparison.runId = Number(runId);
  state.comparison.frames = frames;
  state.comparison.models = payload.models || [];

  updateModelSelections(payload.models || [], { preserveModels });
  renderOverlay();
}

function enrichFrames(payload) {
  const framesByKey = new Map();

  (payload.frames || []).forEach((frame) => {
    const key = frame.frame_index ?? -1;
    framesByKey.set(key, { ...frame, models: {} });
  });

  (payload.detections || []).forEach((detection) => {
    const key = detection.frame_index ?? -1;
    if (!framesByKey.has(key)) {
      framesByKey.set(key, {
        frame_index: detection.frame_index,
        timestamp_seconds: detection.timestamp_seconds,
        models: {},
      });
    }
    const entry = framesByKey.get(key);
    const modelId = detection.model_id || 'unknown';
    if (!entry.models[modelId]) {
      entry.models[modelId] = [];
    }
    entry.models[modelId].push(detection);
  });

  if ((payload.frames || []).length) {
    return payload.frames.map((frame) => {
      const key = frame.frame_index ?? -1;
      const entry = framesByKey.get(key) || { ...frame, models: {} };
      entry.models = entry.models || {};
      return entry;
    });
  }

  return Array.from(framesByKey.values()).sort((a, b) => {
    const aIdx = a.frame_index ?? Number.MAX_SAFE_INTEGER;
    const bIdx = b.frame_index ?? Number.MAX_SAFE_INTEGER;
    return aIdx - bIdx;
  });
}

function updateModelSelections(models, { preserveModels = false } = {}) {
  if (!models.length) {
    state.comparison.modelA = null;
    state.comparison.modelB = null;
    state.comparison.activeToggle = 'A';
    populateModelSelects([]);
    resetComparisonDisplay('No detections captured yet');
    return;
  }

  if (!preserveModels) {
    state.palettes.clear();
    models.forEach((modelId) => getModelColor(modelId));
  }

  if (!preserveModels || !models.includes(state.comparison.modelA)) {
    state.comparison.modelA = models[0] || null;
  }
  if (!preserveModels || !models.includes(state.comparison.modelB)) {
    state.comparison.modelB = models[1] || state.comparison.modelA || null;
  }

  if (state.comparison.activeToggle === 'A' && !state.comparison.modelA) {
    state.comparison.activeToggle = 'B';
  } else if (state.comparison.activeToggle === 'B' && !state.comparison.modelB) {
    state.comparison.activeToggle = 'A';
  }

  state.comparison.frameIndex = 0;
  populateModelSelects(models);
}

function populateModelSelects(models) {
  setSelectOptions(elements.comparisonModelA, models, state.comparison.modelA);
  setSelectOptions(elements.comparisonModelB, models, state.comparison.modelB);
  updateModelToggleAvailability();
}

function setSelectOptions(selectEl, values, selected) {
  if (!selectEl) return;
  const placeholderText = selectEl.dataset.placeholder || 'Select';
  clearContainer(selectEl);
  const placeholder = document.createElement('option');
  placeholder.value = '';
  placeholder.textContent = placeholderText;
  selectEl.appendChild(placeholder);

  values.forEach((value) => {
    const option = document.createElement('option');
    option.value = value;
    option.textContent = value;
    selectEl.appendChild(option);
  });

  if (selected && values.includes(selected)) {
    selectEl.value = selected;
  } else {
    selectEl.value = '';
  }

  selectEl.disabled = !values.length;
}

function updateModelToggleAvailability() {
  if (!elements.modelToggleButtons) return;
  elements.modelToggleButtons.forEach((button) => {
    const slot = button.dataset.model;
    const modelId = slot === 'A' ? state.comparison.modelA : state.comparison.modelB;
    const baseLabel = button.dataset.label || button.textContent || slot;
    const suffix = modelId ? ` · ${modelId}` : '';
    button.textContent = `${baseLabel}${suffix}`;
    if (!modelId) {
      button.disabled = true;
      button.classList.remove('active');
    } else {
      button.disabled = false;
      button.classList.toggle('active', state.comparison.activeToggle === slot);
    }
  });
}

function renderOverlay() {
  if (!elements.frameSlider || !elements.overlayLayer) return;
  const frames = state.comparison.frames;
  if (!frames.length) {
    resetComparisonDisplay('No frames available');
    return;
  }

  const clampedIndex = Math.max(0, Math.min(state.comparison.frameIndex ?? 0, frames.length - 1));
  const frame = frames[clampedIndex];
  state.comparison.frameIndex = clampedIndex;

  const models = frame.models || {};
  const primaryModel = state.comparison.activeToggle === 'A' ? state.comparison.modelA : state.comparison.modelB;
  const overlayDetections = primaryModel ? models[primaryModel] || [] : [];

  renderDetectionList(frame, models);
  drawOverlay(frame, overlayDetections);

  elements.frameSlider.max = String(Math.max(0, frames.length - 1));
  elements.frameSlider.value = String(clampedIndex);
  elements.frameSlider.disabled = frames.length <= 1;
  if (elements.frameLabel) {
    elements.frameLabel.textContent = `Frame ${frame.frame_index ?? '—'} · ${formatTimestamp(frame.timestamp_seconds)}`;
  }
}

function renderDetectionList(frame, models) {
  if (!elements.detectionList) return;
  clearContainer(elements.detectionList);

  const frameInfo = document.createElement('div');
  frameInfo.className = 'text-sm text-slate-500 mb-2';
  const frameLabel = frame?.frame_index ?? '—';
  const timestamp = formatTimestamp(frame?.timestamp_seconds);
  frameInfo.textContent = `Frame ${frameLabel} · ${timestamp} · ${Object.keys(models).length} models`;
  elements.detectionList.appendChild(frameInfo);

  const entries = Object.entries(models);
  if (!entries.length) {
    const empty = document.createElement('div');
    empty.className = 'text-sm text-slate-500 italic';
    empty.textContent = 'No detections for this frame';
    elements.detectionList.appendChild(empty);
    return;
  }

  entries.forEach(([modelId, detections]) => {
    const container = document.createElement('div');
    container.className = 'mb-3';

    const title = document.createElement('div');
    title.className = 'text-sm font-medium text-slate-700 flex items-center justify-between';
    title.textContent = `${modelId} (${detections.length})`;
    container.appendChild(title);

    const list = document.createElement('ul');
    list.className = 'space-y-1 mt-1';

    detections.forEach((det) => {
      const item = document.createElement('li');
      item.className = 'flex items-center justify-between gap-2 rounded border border-slate-200 px-2 py-1 text-xs text-slate-600';
      const confidence = det.confidence != null ? `${Math.round(det.confidence * 100)}%` : 'n/a';
      const label = det.label || det.object_name || 'Detection';

      const leftGroup = document.createElement('span');
      leftGroup.className = 'flex items-center gap-2';

      const badge = document.createElement('span');
      badge.className = 'inline-block h-2.5 w-2.5 rounded-full';
      badge.style.backgroundColor = getModelColor(det.model_id || modelId);
      leftGroup.appendChild(badge);

      const labelText = document.createElement('span');
      labelText.className = 'font-medium';
      labelText.textContent = label;
      leftGroup.appendChild(labelText);

      const confidenceSpan = document.createElement('span');
      confidenceSpan.className = 'font-medium text-slate-500';
      confidenceSpan.textContent = confidence;

      item.appendChild(leftGroup);
      item.appendChild(confidenceSpan);
      list.appendChild(item);
    });

    container.appendChild(list);
    elements.detectionList.appendChild(container);
  });
}

function resetComparisonDisplay(message) {
  if (elements.overlayLayer) {
    clearContainer(elements.overlayLayer);
  }
  if (elements.detectionList) {
    clearContainer(elements.detectionList);
    if (message) {
      const empty = document.createElement('div');
      empty.className = 'text-sm text-slate-500 italic';
      empty.textContent = message;
      elements.detectionList.appendChild(empty);
    }
  }
  if (elements.frameSlider) {
    elements.frameSlider.value = '0';
    elements.frameSlider.disabled = true;
  }
  if (elements.frameLabel) {
    elements.frameLabel.textContent = 'Frame —';
  }
  if (elements.modelToggleButtons) {
    elements.modelToggleButtons.forEach((button) => {
      button.classList.remove('active');
    });
  }
}

function handleFrameChange(event) {
  const frames = state.comparison.frames;
  if (!frames.length) return;
  const nextIndex = Number(event.target.value);
  state.comparison.frameIndex = Number.isNaN(nextIndex) ? 0 : nextIndex;
  renderOverlay();
}

function setComparisonModel(slot, value) {
  if (slot === 'A') {
    state.comparison.modelA = value || null;
  } else if (slot === 'B') {
    state.comparison.modelB = value || null;
  }
  if (!value && state.comparison.activeToggle === slot) {
    state.comparison.activeToggle = slot === 'A' ? 'B' : 'A';
  }
  updateModelToggleAvailability();
  renderOverlay();
}

function drawOverlay(frame, detections) {
  if (!elements.overlayLayer) return;
  clearContainer(elements.overlayLayer);
  if (!detections.length) {
    const fallback = document.createElement('div');
    fallback.className = 'absolute inset-0 flex items-center justify-center text-xs text-slate-400';
    fallback.textContent = 'No detections for this model on this frame';
    elements.overlayLayer.appendChild(fallback);
    return;
  }

  let conceptOffset = 0;

  detections.forEach((det) => {
    const label = det.label || 'Detection';
    const confidenceText = `${Math.round((det.confidence ?? 0) * 100)}%`;
    const bbox = det.bbox || {};
    const hasBox = ['top', 'left', 'bottom', 'right'].every((key) => Number.isFinite(Number(bbox[key])));

    const top = Math.max(0, Math.min(1, Number(bbox.top ?? 0))) * 100;
    const left = Math.max(0, Math.min(1, Number(bbox.left ?? 0))) * 100;
    const bottom = Math.max(0, Math.min(1, Number(bbox.bottom ?? 0))) * 100;
    const right = Math.max(0, Math.min(1, Number(bbox.right ?? 0))) * 100;
    const height = Math.max(0, bottom - top);
    const width = Math.max(0, right - left);

    const box = document.createElement('div');
    box.className = 'bbox';
    box.textContent = `${label} · ${confidenceText}`;
    const sourceModel = det.model_id || state.comparison.activeToggle;
    const accent = getModelColor(sourceModel);
    box.style.setProperty('--bbox-color', accent);
    box.style.borderColor = accent;
    box.style.backgroundColor = 'rgba(15, 23, 42, 0.35)';

    if (hasBox && width > 0 && height > 0) {
      box.style.top = `${top}%`;
      box.style.left = `${left}%`;
      box.style.width = `${width}%`;
      box.style.height = `${height}%`;
    } else {
      box.style.top = `${5 + conceptOffset}%`;
      box.style.left = '5%';
      box.style.right = 'auto';
      box.style.width = 'auto';
      box.style.height = 'auto';
      conceptOffset += 10;
    }

    elements.overlayLayer.appendChild(box);
  });
}

function formatTimestamp(seconds) {
  if (seconds == null || Number.isNaN(Number(seconds))) {
    return '—';
  }
  const total = Math.max(0, Number(seconds));
  const minutes = Math.floor(total / 60)
    .toString()
    .padStart(2, '0');
  const secondsPart = total - Math.floor(total / 60) * 60;
  const decimals = secondsPart % 1 === 0 ? 0 : 1;
  const secondsDisplay = secondsPart
    .toFixed(decimals)
    .padStart(decimals ? 4 : 2, '0');
  return `${minutes}:${secondsDisplay}`;
}

const accentPalette = [
  '#2563eb',
  '#d97706',
  '#059669',
  '#7c3aed',
  '#db2777',
  '#0891b2',
  '#f97316',
  '#14b8a6',
  '#60a5fa',
  '#a855f7',
];

function getModelColor(modelId) {
  const key = modelId || 'default';
  if (state.palettes.has(key)) {
    return state.palettes.get(key);
  }
  const color = accentPalette[state.palettes.size % accentPalette.length];
  state.palettes.set(key, color);
  return color;
}

function setupComparisonControls() {
  if (elements.comparisonVideo) {
    elements.comparisonVideo.addEventListener('change', (event) => {
      const videoId = event.target.value ? Number(event.target.value) : null;
      void handleVideoSelection(videoId, { preserveRun: false, preserveModels: false });
    });
  }

  if (elements.comparisonRun) {
    elements.comparisonRun.addEventListener('change', (event) => {
      const runId = event.target.value ? Number(event.target.value) : null;
      void handleRunSelection(runId);
    });
  }

  if (elements.comparisonModelA) {
    elements.comparisonModelA.addEventListener('change', (event) => {
      const modelId = event.target.value || null;
      setComparisonModel('A', modelId);
    });
  }

  if (elements.comparisonModelB) {
    elements.comparisonModelB.addEventListener('change', (event) => {
      const modelId = event.target.value || null;
      setComparisonModel('B', modelId);
    });
  }

  if (elements.modelToggleButtons) {
    elements.modelToggleButtons.forEach((button) => {
      button.addEventListener('click', (event) => {
        event.preventDefault();
        const slot = button.dataset.model;
        if (!slot) return;
        const targetModel = slot === 'A' ? state.comparison.modelA : state.comparison.modelB;
        if (!targetModel) return;
        state.comparison.activeToggle = slot;
        updateModelToggleAvailability();
        renderOverlay();
      });
    });
  }

  if (elements.frameSlider) {
    elements.frameSlider.addEventListener('input', handleFrameChange);
    elements.frameSlider.disabled = true;
  }
}

function setupButtons() {
  const newProjectBtn = document.getElementById('new-project-btn');
  if (newProjectBtn) {
    newProjectBtn.addEventListener('click', async () => {
      const name = window.prompt('Project name');
      if (!name) return;
      const description = window.prompt('Project description') || '';
      await fetchJSON(projectsEndpoint, {
        method: 'POST',
        body: JSON.stringify({ name, description }),
      });
      await loadProjects();
    });
  }

  const uploadVideoBtn = document.getElementById('upload-video-btn');
  if (uploadVideoBtn) {
    uploadVideoBtn.addEventListener('click', async () => {
      const sourcePath = window.prompt('Enter path to local video file');
      if (!sourcePath) return;
      const projectId = state.activeProject?.id;
      if (!projectId) return;
      try {
        await fetchJSON(`/api/projects/${projectId}/videos`, {
          method: 'POST',
          body: JSON.stringify({ source_path: sourcePath }),
        });
        await loadVideos(projectId);
      } catch (error) {
        window.alert(`Video registration failed: ${error.message}`);
      }
    });
  }
}

function setupSocketListeners() {
  if (!socket) return;
  socket.on('preprocess_status', (event) => {
    if (event && event.video_id) {
      refreshVideo(event.video_id);
    }
  });
  socket.on('inference_status', (event) => {
    if (event && event.video_id) {
      refreshVideo(event.video_id);
      if (state.activeProject) {
        loadInferenceSummary(state.activeProject.id);
      }
      if (event.run_id && state.comparison.runId === event.run_id) {
        void handleRunSelection(event.run_id, { preserveModels: true });
      }
    }
  });
}

async function initDashboard() {
  try {
    setupComparisonControls();
    await loadProjects();
    setupButtons();
    setupSocketListeners();
  } catch (error) {
    console.error('Failed to initialise dashboard', error);
  }
}

initDashboard();
