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
    const downloadBtn = document.querySelector('#download-btn');
    if (downloadBtn) {
        downloadBtn.addEventListener('click', function(e) {
            // Add a visual indicator that download is in progress
            const originalText = this.innerHTML;
            this.innerHTML = '<i class="fas fa-spinner fa-spin me-2"></i>Generating PDF...';
            
            // Make fetch request to check if PDF generation worked
            fetch('/api/system-info')
                .then(response => {
                    if (response.ok) {
                        // If successful, the download will start automatically
                        setTimeout(() => {
                            this.innerHTML = originalText;
                        }, 2000);
                    } else {
                        // If there was an error, show an error message
                        this.innerHTML = '<i class="fas fa-exclamation-circle me-2"></i>PDF Generation Failed';
                        setTimeout(() => {
                            this.innerHTML = originalText;
                        }, 3000);
                        
                        throw new Error('Error checking API');
                    }
                })
                .catch(error => {
                    console.error('Error:', error);
                    this.innerHTML = originalText;
                });
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