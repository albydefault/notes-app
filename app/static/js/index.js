// app/static/js/index.js
class FileUploader {
    constructor() {
        this.uploadInProgress = false;
        this.setupPreviewListeners();
    }

    setupPreviewListeners() {
        const fileInput = document.getElementById('fileInput');
        fileInput.addEventListener('change', () => {
            this.showPreview(fileInput.files);
        });
    }

    showPreview(files) {
        const preview = document.getElementById('preview');
        preview.innerHTML = ''; // Clear existing previews

        Array.from(files).forEach(file => {
            // Create preview container
            const previewItem = document.createElement('div');
            previewItem.className = 'preview-item';

            // Create loading indicator
            previewItem.innerHTML = `
                <div class="preview-loading">
                    <div class="preview-spinner"></div>
                </div>
                <p class="preview-filename">${file.name}</p>
            `;
            preview.appendChild(previewItem);

            // Read and display the image
            const reader = new FileReader();
            reader.onload = (e) => {
                previewItem.innerHTML = `
                    <div class="preview-image-container">
                        <img src="${e.target.result}" alt="Preview" class="preview-image">
                    </div>
                    <p class="preview-filename">${file.name}</p>
                    <p class="preview-size">${this.formatFileSize(file.size)}</p>
                `;
            };
            reader.readAsDataURL(file);
        });
    }

    formatFileSize(bytes) {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
    }

    showStatus(type, message) {
        const status = document.getElementById('status');
        status.className = type;
        status.textContent = message;
        status.style.display = 'block';
    }

    async uploadFiles() {
        if (this.uploadInProgress) {
            return;
        }

        const fileInput = document.getElementById('fileInput');
        const uploadButton = document.getElementById('uploadButton');
        const spinner = document.getElementById('processingSpinner');
        const results = document.getElementById('results');
        
        if (fileInput.files.length === 0) {
            this.showStatus('error', 'Please select at least one file.');
            return;
        }

        this.uploadInProgress = true;
        uploadButton.disabled = true;
        spinner.style.display = 'block';
        this.showStatus('processing', 'Uploading and scanning images...');
        results.innerHTML = '';

        const formData = new FormData();
        for (const file of fileInput.files) {
            formData.append('files', file);
        }

        try {
            // Step 1: Upload and scan files
            const uploadResponse = await fetch('/upload', {
                method: 'POST',
                body: formData
            });

            if (!uploadResponse.ok) {
                throw new Error(`Upload failed: ${uploadResponse.statusText}`);
            }

            const uploadResult = await uploadResponse.json();

            this.displayProcessedImages(uploadResult.processed_files);
            this.showStatus('processing', 'Processing with AI...');

            // Step 2: Process notes with AI
            const processResponse = await fetch(`/process-notes/${uploadResult.session_id}`, {
                method: 'POST'
            });

            if (!processResponse.ok) {
                throw new Error(`AI processing failed: ${processResponse.statusText}`);
            }

            const processResult = await processResponse.json();
            this.displayResults(processResult);
            this.showStatus('success', 'Files processed successfully!');

        } catch (error) {
            console.error('Error during upload/processing:', error);
            this.showStatus('error', error.message);
        } finally {
            this.uploadInProgress = false;
            uploadButton.disabled = false;
            spinner.style.display = 'none';
        }
    }

    displayProcessedImages(files) {
        const results = document.getElementById('results');
        if (!files || !files.length) return;
        
        results.innerHTML = files.map(file => `
            <div class="processed-image">
                <img src="${file}" alt="Processed note">
            </div>
        `).join('');
    }

    displayResults(result) {
        const results = document.getElementById('results');
        results.innerHTML += `
            <div class="results-container">
                <h3>${result.title}</h3>
                <p class="summary">${result.summary}</p>
                <div class="generated-links">
                    ${result.files.map(file => `
                        <a href="/view${file.file}" target="_blank" class="result-link">
                            <span class="link-icon">📄</span>
                            <span class="link-text">View ${file.type.charAt(0).toUpperCase() + file.type.slice(1)}</span>
                        </a>
                    `).join('')}
                </div>
            </div>
        `;
    }
}

// Initialize the uploader
const uploader = new FileUploader();

// Expose the upload function globally
window.uploadFiles = () => uploader.uploadFiles();