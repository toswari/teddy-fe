const projectsEndpoint = '/api/projects';
const metricsEndpoint = '/api/metrics';

// Hardcoded Clarifai models for dropdowns
const HARDCODED_MODELS = [
  { id: 'logo-detection-v2', name: 'Logo Detection (V2)' },
  { id: 'logo-detection', name: 'Logo Detection (V1)' },
  { id: 'general-image-recognition', name: 'General Image Recognition' },
  { id: 'food-item-recognition', name: 'Food Recognition' },
  { id: 'apparel-detection', name: 'Apparel Detection' },
  { id: 'face-detection', name: 'Face Detection' },
  {
    id: 'https://clarifai.com/qwen/qwen-VL/models/Qwen2_5-VL-7B-Instruct/versions/0e5aefc37669445aa50f98786339f340/deployments/toswari-ai/deploy-qwen2_5-vl-7b-instruct-do8b',
    name: 'Qwen Logo Detection (Clarifai OpenAI)',
  },
];

const ZOOM_DEFAULT = 1;
const ZOOM_MIN = 1;
const ZOOM_MAX = 5;
const ZOOM_STEP = 0.25;

const state = {
  activeProject: null,
  videos: new Map(),
  clips: new Map(), // Map of clipId -> clip data
  metrics: null,
  palettes: new Map(),
  clarifaiModels: [],
  comparison: {
    clipId: null,
    videoId: null,
    runId: null,
    modelA: null,
    modelB: null,
    activeToggle: 'A',
    frameIndex: 0,
    frames: [],
    models: [],
    frameImages: new Map(),
    detectionsByModel: new Map(),
    zoom: {
      scale: ZOOM_DEFAULT,
      x: 0,
      y: 0,
    },
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
  runComparisonBtn: document.getElementById('run-comparison-btn'),
  frameSlider: document.getElementById('frame-slider'),
  frameLabel: document.getElementById('frame-label'),
  framePlaceholder: document.getElementById('frame-placeholder'),
  detectionList: document.getElementById('detection-list'),
  overlayLayer: document.getElementById('overlay-layer'),
  overlayCanvas: document.getElementById('overlay-canvas'),
  zoomContainer: document.getElementById('zoom-container'),
  zoomInBtn: document.getElementById('zoom-in-btn'),
  zoomOutBtn: document.getElementById('zoom-out-btn'),
  zoomResetBtn: document.getElementById('zoom-reset-btn'),
  modelToggleButtons: document.querySelectorAll('button[data-toggle="model"]'),
  exportRunBtn: document.getElementById('export-run-btn'),
};

syncExportRunButton();

if (elements.framePlaceholder) {
  elements.framePlaceholder.dataset.placeholderSrc = elements.framePlaceholder.src;
}

const socket = window.io ? window.io() : null;

let zoomControlsInitialized = false;
let panzoomInstance = null;

const delay = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

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

function truncateText(value, limit) {
  if (!value) {
    return '';
  }
  const text = String(value);
  if (text.length <= limit) {
    return text;
  }
  return `${text.slice(0, Math.max(0, limit - 1))}…`;
}

function summarizeClarifaiModel(model, index) {
  const name = model.name || model.id || `Model ${index + 1}`;
  const type = model.model_type ? ` · ${model.model_type}` : '';
  const description = truncateText(model.description, 80);
  const descriptionPart = description ? ` — ${description}` : '';
  return `${index + 1}. ${name} (${model.id})${type}${descriptionPart}`;
}

async function loadClarifaiModels(forceRefresh = false) {
  if (!forceRefresh && Array.isArray(state.clarifaiModels) && state.clarifaiModels.length) {
    return state.clarifaiModels;
  }

  try {
    // First try to load from local config file (faster and more reliable)
    try {
      const response = await fetchJSON('/api/clarifai/models/config');
      const models = Array.isArray(response.models) ? response.models : [];
      if (models.length > 0) {
        // Convert config format to match expected format
        state.clarifaiModels = models.map(m => ({
          id: m.model_id || m.id,
          name: m.name || m.model_id || m.id,
          model_type: m.model_type || 'visual-classifier',
          description: m.description || null,
          user_id: m.user_id || null,
          app_id: m.app_id || null,
          version_id: m.model_version_id || m.version_id || null,
        }));
        console.log('Loaded', state.clarifaiModels.length, 'models from config');
        return state.clarifaiModels;
      }
    } catch (configError) {
      console.debug('Config models not available, trying Clarifai API', configError);
    }

    // Fallback to Clarifai API
    const response = await fetchJSON('/api/clarifai/models?per_page=50');
    const models = Array.isArray(response.models) ? response.models : [];
    state.clarifaiModels = models;
    console.log('Loaded', state.clarifaiModels.length, 'models from Clarifai API');
    return models;
  } catch (error) {
    console.warn('Unable to load Clarifai models', error);
    state.clarifaiModels = [];
    throw error;
  }
}

function buildModelSelectionMessage(models) {
  if (!models.length) {
    return '';
  }
  return models.slice(0, 20).map((model, index) => summarizeClarifaiModel(model, index)).join('\n');
}

function parseModelSelectionInput(input, models) {
  if (!input) {
    return [];
  }
  const entries = input
    .split(',')
    .map((entry) => entry.trim())
    .filter(Boolean);
  if (!entries.length) {
    return [];
  }
  const ids = [];
  const seen = new Set();
  entries.forEach((entry) => {
    if (/^\d+$/.test(entry)) {
      const index = Number(entry) - 1;
      if (index >= 0 && index < models.length) {
        const id = models[index].id;
        if (id && !seen.has(id)) {
          ids.push(id);
          seen.add(id);
        }
      }
      return;
    }
    if (!seen.has(entry)) {
      ids.push(entry);
      seen.add(entry);
    }
  });
  return ids;
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

function triggerFileDownload(blob, filename) {
  const url = window.URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  document.body.removeChild(anchor);
  window.URL.revokeObjectURL(url);
}

async function fetchRunArchiveBlob({ runId, projectId = null, videoId = null, attempts = 5 }) {
  if (!runId) {
    throw new Error('Run ID is required for export.');
  }

  const endpoints = [];
  if (projectId && videoId) {
    endpoints.push(`/api/projects/${projectId}/videos/${videoId}/runs/${runId}/export`);
  }
  endpoints.push(`/api/reports/run/${runId}/download`);

  let lastError = null;
  for (const endpoint of endpoints) {
    try {
      return await attemptRunArchiveFetch(endpoint, attempts);
    } catch (error) {
      lastError = error;
      console.warn(`Run export via ${endpoint} failed`, error);
    }
  }
  throw lastError || new Error('Failed to export run.');
}

async function attemptRunArchiveFetch(endpoint, attempts) {
  for (let attempt = 0; attempt < attempts; attempt += 1) {
    const response = await fetch(endpoint);
    if (response.status === 202) {
      await delay(1500);
      continue;
    }
    if (!response.ok) {
      const message = await extractRunExportError(response);
      throw new Error(message);
    }
    return response.blob();
  }
  throw new Error('Export is still preparing. Please try again shortly.');
}

async function extractRunExportError(response) {
  const fallback = await response.text();
  if (!fallback) {
    return 'Failed to export run.';
  }
  try {
    const payload = JSON.parse(fallback);
    if (payload?.error) {
      return payload.error;
    }
  } catch (error) {
    // Ignore JSON parse errors and return the raw fallback string
  }
  return fallback;
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

function clipLabel(clip, videoOverride) {
  const video = videoOverride || state.videos.get(clip.videoId);
  const videoName = video ? videoLabel(video) : `Video ${clip.videoId}`;
  const segment = Number.isFinite(clip.segment) ? clip.segment : '—';
  const start = Number.isFinite(clip.start) ? formatSecondsToClock(clip.start) : '0:00';
  const end = Number.isFinite(clip.end) ? formatSecondsToClock(clip.end) : '—';
  return `${videoName} · Clip ${segment} (${start} → ${end})`;
}

function extractClipsFromVideos() {
  state.clips.clear();
  const videos = getVideosArray();
  
  videos.forEach((video) => {
    const clips = video.video_metadata?.clips || [];
    clips.forEach((clipData, index) => {
      const segment = clipData.segment || (index + 1);
      const clipId = `${video.id}-${segment}`;
      const clip = {
        id: clipId,
        videoId: video.id,
        path: clipData.path,
        start: clipData.start,
        end: clipData.end,
        segment,
        duration:
          Number.isFinite(clipData.end) && Number.isFinite(clipData.start)
            ? clipData.end - clipData.start
            : null,
      };
      clip.label = clipLabel(clip, video);
      state.clips.set(clipId, clip);
    });
  });
}

function getClipsArray() {
  return Array.from(state.clips.values());
}

function getClipsForVideo(videoId) {
  return getClipsArray().filter((clip) => clip.videoId === videoId);
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
    window.location.href = `/preprocess?project_id=${state.activeProject?.id}&video_id=${video.id}`;
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

  const deleteButton = document.createElement('button');
  deleteButton.className = 'rounded-full border border-red-500 px-3 py-1 text-red-600 hover:bg-red-50';
  deleteButton.textContent = 'Delete';
  deleteButton.addEventListener('click', (event) => {
    event.stopPropagation();
    deleteVideo(video.id);
  });
  actions.appendChild(deleteButton);

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
    const clipInfo = run.results?.clip;
    const clipText = clipInfo?.label || 'Full video';
    card.innerHTML = `
      <div class="flex items-center justify-between">
        <span class="font-medium">Run #${run.id}</span>
        <span class="text-xs uppercase tracking-wide text-slate-500">${run.status}</span>
      </div>
      <p class="mt-1 text-xs text-slate-500">Models: ${(run.model_ids || []).join(', ') || '—'}</p>
      <p class="mt-1 text-xs text-slate-500">Scope: ${clipText}</p>
      <p class="mt-1 text-xs text-slate-500">Detections: ${detectionsCount}</p>
    `;
    runsContainer.appendChild(card);
  });
}

function updateSelectedVideoHighlight() {
  if (!elements.videoList) return;
  const clip = state.comparison.clipId ? state.clips.get(state.comparison.clipId) : null;
  const selectedVideoId = clip ? clip.videoId : state.comparison.videoId;
  document.querySelectorAll('#video-list li').forEach((item) => {
    const isSelected = Number(item.dataset.videoId) === selectedVideoId;
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
    cell.colSpan = 9;
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
      const framesProcessed = Number(data.frames_processed || 0);
      const avgProcessingSeconds = Number(data.avg_processing_seconds || 0);
      row.innerHTML = `
        <td class="py-3 pr-3 font-semibold text-slate-700">${modelId}</td>
        <td class="py-3">${data.detections}</td>
        <td class="py-3">${Number(data.avg_confidence || 0).toFixed(3)}</td>
        <td class="py-3">${Number(data.hit_frequency || 0).toFixed(2)}</td>
        <td class="py-3">${Number(data.detection_density || 0).toFixed(4)}</td>
        <td class="py-3">${framesProcessed}</td>
        <td class="py-3">${formatSecondsToClock(avgProcessingSeconds)}</td>
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
  
  // Populate state first
  videos.forEach((video) => {
    state.videos.set(video.id, video);
  });
  
  // Extract clips from videos
  extractClipsFromVideos();
  
  // Update preprocessing tab video list (only exists on certain pages)
  const preprocessVideoList = document.getElementById('preprocess-video-list');
  if (preprocessVideoList) {
    console.log('Populating preprocessing video list with', videos.length, 'videos');
    clearContainer(preprocessVideoList);
    videos.forEach((video) => {
      preprocessVideoList.appendChild(createVideoCard(video));
    });
  }
  
  updateSelectedVideoHighlight();
  updateComparisonVideoOptions(state.comparison.clipId === null);
  
  // Update preprocessing dropdown if visible
  loadPreprocessingVideos();

  // Populate comparison dropdowns
  await populateComparisonDropdowns();
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

async function deleteVideo(videoId) {
  const projectId = state.activeProject?.id;
  if (!projectId) return;
  
  if (!window.confirm('Are you sure you want to delete this video? This action cannot be undone.')) {
    return;
  }
  
  try {
    const response = await fetch(`/api/projects/${projectId}/videos/${videoId}`, {
      method: 'DELETE',
    });
    
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.error || 'Delete failed');
    }
    
    // Remove from state
    state.videos.delete(videoId);
    
    // Remove from UI
    const card = document.querySelector(`[data-video-id="${videoId}"]`);
    if (card) {
      card.remove();
    }
    
    // Reload videos to update display
    await loadVideos(projectId);
  } catch (error) {
    window.alert(`Delete failed: ${error.message}`);
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
  extractClipsFromVideos();

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
  if (state.comparison.clipId) {
    const activeClip = state.clips.get(state.comparison.clipId);
    if (activeClip && activeClip.videoId === videoId) {
      void handleClipSelection(activeClip.id, { preserveRun: true, preserveModels: true });
    }
  }
}

function updateComparisonVideoOptions(initial = false) {
  if (!elements.comparisonVideo) return;
  const clips = getClipsArray();
  const placeholderText = elements.comparisonVideo.dataset.placeholder || 'Select clip';
  clearContainer(elements.comparisonVideo);
  const placeholder = document.createElement('option');
  placeholder.value = '';
  placeholder.textContent = placeholderText;
  elements.comparisonVideo.appendChild(placeholder);

  clips.forEach((clip) => {
    const option = document.createElement('option');
    option.value = String(clip.id);
    option.textContent = clipLabel(clip);
    elements.comparisonVideo.appendChild(option);
  });

  elements.comparisonVideo.disabled = clips.length === 0;

  if (!clips.length) {
    elements.comparisonVideo.value = '';
    state.comparison.clipId = null;
    state.comparison.videoId = null;
    resetComparisonDisplay('Create clips to view detections');
    return;
  }

  if (state.comparison.clipId && clips.some((clip) => clip.id === state.comparison.clipId)) {
    elements.comparisonVideo.value = String(state.comparison.clipId);
  } else if (initial) {
    const defaultClip = clips.find((clip) => {
      const video = state.videos.get(clip.videoId);
      return (video?.inference_runs || []).length;
    }) || clips[0];
    if (defaultClip) {
      state.comparison.clipId = defaultClip.id;
      elements.comparisonVideo.value = String(defaultClip.id);
      void handleClipSelection(defaultClip.id);
    }
  } else {
    elements.comparisonVideo.value = '';
  }
}

function handleVideoCardSelection(videoId) {
  const clipsForVideo = getClipsForVideo(videoId);
  if (!clipsForVideo.length) {
    window.alert('Preprocess this video to create clips before analyzing.');
    return;
  }
  const currentClip = state.comparison.clipId ? state.clips.get(state.comparison.clipId) : null;
  const nextClip = currentClip && currentClip.videoId === videoId ? currentClip : clipsForVideo[0];
  void handleClipSelection(nextClip.id);
}

async function handleClipSelection(clipId, { preserveRun = false, preserveModels = false } = {}) {
  if (!elements.comparisonRun) return;
  if (!clipId) {
    state.comparison.clipId = null;
    state.comparison.videoId = null;
    populateRunSelect([]);
    resetComparisonDisplay('Select a clip to inspect detections');
    return;
  }

  state.comparison.clipId = clipId;
  const clip = state.clips.get(clipId);
  if (!clip) {
    console.error('Clip not found:', clipId);
    return;
  }
  state.comparison.videoId = clip.videoId;
  if (elements.comparisonVideo) {
    elements.comparisonVideo.value = String(clip.id);
  }
  updateSelectedVideoHighlight();

  const selectedRunId = await loadComparisonRuns(clip.videoId, clip.id, { preserveSelection: preserveRun });
  if (selectedRunId) {
    await handleRunSelection(selectedRunId, { preserveModels, preserveZoom: preserveModels });
  } else {
    populateModelSelects([]);
    resetComparisonDisplay('No inference runs yet for this clip');
  }
}

async function loadComparisonRuns(videoId, clipId, { preserveSelection = false } = {}) {
  const projectId = state.activeProject?.id;
  if (!projectId) return null;
  const status = await fetchJSON(`/api/projects/${projectId}/videos/${videoId}/status`);
  const existing = state.videos.get(videoId) || {};
  const updatedVideo = {
    ...existing,
    status: status.status,
    inference_runs: status.inference_runs,
    video_metadata: status.video_metadata ?? existing.video_metadata,
  };
  state.videos.set(videoId, updatedVideo);
  extractClipsFromVideos();

  const card = document.querySelector(`[data-video-id="${videoId}"]`);
  if (card) {
    populateInferenceRuns(card, status.inference_runs || []);
  }

  const runs = status.inference_runs || [];
  const filteredRuns = runs.filter((run) => {
    const runClipId = run.results?.clip?.id || run.params?.clip_id;
    if (!clipId) {
      return !runClipId;
    }
    return runClipId === clipId;
  });

  return populateRunSelect(filteredRuns, { preserveSelection });
}

function populateRunSelect(runs, { preserveSelection = false } = {}) {
  if (!elements.comparisonRun) return null;
  const placeholderText = elements.comparisonRun.dataset.placeholder || 'Select run';
  clearContainer(elements.comparisonRun);
  const placeholder = document.createElement('option');
  placeholder.value = '';
  placeholder.textContent = placeholderText;
  elements.comparisonRun.appendChild(placeholder);

  // Sort runs by ID descending (newest first)
  const sortedRuns = [...runs].sort((a, b) => b.id - a.id);

  let selectedRunId = null;
  if (preserveSelection && sortedRuns.some((run) => run.id === state.comparison.runId)) {
    selectedRunId = state.comparison.runId;
  } else {
    // Select the first completed run (which is now the newest due to sorting)
    const completed = sortedRuns.find((run) => run.status === 'completed');
    selectedRunId = completed ? completed.id : sortedRuns[0]?.id ?? null;
  }

  sortedRuns.forEach((run) => {
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

  syncExportRunButton();

  return selectedRunId;
}

async function handleRunSelection(runId, { preserveModels = false, preserveZoom = false } = {}) {
  if (!runId) {
    state.comparison.runId = null;
    syncExportRunButton();
    populateModelSelects([]);
    resetComparisonDisplay('Select an inference run');
    // Hide run parameters display
    const paramsDisplay = document.getElementById('run-params-display');
    if (paramsDisplay) paramsDisplay.style.display = 'none';
    return;
  }
  const projectId = state.activeProject?.id;
  const clip = state.clips.get(state.comparison.clipId);
  const videoId = clip?.videoId;
  if (!projectId || !videoId) return;

  if (!preserveZoom) {
    resetZoom();
  }

  const payload = await fetchJSON(`/api/projects/${projectId}/videos/${videoId}/runs/${runId}/detections`);
  const frames = enrichFrames(payload);
  const availableModels = (payload.available_models?.length ? payload.available_models : payload.models) || [];
  
  // Display run parameters if available
  const params = payload.params || {};
  const paramsDisplay = document.getElementById('run-params-display');
  if (paramsDisplay && Object.keys(params).length > 0) {
    paramsDisplay.style.display = 'block';
    const displayFps = document.getElementById('display-fps');
    const displayMinConf = document.getElementById('display-min-confidence');
    const displayMaxConcepts = document.getElementById('display-max-concepts');
    const displayBatchSize = document.getElementById('display-batch-size');
    
    if (displayFps) displayFps.textContent = params.fps != null ? params.fps.toFixed(1) : '—';
    if (displayMinConf) displayMinConf.textContent = params.min_confidence != null ? params.min_confidence.toFixed(2) : '—';
    if (displayMaxConcepts) displayMaxConcepts.textContent = params.max_concepts != null ? params.max_concepts.toString() : '—';
    if (displayBatchSize) displayBatchSize.textContent = params.batch_size != null ? params.batch_size.toString() : '—';
  }

  state.comparison.frameImages = new Map();
  frames.forEach((frame) => {
    if (typeof frame.frame_index === 'number' && frame.frame_index >= 0 && frame.image_url) {
      state.comparison.frameImages.set(frame.frame_index, frame.image_url);
    }
  });

  state.comparison.detectionsByModel = new Map();
  Object.entries(payload.detections_by_model || {}).forEach(([modelId, detections]) => {
    state.comparison.detectionsByModel.set(modelId, detections);
  });
  availableModels.forEach((modelId) => {
    if (!state.comparison.detectionsByModel.has(modelId)) {
      state.comparison.detectionsByModel.set(modelId, []);
    }
  });

  const detectionCounts = payload.model_detection_counts || {};
  Object.keys(detectionCounts).forEach((modelId) => {
    if (!state.comparison.detectionsByModel.has(modelId)) {
      state.comparison.detectionsByModel.set(modelId, []);
    }
  });

  state.comparison.runId = Number(runId);
  syncExportRunButton();
  state.comparison.frames = frames;
  state.comparison.models = availableModels;

  updateModelSelections(availableModels, { preserveModels });
  renderOverlay();
}

async function refreshRunPayload({ preserveModels = true } = {}) {
  if (!state.comparison.runId) {
    return;
  }
  await handleRunSelection(state.comparison.runId, { preserveModels, preserveZoom: true });
}

function resolveRunContext(runId) {
  const numericId = Number(runId);
  if (!Number.isFinite(numericId)) {
    return null;
  }
  for (const video of state.videos.values()) {
    const runs = Array.isArray(video.inference_runs) ? video.inference_runs : [];
    const match = runs.find((run) => Number(run.id) === numericId);
    if (match) {
      return {
        videoId: video.id,
        projectId: video.project_id ?? state.activeProject?.id ?? null,
        run: match,
      };
    }
  }
  return null;
}

function syncExportRunButton() {
  if (!elements.exportRunBtn) {
    return;
  }
  const hasRunSelected = Number.isFinite(Number(state.comparison.runId)) && Number(state.comparison.runId) > 0;
  elements.exportRunBtn.disabled = !hasRunSelected;
  elements.exportRunBtn.setAttribute('aria-disabled', String(!hasRunSelected));
  elements.exportRunBtn.title = hasRunSelected ? 'Download the selected run export' : 'Select a run to enable export';
}

async function handleRunExportClick() {
  const button = elements.exportRunBtn;
  if (!button) {
    return;
  }

  const clip = state.comparison.clipId ? state.clips.get(state.comparison.clipId) : null;
  const targetRunId = Number(state.comparison.runId);
  if (!Number.isFinite(targetRunId) || targetRunId <= 0) {
    window.alert('Select a run to export.');
    return;
  }

  let targetVideoId = clip?.videoId ?? state.comparison.videoId ?? null;
  let targetProjectId = state.activeProject?.id ?? null;
  if (!targetVideoId || !targetProjectId) {
    const context = resolveRunContext(targetRunId);
    if (context) {
      targetVideoId = targetVideoId ?? context.videoId;
      targetProjectId = targetProjectId ?? context.projectId ?? targetProjectId;
    }
  }

  const originalLabel = button.textContent;
  button.disabled = true;
  button.textContent = 'Preparing…';
  try {
    const blob = await fetchRunArchiveBlob({
      runId: targetRunId,
      projectId: targetProjectId,
      videoId: targetVideoId,
    });
    triggerFileDownload(blob, `run_${targetRunId}.zip`);
  } catch (error) {
    console.error('Run export failed', error);
    window.alert(error.message || 'Failed to export run.');
  } finally {
    button.disabled = false;
    button.textContent = originalLabel;
  }
}

function enrichFrames(payload) {
  const framesByKey = new Map();

  (payload.frames || []).forEach((frame) => {
    const key = frame.frame_index ?? -1;
    framesByKey.set(key, { ...frame, models: {} });
  });

  const registerDetection = (detection, fallbackModelId = 'unknown') => {
    const key = detection.frame_index ?? -1;
    if (!framesByKey.has(key)) {
      framesByKey.set(key, {
        frame_index: detection.frame_index,
        timestamp_seconds: detection.timestamp_seconds,
        models: {},
      });
    }
    const entry = framesByKey.get(key);
    const modelId = detection.model_id || fallbackModelId;
    if (!entry.models[modelId]) {
      entry.models[modelId] = [];
    }
    entry.models[modelId].push(detection);
  };

  if (payload.detections_by_model) {
    Object.entries(payload.detections_by_model).forEach(([modelId, detections]) => {
      detections.forEach((detection) => registerDetection(detection, modelId));
    });
  } else {
    (payload.detections || []).forEach((detection) => registerDetection(detection));
  }

  if ((payload.models || []).length) {
    framesByKey.forEach((entry) => {
      (payload.models || []).forEach((modelId) => {
        if (!entry.models[modelId]) {
          entry.models[modelId] = [];
        }
      });
    });
  }

  if (!framesByKey.size) {
    framesByKey.set(-1, {
      frame_index: null,
      timestamp_seconds: null,
      models: Object.fromEntries((payload.models || []).map((modelId) => [modelId, []])),
    });
  }

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

  const fallbackModel = (index = 0) => {
    const fromRun = models[index];
    if (fromRun) return fromRun;
    return HARDCODED_MODELS[index]?.id || HARDCODED_MODELS[0]?.id || null;
  };

  if (!state.comparison.modelA) {
    state.comparison.modelA = fallbackModel(0);
  } else if (!preserveModels && !models.includes(state.comparison.modelA)) {
    state.comparison.modelA = fallbackModel(0);
  }

  if (!state.comparison.modelB) {
    state.comparison.modelB = fallbackModel(1);
  } else if (!preserveModels && !models.includes(state.comparison.modelB)) {
    state.comparison.modelB = fallbackModel(1) || state.comparison.modelA;
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
  console.debug('[populateModelSelects] Called with models:', models);
  console.debug('[populateModelSelects] Using hardcoded models:', HARDCODED_MODELS);
  
  // Always use hardcoded models for dropdown options
  setSelectOptions(elements.comparisonModelA, HARDCODED_MODELS, state.comparison.modelA, {
    labelFn: (item) => item.name || item.id,
  });
  setSelectOptions(elements.comparisonModelB, HARDCODED_MODELS, state.comparison.modelB, {
    labelFn: (item) => item.name || item.id,
  });
  updateModelToggleAvailability();
}

function setSelectOptions(selectEl, values, selected, options = {}) {
  if (!selectEl) {
    console.debug('[setSelectOptions] No select element provided');
    return;
  }
  
  const selectId = selectEl.id || 'unknown';
  console.debug(`[setSelectOptions][${selectId}] Called with:`, {
    valuesCount: values?.length,
    valuesType: Array.isArray(values) ? 'array' : typeof values,
    selected,
    options
  });
  
  const placeholderText = selectEl.dataset.placeholder || 'Select';
  clearContainer(selectEl);
  const placeholder = document.createElement('option');
  placeholder.value = '';
  placeholder.textContent = placeholderText;
  selectEl.appendChild(placeholder);
  console.debug(`[setSelectOptions][${selectId}] Added placeholder: "${placeholderText}"`);

  const normalize = (item) => {
    if (item == null) return null;
    if (typeof item === 'object') {
      return String(item.id ?? item.value ?? '');
    }
    return String(item);
  };

  const labelFn = options.labelFn || ((item) => {
    if (item == null) return '';
    if (typeof item === 'object') {
      return item.name || item.label || normalize(item) || '';
    }
    return String(item);
  });

  const normalizedValues = values
    .map((value) => {
      const normalizedValue = normalize(value);
      const label = labelFn(value);
      console.debug(`[setSelectOptions][${selectId}] Normalizing:`, {
        input: value,
        normalizedValue,
        label
      });
      if (!normalizedValue) {
        return null;
      }
      return {
        value: normalizedValue,
        label: label || normalizedValue,
      };
    })
    .filter(Boolean);

  console.debug(`[setSelectOptions][${selectId}] Normalized ${normalizedValues.length} values:`, normalizedValues);

  normalizedValues.forEach(({ value, label }, index) => {
    const option = document.createElement('option');
    option.value = value;
    option.textContent = label;
    selectEl.appendChild(option);
    console.debug(`[setSelectOptions][${selectId}] Added option ${index + 1}:`, { value, label });
  });

  const hasSelection = selected && normalizedValues.some((entry) => entry.value === selected);
  selectEl.value = hasSelection ? selected : '';
  selectEl.disabled = normalizedValues.length === 0;
  
  console.debug(`[setSelectOptions][${selectId}] Final state:`, {
    totalOptions: selectEl.options.length,
    selectedValue: selectEl.value,
    disabled: selectEl.disabled,
    hasSelection,
    allOptions: Array.from(selectEl.options).map(opt => ({ value: opt.value, text: opt.textContent }))
  });
}

function updateModelToggleAvailability() {
  if (!elements.modelToggleButtons) return;
  elements.modelToggleButtons.forEach((button) => {
    const slot = button.dataset.model;
    const modelId = slot === 'A' ? state.comparison.modelA : state.comparison.modelB;
    const baseLabel = button.dataset.label || button.textContent || slot;
    let suffix = '';
    if (modelId) {
      const detections = state.comparison.detectionsByModel.get(modelId) || [];
      const countText = detections.length ? ` (${detections.length})` : ' (0)';
      suffix = ` · ${modelId}${countText}`;
    }
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

  if (elements.framePlaceholder) {
    const frameUrl =
      (typeof frame.frame_index === 'number' && state.comparison.frameImages.get(frame.frame_index)) || frame.image_url;
    if (frameUrl) {
      elements.framePlaceholder.src = frameUrl;
    } else if (elements.framePlaceholder.dataset.placeholderSrc) {
      elements.framePlaceholder.src = elements.framePlaceholder.dataset.placeholderSrc;
    }
  }

  const models = frame.models || {};
  const primaryModel = state.comparison.activeToggle === 'A' ? state.comparison.modelA : state.comparison.modelB;
  const overlayDetections = primaryModel ? models[primaryModel] || [] : [];

  renderDetectionList(frame, models);
  drawOverlay(frame, overlayDetections);

  elements.frameSlider.max = String(Math.max(0, frames.length - 1));
  elements.frameSlider.value = String(clampedIndex);
  elements.frameSlider.disabled = frames.length <= 1;
  if (elements.frameLabel) {
    const clip = state.comparison.clipId ? state.clips.get(state.comparison.clipId) : null;
    const clipPrefix = clip ? `${clip.label || clipLabel(clip)} · ` : '';
    elements.frameLabel.textContent = `${clipPrefix}Frame ${frame.frame_index ?? '—'} · ${formatTimestamp(frame.timestamp_seconds)}`;
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

    if (!detections.length) {
      const empty = document.createElement('li');
      empty.className = 'rounded border border-dashed border-slate-200 px-2 py-2 text-xs italic text-slate-400';
      empty.textContent = 'No detections for this frame';
      list.appendChild(empty);
    } else {
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
    }

    container.appendChild(list);
    elements.detectionList.appendChild(container);
  });
}

function resetComparisonDisplay(message) {
  resetZoom();
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
  if (elements.framePlaceholder && elements.framePlaceholder.dataset.placeholderSrc) {
    elements.framePlaceholder.src = elements.framePlaceholder.dataset.placeholderSrc;
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

function initializeZoomControls() {
  if (zoomControlsInitialized) {
    return;
  }
  if (!elements.overlayCanvas || !elements.zoomContainer) {
    return;
  }
  if (typeof window.Panzoom !== 'function') {
    console.warn('Panzoom library not available; zoom controls disabled');
    return;
  }

  panzoomInstance = window.Panzoom(elements.zoomContainer, {
    maxScale: ZOOM_MAX,
    minScale: ZOOM_MIN,
    step: ZOOM_STEP,
    animate: false,
    cursor: 'default',
    contain: 'outside',
  });

  elements.zoomContainer.addEventListener('panzoomchange', (event) => {
    const detail = event.detail || {};
    state.comparison.zoom.scale = detail.scale ?? state.comparison.zoom.scale;
    state.comparison.zoom.x = detail.x ?? state.comparison.zoom.x;
    state.comparison.zoom.y = detail.y ?? state.comparison.zoom.y;
    if (elements.overlayCanvas) {
      elements.overlayCanvas.classList.toggle('is-zoomed', state.comparison.zoom.scale > ZOOM_MIN + 0.01);
    }
    updateZoomButtonsState();
  });

  const overlay = elements.overlayCanvas;
  overlay.addEventListener(
    'wheel',
    (event) => {
      if (!panzoomInstance) return;
      if (!(event.ctrlKey || event.metaKey)) {
        return;
      }
      event.preventDefault();
      panzoomInstance.zoomWithWheel(event);
    },
    { passive: false }
  );

  if (elements.zoomInBtn) {
    elements.zoomInBtn.addEventListener('click', (event) => {
      event.preventDefault();
      if (!panzoomInstance || elements.zoomInBtn.classList.contains('is-disabled')) {
        return;
      }
      panzoomInstance.zoomIn({ animate: false });
    });
  }
  if (elements.zoomOutBtn) {
    elements.zoomOutBtn.addEventListener('click', (event) => {
      event.preventDefault();
      if (!panzoomInstance || elements.zoomOutBtn.classList.contains('is-disabled')) {
        return;
      }
      panzoomInstance.zoomOut({ animate: false });
    });
  }
  if (elements.zoomResetBtn) {
    elements.zoomResetBtn.addEventListener('click', (event) => {
      event.preventDefault();
      if (!panzoomInstance || elements.zoomResetBtn.classList.contains('is-disabled')) {
        return;
      }
      resetZoom();
    });
  }

  zoomControlsInitialized = true;
  resetZoom();
}

function setZoomButtonState(button, disabled) {
  if (!button) {
    return;
  }
  button.disabled = false;
  button.classList.toggle('is-disabled', Boolean(disabled));
  button.setAttribute('aria-disabled', disabled ? 'true' : 'false');
}

function updateZoomButtonsState() {
  const { scale, x, y } = state.comparison.zoom;
  setZoomButtonState(elements.zoomInBtn, scale >= ZOOM_MAX - 0.001);
  setZoomButtonState(elements.zoomOutBtn, scale <= ZOOM_MIN + 0.001);
  const nearDefault = Math.abs(scale - ZOOM_DEFAULT) < 0.001 && Math.abs(x) < 0.5 && Math.abs(y) < 0.5;
  setZoomButtonState(elements.zoomResetBtn, nearDefault);
}

function resetZoom() {
  const zoom = state.comparison.zoom;
  zoom.scale = ZOOM_DEFAULT;
  zoom.x = 0;
  zoom.y = 0;
  if (panzoomInstance) {
    panzoomInstance.reset({ animate: false });
  }
  if (elements.overlayCanvas) {
    elements.overlayCanvas.classList.remove('is-zoomed');
  }
  updateZoomButtonsState();
}

function drawOverlay(frame, detections) {
  if (!elements.overlayLayer) {
    console.warn('[drawOverlay] overlayLayer element not found');
    return;
  }
  clearContainer(elements.overlayLayer);
  
  console.log('[drawOverlay] Drawing detections:', {
    frameIndex: frame?.frame_index,
    detectionsCount: detections.length,
    detections: detections.map(d => ({
      label: d.label,
      confidence: d.confidence,
      bbox: d.bbox,
      hasBbox: d.bbox && ['top', 'left', 'bottom', 'right'].every(k => Number.isFinite(Number(d.bbox[k])))
    }))
  });
  
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
      const clipId = event.target.value || null;
      void handleClipSelection(clipId, { preserveRun: false, preserveModels: false });
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
      void refreshRunPayload({ preserveModels: true });
    });
  }
  if (elements.exportRunBtn) {
    elements.exportRunBtn.addEventListener('click', () => {
      void handleRunExportClick();
    });
  }

  if (elements.comparisonModelB) {
    elements.comparisonModelB.addEventListener('change', (event) => {
      const modelId = event.target.value || null;
      setComparisonModel('B', modelId);
      void refreshRunPayload({ preserveModels: true });
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

  initializeZoomControls();
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
  const preprocessUploadBtn = document.getElementById('preprocess-upload-video-btn');
  const videoFileInput = document.getElementById('video-file-input');
  
  // Setup file input (shared between tabs)
  if (!videoFileInput) {
    const input = document.createElement('input');
    input.type = 'file';
    input.accept = 'video/*';
    input.id = 'video-file-input';
    input.className = 'hidden';
    document.body.appendChild(input);
    
    input.addEventListener('change', async (event) => {
      const file = event.target.files?.[0];
      if (!file) return;
      
      const projectId = state.activeProject?.id;
      if (!projectId) return;
      
      try {
        const formData = new FormData();
        formData.append('video', file);
        
        const response = await fetch(`/api/projects/${projectId}/videos`, {
          method: 'POST',
          body: formData,
        });
        
        if (!response.ok) {
          const errorText = await response.text();
          throw new Error(errorText || 'Upload failed');
        }
        
        await loadVideos(projectId);
        input.value = '';
      } catch (error) {
        window.alert(`Video upload failed: ${error.message}`);
        input.value = '';
      }
    });
  }
  
  // Setup upload buttons to trigger file input
  if (uploadVideoBtn) {
    uploadVideoBtn.addEventListener('click', () => {
      const input = document.getElementById('video-file-input');
      input?.click();
    });
  }
  
  if (preprocessUploadBtn) {
    preprocessUploadBtn.addEventListener('click', () => {
      const input = document.getElementById('video-file-input');
      input?.click();
    });
  }
  
  // Setup Run Inference button
  if (elements.runComparisonBtn) {
    elements.runComparisonBtn.addEventListener('click', async () => {
      await runComparisonInference();
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
  socket.on('inference_progress', (event) => {
    try {
      const statusEl = document.getElementById('inference-status');
      if (statusEl && event && event.run_id) {
        statusEl.textContent = `Run ${event.run_id}: ${event.status || 'in-progress'}`;
      }
      if (event && event.video_id) {
        refreshVideo(event.video_id);
      }
    } catch (e) {
      console.debug('Failed to handle inference_progress', e);
    }
  });
  socket.on('inference_partial', (event) => {
    try {
      const partialEl = document.getElementById('inference-partial');
      if (partialEl && event && event.run_id) {
        partialEl.textContent = `Run ${event.run_id} - Model ${event.model_id} batch ${event.batch}: ${event.detections_in_batch} detections`;
      }
    } catch (e) {
      console.debug('Failed to handle inference_partial', e);
    }
  });
}

async function initDashboard() {
  try {
    setupTabs();
    setupComparisonControls();
    // Load Clarifai models before populating dropdowns
    try {
      await loadClarifaiModels();
    } catch (err) {
      console.warn('Clarifai models unavailable, using fallback', err);
    }
    await loadProjects();
    setupButtons();
    setupSocketListeners();
    setupPreprocessingTab();
  } catch (error) {
    console.error('Failed to initialise dashboard', error);
  }
}

// ========================================
// TAB MANAGEMENT
// ========================================

function setupTabs() {
  const tabVideos = document.getElementById('tab-videos');
  const tabPreprocessing = document.getElementById('tab-preprocessing');
  const panelVideos = document.getElementById('panel-videos');
  const panelPreprocessing = document.getElementById('panel-preprocessing');

  if (!tabVideos || !tabPreprocessing) return;

  function switchTab(activeTab, activePanel, inactiveTab, inactivePanel) {
    activeTab.classList.remove('border-transparent', 'text-slate-500');
    activeTab.classList.add('border-slate-900', 'text-slate-900', 'font-semibold');
    activeTab.setAttribute('aria-selected', 'true');
    
    inactiveTab.classList.remove('border-slate-900', 'text-slate-900', 'font-semibold');
    inactiveTab.classList.add('border-transparent', 'text-slate-500');
    inactiveTab.setAttribute('aria-selected', 'false');
    
    activePanel.classList.remove('hidden');
    inactivePanel.classList.add('hidden');
  }

  tabVideos.addEventListener('click', () => {
    switchTab(tabVideos, panelVideos, tabPreprocessing, panelPreprocessing);
  });

  tabPreprocessing.addEventListener('click', () => {
    switchTab(tabPreprocessing, panelPreprocessing, tabVideos, panelVideos);
    loadPreprocessingVideos();
  });
}

// ========================================
// PREPROCESSING TAB
// ========================================

function setupPreprocessingTab() {
  const videoSelect = document.getElementById('preprocess-video-select');
  const video = document.getElementById('preprocess-video');
  const startInput = document.getElementById('preprocess-start');
  const durationInput = document.getElementById('preprocess-duration-input');
  const clipLengthInput = document.getElementById('preprocess-clip-length');
  const markStartBtn = document.getElementById('mark-start-btn');
  const markEndBtn = document.getElementById('mark-end-btn');
  const form = document.getElementById('preprocess-form');

  if (!videoSelect || !video) return;

  // Video selection handler
  videoSelect.addEventListener('change', async (e) => {
    const videoId = e.target.value;
    if (!videoId || !state.activeProject) return;

    try {
      const response = await fetch(`/api/projects/${state.activeProject.id}/videos/${videoId}/status`);
      if (!response.ok) throw new Error('Failed to load video');
      
      const videoData = await response.json();
      
      // Update video source
      if (videoData.storage_path) {
        const filename = videoData.storage_path.split('/').pop();
        const videoUrl = `/media/${state.activeProject.id}/${videoId}/${filename}`;
        video.querySelector('source').src = videoUrl;
        video.load();
      }

      // Update metadata
      document.getElementById('preprocess-duration').textContent = 
        videoData.duration_seconds ? formatSecondsToClock(videoData.duration_seconds) : '--';
      document.getElementById('preprocess-resolution').textContent = videoData.resolution || '--';
      document.getElementById('preprocess-status').textContent = videoData.status || '--';

      // Set max duration
      if (videoData.duration_seconds) {
        durationInput.max = videoData.duration_seconds;
        startInput.max = videoData.duration_seconds;
      }
    } catch (error) {
      console.error('Failed to load video for preprocessing:', error);
      alert('Failed to load video: ' + error.message);
    }
  });

  // Update current time display
  video?.addEventListener('timeupdate', () => {
    document.getElementById('preprocess-current-time').textContent = 
      formatSecondsToClock(video.currentTime);
  });

  // Mark start button
  markStartBtn?.addEventListener('click', () => {
    if (video) {
      startInput.value = video.currentTime.toFixed(1);
      updatePreview();
    }
  });

  // Mark end button
  markEndBtn?.addEventListener('click', () => {
    if (video) {
      const start = parseFloat(startInput.value) || 0;
      const end = video.currentTime;
      const duration = Math.max(0, end - start);
      durationInput.value = duration.toFixed(1);
      updatePreview();
    }
  });

  // Update preview on input change
  [startInput, durationInput, clipLengthInput].forEach(input => {
    input?.addEventListener('input', updatePreview);
  });

  function updatePreview() {
    const start = parseFloat(startInput.value) || 0;
    const duration = parseFloat(durationInput.value) || 0;
    const clipLength = parseFloat(clipLengthInput.value) || 20;
    const end = start + duration;
    const clipCount = Math.ceil(duration / clipLength);

    document.getElementById('preview-clip-count').textContent = clipCount;
    document.getElementById('preview-start').textContent = start.toFixed(1);
    document.getElementById('preview-end').textContent = end.toFixed(1);
  }

  // Form submission
  form?.addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const videoId = videoSelect.value;
    if (!videoId || !state.activeProject) {
      alert('Please select a video');
      return;
    }

    const start = parseFloat(startInput.value) || 0;
    const duration = parseFloat(durationInput.value) || 0;
    const clipLength = parseFloat(clipLengthInput.value) || 20;

    if (duration <= 0) {
      alert('Duration must be greater than 0');
      return;
    }

    try {
      const response = await fetch(`/api/projects/${state.activeProject.id}/videos/${videoId}/preprocess`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          start_seconds: start,
          duration_seconds: duration,
          clip_length: clipLength
        })
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.error || 'Preprocessing failed');
      }

      const result = await response.json();
      alert(`Video preprocessed successfully! Generated ${result.clip_count} clip(s)`);
      
      // Refresh video list
      if (state.activeProject) {
        await loadVideos(state.activeProject.id);
      }
    } catch (error) {
      console.error('Preprocessing error:', error);
      alert('Failed to preprocess video: ' + error.message);
    }
  });

  updatePreview();
}

async function loadPreprocessingVideos() {
  const videoSelect = document.getElementById('preprocess-video-select');
  if (!videoSelect || !state.activeProject) return;

  // Clear existing options except the first one
  videoSelect.innerHTML = '<option value="">-- Select a video --</option>';

  // Populate with videos from state
  state.videos.forEach((video, videoId) => {
    const option = document.createElement('option');
    option.value = videoId;
    option.textContent = video.original_path || `Video ${videoId}`;
    videoSelect.appendChild(option);
  });
}

async function triggerInference(videoId) {
  const video = state.videos.get(videoId);
  if (!video) {
    alert('Video not found');
    return;
  }

  try {
    const response = await fetch(`/api/projects/${state.activeProject.id}/videos/${videoId}/inference`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        model_ids: ['general-image-recognition'], // Default model
        params: { fps: 1.0, min_confidence: 0.2, max_concepts: 5 }
      })
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.error || 'Inference failed');
    }

    const result = await response.json();
    alert(`Inference started! Run ID: ${result.id}`);
    
    // Refresh videos to show the new run
    await loadVideos(state.activeProject.id);
  } catch (error) {
    console.error('Inference error:', error);
    alert('Failed to start inference: ' + error.message);
  }
}

async function loadMetrics() {
  try {
    const response = await fetch('/api/metrics');
    if (!response.ok) throw new Error('Failed to load metrics');
    const metrics = await response.json();
    state.metrics = metrics;
    renderInferenceCards(metrics);
    renderEfficiencyMatrix(metrics);
    updateCostPill(metrics);
  } catch (error) {
    console.error('Error loading metrics:', error);
  }
}

async function populateComparisonDropdowns() {
  // Populate video/clip dropdown
  if (elements.comparisonVideo) {
    elements.comparisonVideo.innerHTML = '<option value="">Select clip</option>';
    // Populate with clips
    state.clips.forEach(clip => {
      const option = document.createElement('option');
      option.value = clip.id; // clip.id like "1-1"
      option.textContent = clipLabel(clip);
      elements.comparisonVideo.appendChild(option);
    });
  }

  // Populate run dropdown (existing runs for the selected clip)
  if (elements.comparisonRun) {
    elements.comparisonRun.innerHTML = '<option value="">Select run</option>';
    // This would be populated when a clip is selected
  }

  // Populate model dropdowns with hardcoded models
  if (elements.comparisonModelA && elements.comparisonModelB) {
    console.log('[populateComparisonDropdowns] Using hardcoded models:', HARDCODED_MODELS);

    if (!state.comparison.modelA && HARDCODED_MODELS.length) {
      state.comparison.modelA = HARDCODED_MODELS[0].id;
    }
    if (!state.comparison.modelB && HARDCODED_MODELS.length > 1) {
      state.comparison.modelB = HARDCODED_MODELS[1].id;
    }

    console.log('[populateComparisonDropdowns] Setting model selections:', { 
      modelA: state.comparison.modelA, 
      modelB: state.comparison.modelB 
    });

    setSelectOptions(elements.comparisonModelA, HARDCODED_MODELS, state.comparison.modelA, {
      labelFn: (item) => item.name,
    });
    
    setSelectOptions(elements.comparisonModelB, HARDCODED_MODELS, state.comparison.modelB, {
      labelFn: (item) => item.name,
    });

    console.log('[populateComparisonDropdowns] Model dropdowns populated:', {
      modelA: {
        disabled: elements.comparisonModelA.disabled,
        value: elements.comparisonModelA.value,
        optionCount: elements.comparisonModelA.options.length
      },
      modelB: {
        disabled: elements.comparisonModelB.disabled,
        value: elements.comparisonModelB.value,
        optionCount: elements.comparisonModelB.options.length
      }
    });
  } else {
    console.error('Model dropdown elements not found:', {
      modelA: elements.comparisonModelA,
      modelB: elements.comparisonModelB,
    });
  }
}

async function runComparisonInference() {
  const clipId = elements.comparisonVideo.value;
  if (!clipId) {
    alert('Please select a clip');
    return;
  }

  const clip = state.clips.get(clipId);
  if (!clip) {
    alert('Clip not found');
    return;
  }

  const videoId = clip.videoId;
  const modelA = elements.comparisonModelA.value;
  const modelB = elements.comparisonModelB.value;

  const models = [];
  if (modelA) models.push(modelA);
  if (modelB) models.push(modelB);
  if (models.length === 0) {
    alert('Please select at least one model');
    return;
  }

  // Get inference parameters from UI inputs
  const fps = parseFloat(document.getElementById('param-fps')?.value || '1.0');
  const minConfidence = parseFloat(document.getElementById('param-min-confidence')?.value || '0.2');
  const maxConcepts = parseInt(document.getElementById('param-max-concepts')?.value || '5');
  const batchSize = parseInt(document.getElementById('param-batch-size')?.value || '8');

  const params = {
    fps,
    min_confidence: minConfidence,
    max_concepts: maxConcepts,
    batch_size: batchSize
  };

  console.log('[runComparisonInference] Starting inference:', {
    projectId: state.activeProject.id,
    videoId,
    clipId,
    models,
    params,
    payload: {
      model_ids: models,
      clip_id: clipId,
      params
    }
  });

  try {
    const response = await fetch(`/api/projects/${state.activeProject.id}/videos/${videoId}/inference`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        model_ids: models,
        clip_id: clipId,
        params
      })
    });

    console.log('[runComparisonInference] Response status:', response.status);

    if (!response.ok) {
      // Read response as text first, then try to parse as JSON
      const responseText = await response.text();
      console.error('[runComparisonInference] Server error response:', responseText);
      
      let errorMessage = 'Inference failed';
      try {
        // Try to parse as JSON
        const error = JSON.parse(responseText);
        errorMessage = error.error || error.message || JSON.stringify(error);
      } catch (jsonError) {
        // Not JSON, extract from HTML or use raw text
        const match = responseText.match(/<title>(.*?)<\/title>/i);
        if (match) {
          errorMessage = match[1];
        } else if (responseText.includes('<!doctype') || responseText.includes('<html')) {
          errorMessage = `Server error (${response.status}). Check console for details.`;
        } else {
          errorMessage = responseText.substring(0, 200) || `Server error (${response.status})`;
        }
      }
      throw new Error(errorMessage);
    }

    const result = await response.json();
    console.log('[runComparisonInference] Inference started:', result);
    alert(`Inference started on clip ${clipId} with models ${models.join(', ')}! Run ID: ${result.id}`);
    
    // Refresh videos to show the new run
    await loadVideos(state.activeProject.id);
  } catch (error) {
    console.error('[runComparisonInference] Error:', error);
    alert('Failed to start inference: ' + error.message);
  }
}

initDashboard();
