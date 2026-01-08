// Preprocessing Dashboard
const state = {
  projectId: 1,
  project: null,
  videos: new Map(),
  currentVideoId: null,
  clips: [], // Array of {start: number, end: number, id: number}
  currentClipIndex: 0, // Which clip we're currently editing
};

// DOM Ready
document.addEventListener("DOMContentLoaded", () => {
  console.log("DOM Content Loaded - initializing preprocessing page");
  loadProject();
  loadVideos();
  setupButtons();
  setupPreprocessForm();
  initializeClips();
});

// Initialize clips array with one empty clip
function initializeClips() {
  state.clips = [{ id: 1, start: null, end: null }];
  state.currentClipIndex = 0;
  renderClipInputs();
  updatePreview();
}

// Load project details
async function loadProject() {
  try {
    const response = await fetch(`/api/projects/${state.projectId}`);
    if (!response.ok) throw new Error("Failed to load project");
    state.project = await response.json();
    document.getElementById("active-project").textContent = state.project.name || "Untitled Project";
    document.getElementById("project-description").textContent = state.project.description || "No description";
  } catch (error) {
    console.error("Error loading project:", error);
    document.getElementById("active-project").textContent = "Error loading project";
  }
}

// Load videos for preprocessing
async function loadVideos() {
  try {
    console.log("Loading videos...");
    const response = await fetch(`/api/projects/${state.projectId}/videos`);
    if (!response.ok) throw new Error("Failed to load videos");
    const videos = await response.json();
    console.log("Loaded videos:", videos);
    
    state.videos.clear();
    videos.forEach(video => state.videos.set(video.id, video));
    
    renderVideoList();
    populateVideoSelect();
  } catch (error) {
    console.error("Error loading videos:", error);
  }
}

// Render video list
function renderVideoList() {
  const videoList = document.getElementById("video-list");
  console.log("Video list element:", videoList);
  if (!videoList) {
    console.error("Video list element not found!");
    return;
  }
  
  videoList.innerHTML = "";
  console.log("Rendering videos:", state.videos.size);
  
  if (state.videos.size === 0) {
    videoList.innerHTML = '<li class="text-sm text-slate-500">No videos uploaded yet</li>';
    return;
  }
  
  state.videos.forEach(video => {
    const li = document.createElement("li");
    li.className = "flex items-center justify-between rounded-lg border border-slate-200 bg-slate-50 p-3";
    
    const leftDiv = document.createElement("div");
    leftDiv.className = "flex items-center gap-3";
    
    const videoIcon = document.createElement("div");
    videoIcon.className = "flex h-10 w-10 items-center justify-center rounded-lg bg-slate-200";
    videoIcon.innerHTML = `<svg class="h-5 w-5 text-slate-600" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 10l4.553-2.276A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z" /></svg>`;
    
    const nameDiv = document.createElement("div");
    const nameP = document.createElement("p");
    nameP.className = "text-sm font-medium";
    // Use original_path for display name, fallback to storage_path filename
    const displayName = video.original_path || (video.storage_path ? video.storage_path.split('/').pop() : `Video ${video.id}`);
    nameP.textContent = displayName;
    const statusP = document.createElement("p");
    statusP.className = "text-xs text-slate-500";
    statusP.textContent = video.status || "uploaded";
    nameDiv.appendChild(nameP);
    nameDiv.appendChild(statusP);
    
    leftDiv.appendChild(videoIcon);
    leftDiv.appendChild(nameDiv);
    
    const selectBtn = document.createElement("button");
    selectBtn.className = "rounded-full border border-slate-900 px-3 py-1 text-xs font-medium hover:bg-slate-50";
    selectBtn.textContent = "Select";
    selectBtn.addEventListener("click", () => selectVideo(video.id));
    
    li.appendChild(leftDiv);
    li.appendChild(selectBtn);
    videoList.appendChild(li);
  });
}

// Populate video select dropdown
function populateVideoSelect() {
  const select = document.getElementById("preprocess-video-select");
  if (!select) return;
  
  // Keep the first "-- Select a video --" option
  select.innerHTML = '<option value="">-- Select a video --</option>';
  
  state.videos.forEach(video => {
    const option = document.createElement("option");
    option.value = video.id;
    // Use original_path for display name, fallback to storage_path filename
    const displayName = video.original_path || (video.storage_path ? video.storage_path.split('/').pop() : `Video ${video.id}`);
    option.textContent = displayName;
    select.appendChild(option);
  });
}

