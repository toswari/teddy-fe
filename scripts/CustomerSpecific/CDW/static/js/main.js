/**
 * Basketball Video Segmenter - Main JavaScript
 */

// Function to create a ZIP file containing all clips
async function downloadAllClipsAsZip(clips, zipFilename = 'basketball_clips.zip') {
    // Check if JSZip is loaded
    if (typeof JSZip !== 'function') {
        console.error('JSZip is not loaded. Make sure to include the JSZip library.');
        alert('Download functionality requires JSZip library. Please try again later.');
        return;
    }
    
    // Create a new ZIP instance
    const zip = new JSZip();
    const statusElement = document.getElementById('progressStatus');
    const progressBar = document.getElementById('progressBar');
    const progressPercentage = document.getElementById('progressPercentage');
    
    try {
        // Show progress container if hidden
        const progressContainer = document.getElementById('progressContainer');
        progressContainer.classList.remove('hidden');
        statusElement.textContent = 'Preparing clips for download...';
        
        // Download each clip and add to zip
        for (let i = 0; i < clips.length; i++) {
            const clip = clips[i];
            const clipNumber = i + 1;
            const filename = `clip_${clipNumber}.mp4`;
            
            // Update progress
            const progress = Math.round((i / clips.length) * 100);
            progressBar.style.width = `${progress}%`;
            progressPercentage.textContent = `${progress}%`;
            statusElement.textContent = `Downloading clip ${clipNumber} of ${clips.length}...`;
            
            // Fetch the clip
            const response = await fetch(clip.path);
            const blob = await response.blob();
            
            // Add to zip
            zip.file(filename, blob);
        }
        
        // Update progress to generating zip
        progressBar.style.width = '90%';
        progressPercentage.textContent = '90%';
        statusElement.textContent = 'Generating zip file...';
        
        // Generate zip file
        const content = await zip.generateAsync({
            type: 'blob',
            compression: 'DEFLATE',
            compressionOptions: {
                level: 5
            }
        });
        
        // Update progress to complete
        progressBar.style.width = '100%';
        progressPercentage.textContent = '100%';
        statusElement.textContent = 'Download complete!';
        
        // Create download link and trigger download
        const url = URL.createObjectURL(content);
        const link = document.createElement('a');
        link.href = url;
        link.download = zipFilename;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        
        // Cleanup
        setTimeout(() => {
            URL.revokeObjectURL(url);
        }, 1000);
        
    } catch (error) {
        console.error('Error creating zip file:', error);
        statusElement.textContent = 'Error creating download. Please try again.';
    }
}

// Function to toggle fullscreen for the video player
function toggleFullscreen(videoElement) {
    if (!document.fullscreenElement) {
        if (videoElement.requestFullscreen) {
            videoElement.requestFullscreen();
        } else if (videoElement.webkitRequestFullscreen) { /* Safari */
            videoElement.webkitRequestFullscreen();
        } else if (videoElement.msRequestFullscreen) { /* IE11 */
            videoElement.msRequestFullscreen();
        }
    } else {
        if (document.exitFullscreen) {
            document.exitFullscreen();
        } else if (document.webkitExitFullscreen) { /* Safari */
            document.webkitExitFullscreen();
        } else if (document.msExitFullscreen) { /* IE11 */
            document.msExitFullscreen();
        }
    }
}

// Detect when the page is about to be unloaded
window.addEventListener('beforeunload', (event) => {
    // Check if there's an active upload/processing
    const progressContainer = document.getElementById('progressContainer');
    if (progressContainer && !progressContainer.classList.contains('hidden')) {
        // Cancel any pending requests (best effort)
        if (window.currentRequest && typeof window.currentRequest.abort === 'function') {
            window.currentRequest.abort();
        }
        
        // Show a confirmation dialog
        event.preventDefault();
        event.returnValue = 'You have an active process running. Are you sure you want to leave?';
        return event.returnValue;
    }
}); 