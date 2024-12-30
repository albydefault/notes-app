// app/static/js/imageViewer.js
class ImageViewer {
    constructor() {
        this.currentImages = [];
        this.currentImageIndex = 0;
        this.setupKeyboardNavigation();
    }

    viewImages(images) {
        this.currentImages = images;
        this.currentImageIndex = 0;
        this.showImage();
        document.querySelector('.image-viewer-overlay').style.display = 'block';
    }

    closeViewer() {
        document.querySelector('.image-viewer-overlay').style.display = 'none';
    }

    showImage() {
        const img = document.getElementById('currentImage');
        const counter = document.getElementById('imageCounter');
        img.src = this.currentImages[this.currentImageIndex].file;
        counter.textContent = `${this.currentImageIndex + 1} of ${this.currentImages.length}`;
        this.updateNavigationButtons();
    }

    nextImage() {
        if (this.currentImageIndex < this.currentImages.length - 1) {
            this.currentImageIndex++;
            this.showImage();
        }
    }

    prevImage() {
        if (this.currentImageIndex > 0) {
            this.currentImageIndex--;
            this.showImage();
        }
    }

    updateNavigationButtons() {
        document.getElementById('prevButton').disabled = this.currentImageIndex === 0;
        document.getElementById('nextButton').disabled = 
            this.currentImageIndex === this.currentImages.length - 1;
    }

    setupKeyboardNavigation() {
        document.addEventListener('keydown', (event) => {
            if (document.querySelector('.image-viewer-overlay').style.display === 'block') {
                if (event.key === 'ArrowRight') this.nextImage();
                if (event.key === 'ArrowLeft') this.prevImage();
                if (event.key === 'Escape') this.closeViewer();
            }
        });
    }
}

// Initialize the viewer
const imageViewer = new ImageViewer();