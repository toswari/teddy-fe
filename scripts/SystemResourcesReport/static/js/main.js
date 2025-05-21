// This file contains JavaScript functionality for the System Resources Report

document.addEventListener('DOMContentLoaded', function() {
    console.log('System Resources Report loaded successfully');
    
    // Add animation to progress bars
    const progressBars = document.querySelectorAll('.progress-bar');
    progressBars.forEach(bar => {
        // Get the current width value
        const width = bar.style.width;
        // Reset width to 0
        bar.style.width = '0%';
        
        // Set a timeout to animate the progress bar
        setTimeout(() => {
            bar.style.transition = 'width 1s ease-in-out';
            bar.style.width = width;
        }, 200);
    });
    
    // Add click animation to download button
    const downloadBtn = document.querySelector('a[href="/download-report"]');
    if (downloadBtn) {
        downloadBtn.addEventListener('click', function(e) {
            // Add a visual indicator that download is in progress
            this.innerHTML = '<i class="fas fa-spinner fa-spin me-2"></i>Generating PDF...';
            
            // Reset button text after 2 seconds (PDF should be downloading by then)
            setTimeout(() => {
                this.innerHTML = '<i class="fas fa-download me-2"></i>Download Report';
            }, 2000);
        });
    }
    
    // Add card highlighting effect
    const cards = document.querySelectorAll('.card');
    cards.forEach(card => {
        card.addEventListener('mouseover', function() {
            this.classList.add('shadow');
        });
        
        card.addEventListener('mouseleave', function() {
            this.classList.remove('shadow');
        });
    });
});