document.addEventListener('DOMContentLoaded', function() {
    console.log("Basketball analytics visualization loaded");
    
    // Add red marker dots to the court diagram representing players
    const courtDiagram = document.querySelector('.diagram-court');
    
    // Add markers for each player on the court diagram
    addDiagramMarker(courtDiagram, 'player-119-marker', 25, 70, '#ff0000');
    addDiagramMarker(courtDiagram, 'player-10-marker', 60, 50, '#00ff00');
    addDiagramMarker(courtDiagram, 'player-52-marker', 55, 61, '#00ff00');
    addDiagramMarker(courtDiagram, 'player-85-marker', 90, 60, '#ff0000');
    
    // Add circle visuals around players to show movement/speed
    document.querySelectorAll('.player-marker').forEach(player => {
        const id = player.id;
        const playerElement = document.getElementById(id);
        
        // Create a speed indicator circle
        const speedCircle = document.createElement('div');
        speedCircle.className = 'speed-circle';
        
        // Set different sizes based on player
        if (id === 'player-119') {
            speedCircle.style.width = '60px';
            speedCircle.style.height = '60px';
        } else if (id === 'player-10') {
            speedCircle.style.width = '50px';
            speedCircle.style.height = '50px';
        } else if (id === 'player-52') {
            speedCircle.style.width = '55px';
            speedCircle.style.height = '55px';
        } else if (id === 'player-85') {
            speedCircle.style.width = '65px';
            speedCircle.style.height = '65px';
        }
        
        playerElement.prepend(speedCircle);
    });
});

/**
 * Adds a marker to the court diagram
 * @param {HTMLElement} diagram - The court diagram element
 * @param {string} id - ID for the marker
 * @param {number} x - X position as percentage
 * @param {number} y - Y position as percentage
 * @param {string} color - Marker color
 */
function addDiagramMarker(diagram, id, x, y, color) {
    const marker = document.createElement('div');
    marker.id = id;
    marker.style.position = 'absolute';
    marker.style.left = x + '%';
    marker.style.top = y + '%';
    marker.style.width = '5px';
    marker.style.height = '5px';
    marker.style.backgroundColor = color;
    marker.style.borderRadius = '50%';
    marker.style.transform = 'translate(-50%, -50%)';
    
    diagram.appendChild(marker);
}