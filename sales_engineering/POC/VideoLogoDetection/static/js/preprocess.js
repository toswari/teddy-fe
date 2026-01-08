const urlParams = new URLSearchParams(window.location.search);
const projectId = urlParams.get('project_id');
const videoId = urlParams.get('video_id');

const elements = {
  videoPlayer: document.getElementById('video-player'),
  videoDuration: document.getElementById('video-duration'),
  videoCurrentTime: document.getElementById('video-current-time'),
  videoResolution: document.getElementById('video-resolution'),
  videoStatus: document.getElementById('video-status'),
  markStartBtn: document.getElementById('mark-start-btn'),
  markEndBtn: document.getElementById('mark-end-btn'),
  startSecondsInput: document.getElementById('start-seconds'),
  durationSecondsInput: document.getElementById('duration-seconds'),
  clipLengthInput: document.getElementById('clip-length'),
  markedStart: document.getElementById('marked-start'),
  markedDuration: document.getElementById('marked-duration'),
  previewWindow: document.getElementById('preview-window'),
  previewClipLength: document.getElementById('preview-clip-length'),
  previewClipCount: document.getElementById('preview-clip-count'),
  preprocessForm: document.getElementById('preprocess-form'),
  resetFormBtn: document.getElementById('reset-form-btn'),
  processingStatus: document.getElementById('processing-status'),
};

const socket = window.io ? window.io() : null;

let markedStartTime = null;
let markedEndTime = null;
let videoDuration = 0;