// Select a video for preprocessing
function selectVideo(videoId) {
  console.log("Selecting video:", videoId);
  const video = state.videos.get(videoId);
  console.log("Video data:", video);
  if (!video) {
    console.error("Video not found:", videoId);
    return;
  }
  
  state.currentVideoId = videoId;
  
  // Update select dropdown
  const select = document.getElementById("preprocess-video-select");
  if (select) {
    // Add the selected video as an option and select it
    const displayName = video.original_path || (video.storage_path ? video.storage_path.split('/').pop() : `Video ${video.id}`);
    select.innerHTML = `<option value="${videoId}" selected>${displayName}</option>`;
  }
  
  // Reset marked times when selecting a new video
  initializeClips();
  
  // Load video into player
  const videoElement = document.getElementById("preprocess-video");
  const videoSource = document.getElementById("preprocess-video-source");
  
  if (videoElement && videoSource) {
    // Extract filename from storage_path (remove the media/project_X/video_Y/ prefix)
    const filename = video.storage_path ? video.storage_path.split('/').pop() : video.original_path;
    const videoUrl = `/media/${state.projectId}/${videoId}/${filename}`;
    console.log("Setting video source:", videoUrl);
    
    // Set src directly on video element (like the working preprocess.js)
    videoElement.src = videoUrl;
    videoElement.load();
    
    // Add error handling
    videoElement.addEventListener("error", (e) => {
      console.error("Video loading error:", e);
      console.error("Video network state:", videoElement.networkState);
      console.error("Video ready state:", videoElement.readyState);
      const sources = videoElement.querySelectorAll('source');
      sources.forEach((src, i) => {
        console.error(`Source ${i} src:`, src.src);
      });
    });
    
    videoElement.addEventListener("loadstart", () => console.log("Video load started"));
    videoElement.addEventListener("loadeddata", () => console.log("Video data loaded"));
    videoElement.addEventListener("canplay", () => console.log("Video can play"));
    
    // Update metadata when loaded
    videoElement.addEventListener("loadedmetadata", () => {
      document.getElementById("preprocess-duration").textContent = formatDuration(videoElement.duration);
      document.getElementById("preprocess-resolution").textContent = `${videoElement.videoWidth}x${videoElement.videoHeight}`;
      document.getElementById("preprocess-status").textContent = "Ready";
      
      // Reset times when video loads
      state.startTime = null;
      state.endTime = null;
      updatePreview();
    }, { once: true });
    
    // Update current time display
    videoElement.addEventListener("timeupdate", () => {
      document.getElementById("preprocess-current-time").textContent = formatTime(videoElement.currentTime);
    });
  }
  
  // Scroll to the form section when a video is selected
  const formSection = document.getElementById("clip-form-section");
  if (formSection) {
    formSection.scrollIntoView({ behavior: "smooth", block: "start" });
  }
}

// Setup buttons
function setupButtons() {
  const fileInput = document.getElementById("video-file-input");
  const uploadBtn = document.getElementById("upload-video-btn");
  
  if (uploadBtn && fileInput) {
    uploadBtn.addEventListener("click", () => fileInput.click());
    fileInput.addEventListener("change", handleFileUpload);
  }
  
  const markStartBtn = document.getElementById("mark-start-btn");
  const markEndBtn = document.getElementById("mark-end-btn");
  
  if (markStartBtn) {
    markStartBtn.addEventListener("click", markStartTime);
  }
  
  if (markEndBtn) {
    markEndBtn.addEventListener("click", markEndTime);
  }
}

// Handle file upload
async function handleFileUpload(event) {
  const file = event.target.files[0];
  if (!file) return;
  
  const formData = new FormData();
  formData.append("video", file);
  
  try {
    const response = await fetch(`/api/projects/${state.projectId}/videos`, {
      method: "POST",
      body: formData
    });
    
    if (!response.ok) throw new Error("Upload failed");
    
    const video = await response.json();
    state.videos.set(video.id, video);
    renderVideoList();
    populateVideoSelect();
    
    alert("Video uploaded successfully!");
  } catch (error) {
    console.error("Error uploading video:", error);
    alert("Failed to upload video");
  }
  
  // Reset input
  event.target.value = "";
}

// Mark start time for current clip
function markStartTime() {
  const videoElement = document.getElementById("preprocess-video");
  if (!videoElement) return;
  
  const currentTime = videoElement.currentTime;
  state.clips[state.currentClipIndex].start = currentTime;
  renderClipInputs();
  updatePreview();
}

// Mark end time for current clip
function markEndTime() {
  const videoElement = document.getElementById("preprocess-video");
  if (!videoElement) return;
  
  const currentTime = videoElement.currentTime;
  state.clips[state.currentClipIndex].end = currentTime;
  renderClipInputs();
  updatePreview();
}

// Setup preprocessing form
function setupPreprocessForm() {
  const form = document.getElementById("preprocess-form");
  console.log("Form element:", form);
  
  if (form) {
    console.log("Setting up form submit handler");
    form.addEventListener("submit", handlePreprocessSubmit);
  } else {
    console.error("Form element not found!");
  }
}

// Update preview for current clip
function updatePreview() {
  const currentClip = state.clips[state.currentClipIndex];
  const start = currentClip.start || 0;
  const end = currentClip.end || 0;
  const duration = end - start;
  
  document.getElementById("preview-start").textContent = start.toFixed(1);
  document.getElementById("preview-end").textContent = end.toFixed(1);
  document.getElementById("preview-duration").textContent = duration > 0 ? duration.toFixed(1) : "0.0";
}

