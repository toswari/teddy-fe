document.addEventListener('DOMContentLoaded', () => {
    // Application state
    const state = {
        sessionId: null,
        canvasWidth: 0,
        canvasHeight: 0,
        imageData: null,
        pointType: 'positive',
        selectingPoints: false,
        currentPlayer: null,
        players: {},
        canvasPoints: [], // {x, y, type, playerId}
        downloadUrl: null
    };

    // DOM Elements
    const elements = {
        // Upload area
        uploadArea: document.getElementById('upload-area'),
        dropArea: document.getElementById('drop-area'),
        fileUpload: document.getElementById('file-upload'),
        uploadProgress: document.getElementById('upload-progress'),
        uploadProgressBar: document.querySelector('#upload-progress .progress-bar'),
        uploadError: document.getElementById('upload-error'),
        
        // Annotation area
        annotationArea: document.getElementById('annotation-area'),
        annotationCanvas: document.getElementById('annotation-canvas'),
        canvasContainer: document.getElementById('canvas-container'),
        annotationStatus: document.getElementById('annotation-status'),
        currentPointType: document.getElementById('current-point-type'),
        
        // Control panel
        startPlayerSelection: document.getElementById('start-player-selection'),
        nextPlayer: document.getElementById('next-player'),
        endPointCollection: document.getElementById('end-point-collection'),
        pointTypeSelection: document.getElementById('point-type-selection'),
        pointTypeRadios: document.querySelectorAll('input[name="point-type"]'),
        currentPlayerPoints: document.getElementById('current-player-points'),
        currentPlayerId: document.getElementById('current-player-id'),
        pointsList: document.getElementById('points-list'),
        clearPoints: document.getElementById('clear-points'),
        playersList: document.getElementById('players-list'),
        noPlayersMessage: document.getElementById('no-players-message'),
        annotationInstructions: document.getElementById('annotation-instructions'),
        
        // Processing
        processingButtons: document.getElementById('processing-buttons'),
        generateMasks: document.getElementById('generate-masks'),
        trackAnnotate: document.getElementById('track-annotate'),
        
        // Results
        resultsArea: document.getElementById('results-area'),
        maskPreview: document.getElementById('mask-preview'),
        trackingResults: document.getElementById('tracking-results'),
        trackingPreview: document.getElementById('tracking-preview'),
        frameSlider: document.getElementById('frame-slider'),
        currentFrame: document.getElementById('current-frame'),
        trackingProgress: document.getElementById('tracking-progress'),
        progressBar: document.querySelector('#tracking-progress .progress-bar'),
        statusLine: document.getElementById('status-line'),
        downloadResults: document.getElementById('download-results')
    };

    // Templates
    const templates = {
        playerItem: document.getElementById('player-item-template'),
        pointItem: document.getElementById('point-item-template')
    };

    // Initialize event listeners
    function initEventListeners() {
        console.log("Initializing event listeners");
        
        // File upload events
        elements.dropArea.addEventListener('click', () => elements.fileUpload.click());
        elements.fileUpload.addEventListener('change', handleFileSelect);
        elements.dropArea.addEventListener('dragover', handleDragOver);
        elements.dropArea.addEventListener('dragleave', handleDragLeave);
        elements.dropArea.addEventListener('drop', handleFileDrop);
        
        // Canvas events - add multiple event types for debugging
        elements.annotationCanvas.addEventListener('click', handleCanvasClick);
        elements.annotationCanvas.addEventListener('mousedown', (e) => {
            console.log("Canvas mousedown detected");
        });
        
        // Also add a click handler directly to the container
        elements.canvasContainer.addEventListener('click', (e) => {
            console.log("Canvas container clicked");
            // Show a temporary marker at click location
            const marker = document.createElement('div');
            marker.style.position = 'absolute';
            marker.style.left = (e.clientX - elements.canvasContainer.getBoundingClientRect().left) + 'px';
            marker.style.top = (e.clientY - elements.canvasContainer.getBoundingClientRect().top) + 'px';
            marker.style.width = '20px';
            marker.style.height = '20px';
            marker.style.backgroundColor = 'yellow';
            marker.style.borderRadius = '50%';
            marker.style.zIndex = '1000';
            elements.canvasContainer.appendChild(marker);
            
            // Remove after 2 seconds
            setTimeout(() => {
                elements.canvasContainer.removeChild(marker);
            }, 2000);
        });
        
        // Window resize event for canvas redrawing
        window.addEventListener('resize', () => {
            if (state.imageData) {
                drawCanvas();
            }
        });
        
        // Button events
        elements.startPlayerSelection.addEventListener('click', startPlayerSelection);
        elements.nextPlayer.addEventListener('click', nextPlayer);
        elements.endPointCollection.addEventListener('click', endPointCollection);
        elements.clearPoints.addEventListener('click', clearCurrentPlayerPoints);
        
        // Point type selection
        elements.pointTypeRadios.forEach(radio => {
            radio.addEventListener('change', (e) => {
                state.pointType = e.target.value;
                updatePointTypeIndicator();
            });
        });
        
        // Processing buttons
        elements.generateMasks.addEventListener('click', generateMasks);
        elements.trackAnnotate.addEventListener('click', trackAndAnnotate);
        
        // Download results
        elements.downloadResults.addEventListener('click', downloadResults);
        
        // Frame slider
        elements.frameSlider.addEventListener('input', updateFramePreview);
    }

    // File upload handling
    function handleDragOver(e) {
        e.preventDefault();
        elements.dropArea.classList.add('drag-over');
    }

    function handleDragLeave(e) {
        e.preventDefault();
        elements.dropArea.classList.remove('drag-over');
    }

    function handleFileDrop(e) {
        e.preventDefault();
        elements.dropArea.classList.remove('drag-over');
        
        if (e.dataTransfer.files.length) {
            elements.fileUpload.files = e.dataTransfer.files;
            handleFileSelect();
        }
    }

    function handleFileSelect() {
        const file = elements.fileUpload.files[0];
        if (!file) return;
        
        // Check file type
        const validTypes = ['video/mp4', 'video/quicktime', 'video/avi'];
        if (!validTypes.includes(file.type)) {
            showUploadError('Please select a valid video file (MP4, MOV, or AVI)');
            return;
        }
        
        // Check file size (max 500MB)
        if (file.size > 500 * 1024 * 1024) {
            showUploadError('File size exceeds 500MB limit');
            return;
        }
        
        // Reset error
        elements.uploadError.classList.add('d-none');
        
        // Show progress
        elements.uploadProgress.classList.remove('d-none');
        elements.uploadProgressBar.style.width = '0%';
        elements.uploadProgressBar.setAttribute('aria-valuenow', 0);
        
        // Upload file
        uploadFile(file);
    }

    function showUploadError(message) {
        elements.uploadError.textContent = message;
        elements.uploadError.classList.remove('d-none');
        elements.uploadProgress.classList.add('d-none');
    }

    function uploadFile(file) {
        const formData = new FormData();
        formData.append('video', file);
        
        const xhr = new XMLHttpRequest();
        
        xhr.upload.addEventListener('progress', (e) => {
            if (e.lengthComputable) {
                const percentComplete = Math.round((e.loaded / e.total) * 100);
                elements.uploadProgressBar.style.width = percentComplete + '%';
                elements.uploadProgressBar.setAttribute('aria-valuenow', percentComplete);
            }
        });
        
        xhr.addEventListener('load', () => {
            if (xhr.status === 200) {
                const response = JSON.parse(xhr.responseText);
                handleUploadSuccess(response);
            } else {
                try {
                    const error = JSON.parse(xhr.responseText).error || 'Upload failed';
                    showUploadError(error);
                } catch (e) {
                    showUploadError('Upload failed: ' + xhr.statusText);
                }
            }
        });
        
        xhr.addEventListener('error', () => {
            showUploadError('Network error occurred');
        });
        
        xhr.open('POST', '/upload', true);
        xhr.send(formData);
    }

    function handleUploadSuccess(response) {
        // Store session ID and image dimensions
        state.sessionId = response.session_id;
        state.canvasWidth = response.width;
        state.canvasHeight = response.height;
        
        // Load image
        const img = new Image();
        img.onload = () => {
            // Save image data
            state.imageData = img;
            
            // Hide upload area, show annotation area
            elements.uploadArea.classList.add('d-none');
            elements.annotationArea.classList.remove('d-none');
            
            // Initialize canvas
            initCanvas();
        };
        img.src = response.first_frame;
    }

    // Canvas initialization and handling
    function initCanvas() {
        const canvas = elements.annotationCanvas;
        const ctx = canvas.getContext('2d');
        
        console.log("Initializing canvas");
        
        // Set canvas dimensions to match the original image
        canvas.width = state.canvasWidth;
        canvas.height = state.canvasHeight;
        
        console.log(`Set canvas dimensions to ${canvas.width}x${canvas.height}`);
        
        // Set container dimensions to fit in the available space while maintaining aspect ratio
        const container = elements.canvasContainer;
        const containerWidth = container.clientWidth;
        
        // Set canvas CSS dimensions
        canvas.style.width = '100%';
        canvas.style.height = 'auto';
        
        console.log(`Canvas display dimensions: ${canvas.getBoundingClientRect().width}x${canvas.getBoundingClientRect().height}`);
        
        // Draw image
        ctx.drawImage(state.imageData, 0, 0, canvas.width, canvas.height);
        
        // Update status
        elements.annotationStatus.textContent = 'Ready';
        elements.annotationStatus.classList.remove('bg-info', 'bg-warning', 'bg-success');
        elements.annotationStatus.classList.add('bg-info');
        
        // MAJOR CHANGE: Remove the old click handler and add a new one directly to the canvas container
        // that bypasses the scaling issues
        elements.annotationCanvas.removeEventListener('click', handleCanvasClick);
        
        // Add magnifier element
        let magnifier = document.getElementById('magnifier');
        if (!magnifier) {
            magnifier = document.createElement('div');
            magnifier.id = 'magnifier';
            magnifier.className = 'magnifier';
            container.appendChild(magnifier);
        }
        
        // Add overlay div for better click handling
        const overlay = document.createElement('div');
        overlay.id = 'canvas-overlay';
        overlay.style.position = 'absolute';
        overlay.style.top = '0';
        overlay.style.left = '0';
        overlay.style.width = '100%';
        overlay.style.height = '100%';
        overlay.style.cursor = 'crosshair';
        overlay.style.zIndex = '10';
        
        // Remove any existing overlay
        const existingOverlay = document.getElementById('canvas-overlay');
        if (existingOverlay) {
            container.removeChild(existingOverlay);
        }
        
        container.appendChild(overlay);
        
        // Add mousemove handler for magnifier
        overlay.addEventListener('mousemove', function(e) {
            if (!state.selectingPoints) {
                magnifier.style.display = 'none';
                return;
            }
            
            // Get mouse position
            const rect = overlay.getBoundingClientRect();
            const mouseX = e.clientX - rect.left;
            const mouseY = e.clientY - rect.top;
            
            // Convert to canvas coordinates for magnifier background position
            const canvasRect = canvas.getBoundingClientRect();
            const scaleX = canvas.width / canvasRect.width;
            const scaleY = canvas.height / canvasRect.height;
            
            // Position the magnifier
            magnifier.style.left = (mouseX - 75) + 'px';
            magnifier.style.top = (mouseY - 75) + 'px';
            
            // Calculate background position
            const bgX = -mouseX * 2 + 75;
            const bgY = -mouseY * 2 + 75;
            
            // Set background image from canvas
            magnifier.style.backgroundImage = `url(${canvas.toDataURL()})`;
            magnifier.style.backgroundPosition = `${bgX}px ${bgY}px`;
            magnifier.style.backgroundSize = `${canvasRect.width * 2}px ${canvasRect.height * 2}px`;
            magnifier.style.display = 'block';
        });
        
        // Hide magnifier when mouse leaves the overlay
        overlay.addEventListener('mouseleave', function() {
            magnifier.style.display = 'none';
        });
        
        // Add click handler to the overlay
        overlay.addEventListener('click', function(e) {
            // Explicitly use the window.state instead of closure reference to avoid scope issues
            console.log("Overlay clicked - Current State:", JSON.stringify({
                selectingPoints: state.selectingPoints,
                currentPlayer: state.currentPlayer,
                pointType: state.pointType
            }));
            
            if (!state.selectingPoints || state.currentPlayer === null) {
                console.log("Click ignored: not in point selection mode or no current player");
                return;
            }
            
            console.log("Overlay clicked - Processing click");
            
            // Get click position relative to the container
            const rect = overlay.getBoundingClientRect();
            const clickX = e.clientX - rect.left;
            const clickY = e.clientY - rect.top;
            
            // Convert to canvas coordinates
            const canvasRect = canvas.getBoundingClientRect();
            const scaleX = canvas.width / canvasRect.width;
            const scaleY = canvas.height / canvasRect.height;
            
            const canvasX = Math.round(clickX * scaleX);
            const canvasY = Math.round(clickY * scaleY);
            
            console.log(`Click at (${clickX}, ${clickY}) -> Canvas: (${canvasX}, ${canvasY})`);
            
            // Show visual feedback (temporary marker)
            const marker = document.createElement('div');
            marker.style.position = 'absolute';
            marker.style.left = (clickX - 10) + 'px';
            marker.style.top = (clickY - 10) + 'px';
            marker.style.width = '20px';
            marker.style.height = '20px';
            marker.style.backgroundColor = state.pointType === 'positive' ? 'rgba(40, 167, 69, 0.8)' : 'rgba(220, 53, 69, 0.8)';
            marker.style.borderRadius = '50%';
            marker.style.border = '2px solid white';
            marker.style.zIndex = '20';
            overlay.appendChild(marker);
            
            // Remove after animation
            setTimeout(() => {
                overlay.removeChild(marker);
            }, 1000);
            
            // Add the point
            addPoint(canvasX, canvasY);
        });
    }

    function drawCanvas() {
        drawCanvasWithMasks();
    }

    function handleCanvasClick(e) {
        if (!state.selectingPoints || !state.currentPlayer) return;
        
        console.log("Canvas clicked"); // Debugging
        
        // Get click coordinates relative to canvas with proper scaling
        const rect = elements.annotationCanvas.getBoundingClientRect();
        const canvas = elements.annotationCanvas;
        
        // Calculate the scale factor between actual canvas dimensions and displayed dimensions
        const scaleX = canvas.width / rect.width;
        const scaleY = canvas.height / rect.height;
        
        // Calculate clicked position in canvas coordinates
        const x = Math.round((e.clientX - rect.left) * scaleX);
        const y = Math.round((e.clientY - rect.top) * scaleY);
        
        console.log(`Click at: ${x}, ${y} (Canvas: ${canvas.width}x${canvas.height}, Display: ${rect.width}x${rect.height})`);
        
        // Add point to current player
        addPoint(x, y);
    }

    function addPoint(x, y) {
        console.log(`Adding point at ${x}, ${y} with type ${state.pointType}`);
        
        // Calculate normalized coordinates
        const normX = parseFloat((x / state.canvasWidth).toFixed(3));
        const normY = parseFloat((y / state.canvasHeight).toFixed(3));
        
        console.log(`Normalized coordinates: ${normX}, ${normY}`);
        
        // First, clear any existing mask for this player to show that it's being updated
        if (state.players[state.currentPlayer] && state.players[state.currentPlayer].maskImage) {
            // Remove the mask immediately from visual display
            delete state.players[state.currentPlayer].maskImage;
            // Redraw canvas without the mask
            drawCanvas();
        }
        
        // Update status to show we're updating
        elements.annotationStatus.textContent = "Adding point...";
        elements.annotationStatus.classList.remove('bg-info', 'bg-warning', 'bg-success');
        elements.annotationStatus.classList.add('bg-warning');
        
        // Add to server
        fetch('/add_point', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                session_id: state.sessionId,
                obj_id: state.currentPlayer,
                point: [normX, normY],
                point_type: state.pointType
            })
        })
        .then(response => {
            if (!response.ok) {
                throw new Error(`Server returned ${response.status}: ${response.statusText}`);
            }
            return response.json();
        })
        .then(data => {
            console.log('Server response:', data);
            
            if (data.success) {
                // Add to local state
                const point = {
                    x: x,
                    y: y,
                    type: state.pointType,
                    playerId: state.currentPlayer,
                    pointId: data.point_id
                };
                
                state.canvasPoints.push(point);
                console.log(`Added point to canvas points. Total: ${state.canvasPoints.length}`);
                
                // Update player data
                if (!state.players[state.currentPlayer]) {
                    state.players[state.currentPlayer] = {
                        points: [],
                        color: getPlayerColor(state.currentPlayer)
                    };
                }
                
                state.players[state.currentPlayer].points.push({
                    normX: normX,
                    normY: normY,
                    type: state.pointType,
                    pointId: data.point_id
                });
                
                // Redraw canvas with the new point (but without mask yet)
                drawCanvas();
                
                // Update points list
                updatePointsList();
                
                // Update player item
                updatePlayerItem(state.currentPlayer);
                
                // Generate new mask after adding the point
                // This will show a loading indicator and create a new mask
                generateMaskForCurrentPlayer();
            } else {
                console.error('Failed to add point:', data.error || 'Unknown error');
                // Restore status
                elements.annotationStatus.textContent = "Point addition failed";
                elements.annotationStatus.classList.remove('bg-info', 'bg-warning', 'bg-success');
                elements.annotationStatus.classList.add('bg-danger');
            }
        })
        .catch(error => {
            console.error('Error adding point:', error);
            alert('Failed to add point: ' + error.message);
            // Restore status
            elements.annotationStatus.textContent = "Error";
            elements.annotationStatus.classList.remove('bg-info', 'bg-warning', 'bg-success');
            elements.annotationStatus.classList.add('bg-danger');
        });
    }

    // New function to generate mask just for the current player
    function generateMaskForCurrentPlayer() {
        const playerId = state.currentPlayer;
        if (playerId === null || !state.players[playerId] || state.players[playerId].points.length === 0) {
            console.log("Can't generate mask: no current player or no points");
            return;
        }
        
        // Count the number of points
        const pointCount = state.players[playerId].points.length;
        console.log(`Generating mask using ${pointCount} points`);
        
        // Show loading indicator
        const statusText = elements.annotationStatus.textContent;
        elements.annotationStatus.textContent = `Generating mask with ${pointCount} points...`;
        elements.annotationStatus.classList.remove('bg-info', 'bg-warning', 'bg-success');
        elements.annotationStatus.classList.add('bg-warning');
        
        // First, clear any existing mask from the display while generating
        if (state.players[playerId].maskImage) {
            const oldMask = state.players[playerId].maskImage;
            delete state.players[playerId].maskImage;
            drawCanvas(); // Redraw without the mask to show it's updating
        }
        
        // Make API call for this specific player
        fetch('/generate_mask_for_player', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                session_id: state.sessionId,
                obj_id: playerId
            })
        })
        .then(response => response.json())
        .then(data => {
            console.log("Mask generation response:", data);
            
            if (data.success) {
                // Check if the server used all the points
                const serverPointCount = data.point_count || 0;
                if (serverPointCount !== pointCount) {
                    console.warn(`Warning: Server used ${serverPointCount} points but client has ${pointCount} points`);
                }
                
                // Load the mask image
                const maskImage = new Image();
                maskImage.onload = () => {
                    // Store mask in player data
                    state.players[playerId].maskImage = maskImage;
                    
                    // Draw the canvas with the mask
                    drawCanvasWithMasks();
                    
                    // Update status with point count
                    elements.annotationStatus.textContent = `Mask updated with ${serverPointCount} points`;
                    elements.annotationStatus.classList.remove('bg-info', 'bg-warning', 'bg-success');
                    elements.annotationStatus.classList.add('bg-success');
                    
                    // Reset status after 2 seconds
                    setTimeout(() => {
                        elements.annotationStatus.textContent = `Player ${playerId} - ${serverPointCount} points`;
                        elements.annotationStatus.classList.remove('bg-info', 'bg-warning', 'bg-success');
                        elements.annotationStatus.classList.add('bg-success');
                    }, 2000);
                };
                maskImage.src = data.preview;
            } else {
                console.error("Failed to generate mask:", data.error);
                elements.annotationStatus.textContent = "Mask generation failed";
                elements.annotationStatus.classList.remove('bg-info', 'bg-warning', 'bg-success');
                elements.annotationStatus.classList.add('bg-danger');
                
                // Reset status after 2 seconds
                setTimeout(() => {
                    elements.annotationStatus.textContent = statusText;
                    elements.annotationStatus.classList.remove('bg-info', 'bg-warning', 'bg-success', 'bg-danger');
                    elements.annotationStatus.classList.add('bg-success');
                }, 2000);
            }
        })
        .catch(error => {
            console.error("Error generating mask:", error);
            elements.annotationStatus.textContent = "Mask generation error";
            elements.annotationStatus.classList.remove('bg-info', 'bg-warning', 'bg-success');
            elements.annotationStatus.classList.add('bg-danger');
            
            // Reset status after 2 seconds
            setTimeout(() => {
                elements.annotationStatus.textContent = statusText;
                elements.annotationStatus.classList.remove('bg-info', 'bg-warning', 'bg-success', 'bg-danger');
                elements.annotationStatus.classList.add('bg-success');
            }, 2000);
        });
    }
    
    // Modified drawing function to include masks
    function drawCanvasWithMasks() {
        const canvas = elements.annotationCanvas;
        const ctx = canvas.getContext('2d');
        
        // Clear canvas and redraw image
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        ctx.drawImage(state.imageData, 0, 0, canvas.width, canvas.height);
        
        // Draw masks if available
        Object.entries(state.players).forEach(([playerId, playerData]) => {
            if (playerData.maskImage) {
                // Draw mask with semi-transparency
                ctx.globalAlpha = 0.5;
                const color = playerData.color;
                if (typeof color === 'string') {
                    // Parse color string like "rgb(r, g, b)"
                    const match = color.match(/rgb\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\)/);
                    if (match) {
                        const [_, r, g, b] = match;
                        ctx.fillStyle = `rgba(${r}, ${g}, ${b}, 0.5)`;
                    } else {
                        ctx.fillStyle = color;
                    }
                } else if (Array.isArray(color)) {
                    // Use array color [r, g, b]
                    ctx.fillStyle = `rgba(${color[0]}, ${color[1]}, ${color[2]}, 0.5)`;
                }
                
                // Draw the mask
                ctx.drawImage(playerData.maskImage, 0, 0, canvas.width, canvas.height);
                ctx.globalAlpha = 1.0;
            }
        });
        
        // Draw all points on top of masks
        state.canvasPoints.forEach(point => {
            ctx.beginPath();
            ctx.arc(point.x, point.y, 8, 0, Math.PI * 2);
            
            if (point.type === 'positive') {
                ctx.fillStyle = 'rgba(40, 167, 69, 0.8)'; // green
            } else {
                ctx.fillStyle = 'rgba(220, 53, 69, 0.8)'; // red
            }
            
            ctx.fill();
            ctx.strokeStyle = 'white';
            ctx.lineWidth = 2;
            ctx.stroke();
        });
    }

    function removePoint(playerId, pointId) {
        fetch('/remove_point', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                session_id: state.sessionId,
                obj_id: playerId,
                point_id: pointId
            })
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                // Remove from canvas points
                const pointIndex = state.canvasPoints.findIndex(p => 
                    p.playerId === playerId && p.pointId === pointId);
                
                if (pointIndex !== -1) {
                    state.canvasPoints.splice(pointIndex, 1);
                }
                
                // Remove from player data
                const playerPoints = state.players[playerId].points;
                const playerPointIndex = playerPoints.findIndex(p => p.pointId === pointId);
                
                if (playerPointIndex !== -1) {
                    playerPoints.splice(playerPointIndex, 1);
                }
                
                // Redraw canvas (this will temporarily remove mask until regenerated)
                drawCanvas();
                
                // Update points list if this is the current player
                if (playerId === state.currentPlayer) {
                    updatePointsList();
                }
                
                // Update player item
                updatePlayerItem(playerId);
                
                // Regenerate mask if there are still points remaining
                if (playerPoints.length > 0 && playerId === state.currentPlayer) {
                    generateMaskForCurrentPlayer();
                } else if (playerPoints.length === 0) {
                    // If no points remain, clear any existing mask
                    if (state.players[playerId].maskImage) {
                        delete state.players[playerId].maskImage;
                        drawCanvas(); // Redraw without the mask
                    }
                }
            }
        })
        .catch(error => {
            console.error('Error removing point:', error);
        });
    }

    // Player management
    function startPlayerSelection() {
        console.log("startPlayerSelection called");
        
        // Start selecting points
        state.selectingPoints = true;
        state.pointType = 'positive';
        
        console.log("State updated: selectingPoints=true, pointType=positive");
        
        // Add new player
        fetch('/add_player', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                session_id: state.sessionId
            })
        })
        .then(response => response.json())
        .then(data => {
            console.log("Server response for add_player:", data);
            
            // Set as current player
            state.currentPlayer = data.obj_id;
            
            // Initialize player data
            state.players[data.obj_id] = {
                points: [],
                color: data.color
            };
            
            console.log(`Current player set to: ${data.obj_id}`);
            console.log("Updated state:", JSON.stringify({
                selectingPoints: state.selectingPoints,
                currentPlayer: state.currentPlayer,
                pointType: state.pointType
            }));
            
            // Add player to UI
            addPlayerItem(data.obj_id, data.color);
            
            // Show point type selection
            elements.pointTypeSelection.classList.remove('d-none');
            
            // Show current player points
            elements.currentPlayerPoints.classList.remove('d-none');
            elements.currentPlayerId.textContent = data.obj_id;
            
            // Hide instructions
            elements.annotationInstructions.classList.add('d-none');
            
            // Update button states
            elements.startPlayerSelection.disabled = true;
            elements.nextPlayer.disabled = false;
            elements.endPointCollection.disabled = false;
            
            // Update point type indicator
            updatePointTypeIndicator();
            
            // Update status
            elements.annotationStatus.textContent = 'Selecting Player ' + data.obj_id;
            elements.annotationStatus.classList.remove('bg-info', 'bg-warning', 'bg-success');
            elements.annotationStatus.classList.add('bg-success');
            
            // Force create a new overlay to ensure it uses the current state
            initCanvas();
        })
        .catch(error => {
            console.error('Error starting player selection:', error);
        });
    }

    function nextPlayer() {
        // Add new player
        fetch('/add_player', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                session_id: state.sessionId
            })
        })
        .then(response => response.json())
        .then(data => {
            // Set as current player
            state.currentPlayer = data.obj_id;
            
            // Initialize player data
            state.players[data.obj_id] = {
                points: [],
                color: data.color
            };
            
            // Add player to UI
            addPlayerItem(data.obj_id, data.color);
            
            // Update current player ID
            elements.currentPlayerId.textContent = data.obj_id;
            
            // Clear points list
            elements.pointsList.innerHTML = '';
            
            // Update status
            elements.annotationStatus.textContent = 'Selecting Player ' + data.obj_id;
        })
        .catch(error => {
            console.error('Error adding player:', error);
        });
    }

    function endPointCollection() {
        // End point selection
        state.selectingPoints = false;
        state.currentPlayer = null;
        
        // Hide point type selection
        elements.pointTypeSelection.classList.add('d-none');
        
        // Hide current player points
        elements.currentPlayerPoints.classList.add('d-none');
        
        // Show instructions
        elements.annotationInstructions.classList.remove('d-none');
        
        // Update button states
        elements.startPlayerSelection.disabled = true;
        elements.nextPlayer.disabled = true;
        elements.endPointCollection.disabled = true;
        
        // Show processing buttons
        elements.processingButtons.classList.remove('d-none');
        
        // Update status
        elements.annotationStatus.textContent = 'Ready to Process';
        elements.annotationStatus.classList.remove('bg-info', 'bg-warning', 'bg-success');
        elements.annotationStatus.classList.add('bg-info');
    }

    function clearCurrentPlayerPoints() {
        if (!state.currentPlayer) return;
        
        fetch('/clear_points', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                session_id: state.sessionId,
                obj_id: state.currentPlayer
            })
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                // Clear points from canvas
                state.canvasPoints = state.canvasPoints.filter(p => p.playerId !== state.currentPlayer);
                
                // Clear player data
                state.players[state.currentPlayer].points = [];
                
                // Remove any existing mask
                if (state.players[state.currentPlayer].maskImage) {
                    delete state.players[state.currentPlayer].maskImage;
                }
                
                // Redraw canvas
                drawCanvas();
                
                // Update points list
                updatePointsList();
                
                // Update player item
                updatePlayerItem(state.currentPlayer);
                
                // Update status message
                elements.annotationStatus.textContent = `Points cleared for Player ${state.currentPlayer}`;
                elements.annotationStatus.classList.remove('bg-success', 'bg-warning', 'bg-danger');
                elements.annotationStatus.classList.add('bg-info');
            }
        })
        .catch(error => {
            console.error('Error clearing points:', error);
        });
    }

    // UI updates
    function updatePointTypeIndicator() {
        // Update radio button
        document.getElementById(state.pointType + '-point').checked = true;
        
        // Update indicator
        elements.currentPointType.textContent = 
            state.pointType === 'positive' ? 'Positive Point' : 'Negative Point';
        
        elements.currentPointType.className = 'badge ' + 
            (state.pointType === 'positive' ? 'bg-success' : 'bg-danger');
    }

    function addPlayerItem(playerId, color) {
        // Hide no players message
        elements.noPlayersMessage.classList.add('d-none');
        
        // Clone template
        const template = templates.playerItem.content.cloneNode(true);
        const playerItem = template.querySelector('.player-item');
        
        // Set player ID
        playerItem.dataset.playerId = playerId;
        playerItem.querySelector('.player-id').textContent = playerId;
        
        // Set color
        const colorDot = playerItem.querySelector('.player-color-dot');
        colorDot.style.backgroundColor = `rgb(${color[0]}, ${color[1]}, ${color[2]})`;
        
        // Add event listener to select button
        const selectButton = playerItem.querySelector('.select-player');
        selectButton.addEventListener('click', () => selectPlayer(playerId));
        
        // Add to players list
        elements.playersList.appendChild(playerItem);
    }

    function updatePlayerItem(playerId) {
        const playerItem = document.querySelector(`.player-item[data-player-id="${playerId}"]`);
        if (!playerItem) return;
        
        const pointsCount = state.players[playerId].points.length;
        playerItem.querySelector('.player-points-count').textContent = `${pointsCount} points`;
        
        // Add animation class
        playerItem.classList.add('point-added');
        setTimeout(() => {
            playerItem.classList.remove('point-added');
        }, 300);
    }

    function updatePointsList() {
        if (!state.currentPlayer) return;
        
        // Clear list
        elements.pointsList.innerHTML = '';
        
        // Get points for current player
        const points = state.players[state.currentPlayer].points;
        
        // Add each point to the list
        points.forEach((point, index) => {
            // Clone template
            const template = templates.pointItem.content.cloneNode(true);
            const pointItem = template.querySelector('.point-item');
            
            // Set point data
            pointItem.dataset.pointId = point.pointId;
            
            // Set type indicator
            const typeIndicator = pointItem.querySelector('.point-type-indicator');
            typeIndicator.classList.add('point-type-' + point.type);
            
            // Set coordinates
            pointItem.querySelector('.point-coords').textContent = 
                `(${point.normX.toFixed(3)}, ${point.normY.toFixed(3)})`;
            
            // Add event listener to remove button
            const removeButton = pointItem.querySelector('.remove-point');
            removeButton.addEventListener('click', () => {
                removePoint(state.currentPlayer, point.pointId);
            });
            
            // Add to points list
            elements.pointsList.appendChild(pointItem);
        });
    }

    function selectPlayer(playerId) {
        // Can only select if not already selecting points
        if (state.selectingPoints) return;
        
        // Set current player
        state.currentPlayer = playerId;
        state.selectingPoints = true;
        
        // Update UI
        elements.currentPlayerId.textContent = playerId;
        elements.currentPlayerPoints.classList.remove('d-none');
        elements.pointTypeSelection.classList.remove('d-none');
        elements.annotationInstructions.classList.add('d-none');
        
        // Update button states
        elements.startPlayerSelection.disabled = true;
        elements.nextPlayer.disabled = false;
        elements.endPointCollection.disabled = false;
        
        // Update points list
        updatePointsList();
        
        // Update status
        elements.annotationStatus.textContent = 'Selecting Player ' + playerId;
        elements.annotationStatus.classList.remove('bg-info', 'bg-warning', 'bg-success');
        elements.annotationStatus.classList.add('bg-success');
    }

    // Processing functions
    function generateMasks() {
        // Update UI
        elements.annotationStatus.textContent = 'Generating Masks...';
        elements.annotationStatus.classList.remove('bg-info', 'bg-warning', 'bg-success');
        elements.annotationStatus.classList.add('bg-warning');
        
        // Disable buttons
        elements.generateMasks.disabled = true;
        
        // Make API call
        fetch('/generate_masks', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                session_id: state.sessionId
            })
        })
        .then(response => response.json())
        .then(data => {
            // Show results
            elements.resultsArea.classList.remove('d-none');
            elements.maskPreview.src = data.combined_preview;
            
            // Update UI
            elements.annotationStatus.textContent = 'Masks Generated';
            elements.annotationStatus.classList.remove('bg-info', 'bg-warning', 'bg-success');
            elements.annotationStatus.classList.add('bg-success');
            
            // Show track button
            elements.trackAnnotate.classList.remove('d-none');
            
            // Process individual results
            data.results.forEach(result => {
                if (!result.success) {
                    console.warn(`Failed to generate mask for player ${result.obj_id}: ${result.error}`);
                }
            });
        })
        .catch(error => {
            console.error('Error generating masks:', error);
            elements.annotationStatus.textContent = 'Error Generating Masks';
            elements.annotationStatus.classList.remove('bg-info', 'bg-warning', 'bg-success');
            elements.annotationStatus.classList.add('bg-danger');
            elements.generateMasks.disabled = false;
        });
    }

    function trackAndAnnotate() {
        // Update UI
        elements.annotationStatus.textContent = 'Tracking and Annotating...';
        elements.annotationStatus.classList.remove('bg-info', 'bg-warning', 'bg-success');
        elements.annotationStatus.classList.add('bg-warning');
        
        // Disable buttons
        elements.trackAnnotate.disabled = true;
        
        // Show progress area
        elements.trackingProgress.classList.remove('d-none');
        elements.progressBar.style.width = '0%';
        elements.progressBar.setAttribute('aria-valuenow', 0);
        
        // Set initial status
        updateStatusLine('Starting tracking process...', 'info');
        
        // Make API call
        fetch('/track_and_annotate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                session_id: state.sessionId
            })
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                // Start polling for progress
                startProgressPolling();
            } else {
                // Update UI on error
                elements.annotationStatus.textContent = 'Tracking Failed';
                elements.annotationStatus.classList.remove('bg-info', 'bg-warning', 'bg-success');
                elements.annotationStatus.classList.add('bg-danger');
                
                // Show error message
                updateStatusLine('Error: ' + data.error, 'danger');
                
                // Re-enable button
                elements.trackAnnotate.disabled = false;
            }
        })
        .catch(error => {
            console.error('Error starting tracking and annotating:', error);
            elements.annotationStatus.textContent = 'Tracking Failed';
            elements.annotationStatus.classList.remove('bg-info', 'bg-warning', 'bg-success');
            elements.annotationStatus.classList.add('bg-danger');
            
            // Show error message
            updateStatusLine('Network error occurred', 'danger');
            
            // Re-enable button
            elements.trackAnnotate.disabled = false;
        });
    }

    // Function to initialize the frame slider once tracking is complete
    function initFrameSlider(totalFrames) {
        // Reset and set up frame slider
        elements.frameSlider.min = 0;
        elements.frameSlider.max = totalFrames - 1;
        elements.frameSlider.value = 0;
        elements.currentFrame.textContent = `Frame: 0`;
        
        // Show tracking results area
        elements.trackingResults.classList.remove('d-none');
        
        // Load the first frame
        updateFramePreview();
    }

    // Update the frame preview when slider is moved
    function updateFramePreview() {
        const frameIndex = parseInt(elements.frameSlider.value);
        elements.currentFrame.textContent = `Frame: ${frameIndex}`;
        
        // Show loading indicator
        elements.trackingPreview.src = "data:image/svg+xml;charset=utf8,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100' preserveAspectRatio='xMidYMid'%3E%3Ccircle cx='50' cy='50' fill='none' stroke='%233498db' stroke-width='10' r='35' stroke-dasharray='164.93361431346415 56.97787143782138'%3E%3CanimateTransform attributeName='transform' type='rotate' repeatCount='indefinite' dur='1s' values='0 50 50;360 50 50' keyTimes='0;1'%3E%3C/animateTransform%3E%3C/circle%3E%3C/svg%3E";
        
        // Load the frame from the server
        elements.trackingPreview.src = `/get_frame_preview/${state.sessionId}/${frameIndex}?t=${new Date().getTime()}`;
        
        // Add error handler
        elements.trackingPreview.onerror = function() {
            elements.trackingPreview.src = "data:image/svg+xml;charset=utf8,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'%3E%3Ctext x='50%' y='50%' text-anchor='middle' dominant-baseline='middle' font-family='sans-serif' font-size='14'%3EFrame not available%3C/text%3E%3C/svg%3E";
        };
    }

    // Update the progress polling function to use status line
    function startProgressPolling() {
        let pollInterval = null;
        let lastUpdateCount = 0;
        let sliderInitialized = false;
        let lastStatus = '';
        
        function checkProgress() {
            fetch(`/check_tracking_progress?session_id=${state.sessionId}`)
                .then(response => response.json())
                .then(progressData => {
                    // Update the progress bar
                    const percent = Math.round(progressData.progress * 100);
                    elements.progressBar.style.width = `${percent}%`;
                    elements.progressBar.setAttribute('aria-valuenow', percent);
                    
                    // Update status message if changed
                    if (progressData.status && progressData.status !== lastStatus) {
                        updateStatusLine(`Status: ${progressData.status}`, 'info');
                        lastStatus = progressData.status;
                    }
                    
                    // Check for the most recent progress update
                    if (progressData.updates && progressData.updates.length > 0) {
                        const latestUpdate = progressData.updates[progressData.updates.length - 1];
                        updateStatusLine(latestUpdate.message, 'info');
                        
                        // If there's a preview image, update it
                        if (latestUpdate.preview) {
                            elements.trackingResults.classList.remove('d-none');
                            elements.trackingPreview.src = latestUpdate.preview;
                        }
                    }
                    
                    // Check if processing is complete
                    if (progressData.is_complete) {
                        // Stop polling
                        clearInterval(pollInterval);
                        
                        if (progressData.success) {
                            // Update UI for success
                            elements.annotationStatus.textContent = 'Tracking Complete';
                            elements.annotationStatus.classList.remove('bg-info', 'bg-warning', 'bg-success');
                            elements.annotationStatus.classList.add('bg-success');
                            
                            // Add completion message
                            const completionMessage = document.createElement('div');
                            completionMessage.className = 'alert alert-success mt-3';
                            completionMessage.innerHTML = '<strong>Processing Complete!</strong> Results are ready for download.';
                            
                            // Replace progress tracking with completion message
                            elements.trackingProgress.innerHTML = '';
                            elements.trackingProgress.appendChild(completionMessage);
                            
                            // Store download URL
                            if (progressData.download_url) {
                                state.downloadUrl = progressData.download_url;
                                
                                // Enable download button
                                elements.downloadResults.disabled = false;
                            }
                            
                            // Initialize the frame slider if not already done
                            if (!sliderInitialized && progressData.total_frames) {
                                initFrameSlider(progressData.total_frames);
                                sliderInitialized = true;
                            }
                        } else {
                            // Update UI for failure
                            elements.annotationStatus.textContent = 'Tracking Failed';
                            elements.annotationStatus.classList.remove('bg-info', 'bg-warning', 'bg-success');
                            elements.annotationStatus.classList.add('bg-danger');
                            
                            // Show error message
                            updateStatusLine('Error: ' + (progressData.error || 'Unknown error'), 'danger');
                            
                            // Re-enable tracking button
                            elements.trackAnnotate.disabled = false;
                        }
                    }
                })
                .catch(error => {
                    console.error('Error checking progress:', error);
                    updateStatusLine('Error checking progress. Will retry...', 'warning');
                });
        }
        
        // Check immediately, then start polling every 2 seconds
        checkProgress();
        pollInterval = setInterval(checkProgress, 2000);
    }

    function updateStatusLine(message, type = 'info') {
        elements.statusLine.className = `alert alert-${type} mb-2`;
        elements.statusLine.textContent = message;
    }

    function downloadResults() {
        if (state.downloadUrl) {
            window.location.href = state.downloadUrl;
        }
    }

    // Utility functions
    function getPlayerColor(playerId) {
        const player = document.querySelector(`.player-item[data-player-id="${playerId}"]`);
        if (player) {
            const colorDot = player.querySelector('.player-color-dot');
            return colorDot.style.backgroundColor;
        }
        return 'rgb(0, 0, 0)';
    }

    // Initialize the application
    initEventListeners();
}); 