function formatTime(seconds) {
  if (!Number.isFinite(seconds) || seconds < 0) return '00:00';
  const hrs = Math.floor(seconds / 3600);
  const mins = Math.floor((seconds % 3600) / 60);
  const secs = Math.floor(seconds % 60);
  if (hrs > 0) {
    return `${hrs}:${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;
  }
  return `${mins}:${String(secs).padStart(2, '0')}`;
}

function updatePreview() {
  const startValue = parseFloat(elements.startSecondsInput.value) || 0;
  const durationValue = parseFloat(elements.durationSecondsInput.value) || null;
  const clipLength = parseInt(elements.clipLengthInput.value) || 20;

  elements.previewClipLength.textContent = `${clipLength}s`;

  if (durationValue === null && videoDuration > 0) {
    const effectiveDuration = videoDuration - startValue;
    elements.previewWindow.textContent = startValue > 0 
      ? `${formatTime(startValue)} → End (${formatTime(effectiveDuration)})`
      : 'Full video';
    elements.previewClipCount.textContent = Math.ceil(effectiveDuration / clipLength);
  } else if (durationValue !== null) {
    const endTime = startValue + durationValue;
    elements.previewWindow.textContent = `${formatTime(startValue)} → ${formatTime(endTime)} (${formatTime(durationValue)})`;
    elements.previewClipCount.textContent = Math.ceil(durationValue / clipLength);
  } else {
    elements.previewWindow.textContent = 'Full video';
    elements.previewClipCount.textContent = '--';
  }
}

async function loadVideo() {
  if (!projectId || !videoId) {
    alert('Missing project or video ID');
    window.location.href = '/';
    return;
  }

  try {
    const response = await fetch(`/api/projects/${projectId}/videos/${videoId}/status`);
    if (!response.ok) throw new Error('Failed to load video');
    
    const video = await response.json();
    
    // Set video source - extract filename from storage_path
    if (video.storage_path) {
      const filename = video.storage_path.split('/').pop();
      const videoUrl = `/media/${projectId}/${videoId}/${filename}`;
      
      console.log('Loading video from:', videoUrl);
      console.log('Storage path:', video.storage_path);
      
      // Set the source and load
      elements.videoPlayer.src = videoUrl;
      elements.videoPlayer.load();
      
      // Add error handler
      elements.videoPlayer.onerror = (e) => {
        console.error('Video load error:', e);
        console.error('Failed to load video from:', videoUrl);
        alert('Failed to load video. Check if the file exists and is accessible.');
      };
    } else {
      alert('Video storage path not found. Video may not be uploaded yet.');
    }
    
    // Update metadata
    elements.videoStatus.textContent = video.status;
    elements.videoResolution.textContent = video.resolution || '--';
    
    if (video.duration_seconds) {
      videoDuration = video.duration_seconds;
      elements.videoDuration.textContent = formatTime(videoDuration);
    }
  } catch (error) {
    console.error('Failed to load video:', error);
    alert('Failed to load video details: ' + error.message);
  }
}

elements.videoPlayer?.addEventListener('timeupdate', () => {
  if (elements.videoPlayer) {
    elements.videoCurrentTime.textContent = formatTime(elements.videoPlayer.currentTime);
  }
});

elements.videoPlayer?.addEventListener('loadedmetadata', () => {
  if (elements.videoPlayer && elements.videoPlayer.duration) {
    videoDuration = elements.videoPlayer.duration;
    elements.videoDuration.textContent = formatTime(videoDuration);
    updatePreview();
  }
});

elements.markStartBtn?.addEventListener('click', () => {
  if (elements.videoPlayer) {
    markedStartTime = elements.videoPlayer.currentTime;
    elements.startSecondsInput.value = Math.floor(markedStartTime).toString();
    elements.markedStart.textContent = formatTime(markedStartTime);
    
    // If end is already marked, calculate duration
    if (markedEndTime !== null && markedEndTime > markedStartTime) {
      const duration = markedEndTime - markedStartTime;
      elements.durationSecondsInput.value = Math.floor(duration).toString();
      elements.markedDuration.textContent = formatTime(duration);
    }
    
    updatePreview();
  }
});

elements.markEndBtn?.addEventListener('click', () => {
  if (elements.videoPlayer) {
    markedEndTime = elements.videoPlayer.currentTime;
    
    // Calculate duration from start
    const startValue = parseFloat(elements.startSecondsInput.value) || markedStartTime || 0;
    if (markedEndTime > startValue) {
      const duration = markedEndTime - startValue;
      elements.durationSecondsInput.value = Math.floor(duration).toString();
      elements.markedDuration.textContent = formatTime(duration);
    }
    
    updatePreview();
  }
});

elements.startSecondsInput?.addEventListener('input', updatePreview);
elements.durationSecondsInput?.addEventListener('input', updatePreview);
elements.clipLengthInput?.addEventListener('input', updatePreview);

elements.resetFormBtn?.addEventListener('click', () => {
  elements.startSecondsInput.value = '';
  elements.durationSecondsInput.value = '';
  elements.clipLengthInput.value = '20';
  markedStartTime = null;
  markedEndTime = null;
  elements.markedStart.textContent = 'None';
  elements.markedDuration.textContent = 'None';
  updatePreview();
});

elements.preprocessForm?.addEventListener('submit', async (e) => {
  e.preventDefault();
  
  const payload = {};
  const startValue = parseFloat(elements.startSecondsInput.value);
  const durationValue = parseFloat(elements.durationSecondsInput.value);
  const clipLength = parseInt(elements.clipLengthInput.value) || 20;
  
  if (Number.isFinite(startValue) && startValue >= 0) {
    payload.start_seconds = startValue;
  }
  
  if (Number.isFinite(durationValue) && durationValue > 0) {
    payload.duration_seconds = durationValue;
  }
  
  if (clipLength) {
    payload.clip_length = clipLength;
  }
  
  try {
    elements.processingStatus.classList.remove('hidden');
    
    const response = await fetch(`/api/projects/${projectId}/videos/${videoId}/preprocess`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.error || 'Preprocessing failed');
    }
    
    alert('Preprocessing started! Redirecting to dashboard...');
    window.location.href = '/';
  } catch (error) {
    alert(`Preprocessing failed: ${error.message}`);
    elements.processingStatus.classList.add('hidden');
  }
});

if (socket) {
  socket.on('preprocess_status', (event) => {
    if (event && event.video_id === parseInt(videoId)) {
      if (event.status === 'completed') {
        alert('Preprocessing completed! Redirecting to dashboard...');
        window.location.href = '/';
      } else if (event.status === 'failed') {
        alert('Preprocessing failed: ' + (event.error || 'Unknown error'));
        elements.processingStatus.classList.add('hidden');
      }
    }
  });
}

loadVideo();