// Render clip input controls
function renderClipInputs() {
  const container = document.getElementById("clip-inputs-container");
  if (!container) return;
  
  container.innerHTML = "";
  
  state.clips.forEach((clip, index) => {
    const clipDiv = document.createElement("div");
    clipDiv.className = `p-4 rounded-lg border-2 ${index === state.currentClipIndex ? 'border-blue-500 bg-blue-50' : 'border-slate-200 bg-white'}`;
    
    clipDiv.innerHTML = `
      <div class="flex items-center justify-between mb-3">
        <h4 class="font-medium text-slate-700">Clip ${clip.id}</h4>
        <div class="flex gap-2">
          <button type="button" class="px-3 py-1 text-xs bg-blue-500 text-white rounded hover:bg-blue-600" onclick="selectClip(${index})">
            ${index === state.currentClipIndex ? 'Active' : 'Select'}
          </button>
          ${state.clips.length > 1 ? `<button type="button" class="px-3 py-1 text-xs bg-red-500 text-white rounded hover:bg-red-600" onclick="removeClip(${index})">Remove</button>` : ''}
        </div>
      </div>
      <div class="grid grid-cols-2 gap-4">
        <div>
          <label class="block text-sm font-medium text-slate-700">Start Time</label>
          <input type="number" class="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm" value="${clip.start !== null ? clip.start.toFixed(1) : ''}" readonly />
        </div>
        <div>
          <label class="block text-sm font-medium text-slate-700">End Time</label>
          <input type="number" class="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm" value="${clip.end !== null ? clip.end.toFixed(1) : ''}" readonly />
        </div>
      </div>
    `;
    
    container.appendChild(clipDiv);
  });
  
  // Add clip button (if less than 5 clips)
  if (state.clips.length < 5) {
    const addButton = document.createElement("button");
    addButton.type = "button";
    addButton.className = "w-full mt-4 px-4 py-2 bg-green-500 text-white rounded-lg hover:bg-green-600 text-sm font-medium";
    addButton.textContent = "+ Add Another Clip";
    addButton.onclick = addClip;
    container.appendChild(addButton);
  }
}

// Select a clip to edit
function selectClip(index) {
  state.currentClipIndex = index;
  renderClipInputs();
  updatePreview();
}

// Add a new clip
function addClip() {
  if (state.clips.length >= 5) return;
  
  const newClipId = Math.max(...state.clips.map(c => c.id)) + 1;
  state.clips.push({ id: newClipId, start: null, end: null });
  state.currentClipIndex = state.clips.length - 1;
  renderClipInputs();
  updatePreview();
}

// Remove a clip
function removeClip(index) {
  if (state.clips.length <= 1) return;
  
  state.clips.splice(index, 1);
  if (state.currentClipIndex >= state.clips.length) {
    state.currentClipIndex = state.clips.length - 1;
  }
  renderClipInputs();
  updatePreview();
}

// Make functions globally accessible
window.selectClip = selectClip;
window.addClip = addClip;
window.removeClip = removeClip;

// Handle preprocessing form submission
async function handlePreprocessSubmit(event) {
  event.preventDefault();
  
  if (!state.currentVideoId) {
    alert("Please select a video first");
    return;
  }
  
  // Validate clips
  const validClips = state.clips.filter(clip => clip.start !== null && clip.end !== null && clip.start < clip.end);
  if (validClips.length === 0) {
    alert("Please define at least one valid clip segment");
    return;
  }
  
  try {
    const response = await fetch(`/api/projects/${state.projectId}/videos/${state.currentVideoId}/preprocess`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({
        clips: validClips.map(clip => ({ start: clip.start, end: clip.end }))
      })
    });
    
    if (!response.ok) {
      const errorData = await response.json();
      throw new Error(errorData.error || `HTTP ${response.status}`);
    }
    
    const result = await response.json();
    console.log("Preprocessing result:", result);
    alert(`${validClips.length} clip(s) created successfully!`);
    
    // Reload videos to show updated status
    loadVideos();
  } catch (error) {
    console.error("Error starting preprocessing:", error);
    alert(`Failed to create clips: ${error.message}`);
  }
}

// Format duration (seconds to MM:SS or HH:MM:SS)
function formatDuration(seconds) {
  if (isNaN(seconds) || seconds < 0) return "--";
  
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const secs = Math.floor(seconds % 60);
  
  if (hours > 0) {
    return `${hours}:${String(minutes).padStart(2, "0")}:${String(secs).padStart(2, "0")}`;
  }
  return `${minutes}:${String(secs).padStart(2, "0")}`;
}

// Format time (seconds to HH:MM:SS.mm)
function formatTime(seconds) {
  if (isNaN(seconds) || seconds < 0) return "00:00:00";
  
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const secs = Math.floor(seconds % 60);
  const millis = Math.floor((seconds % 1) * 100);
  
  return `${String(hours).padStart(2, "0")}:${String(minutes).padStart(2, "0")}:${String(secs).padStart(2, "0")}.${String(millis).padStart(2, "0")}`;
}
