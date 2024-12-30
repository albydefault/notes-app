// app/static/js/index.js
async function uploadFiles() {
    const fileInput = document.getElementById('fileInput');
    const status = document.getElementById('status');
    const results = document.getElementById('results');
    const uploadButton = document.getElementById('uploadButton');
    const spinner = document.getElementById('processingSpinner');
    
    if (fileInput.files.length === 0) {
        status.className = 'error';
        status.textContent = 'Please select at least one file.';
        return;
    }

    uploadButton.disabled = true;
    spinner.style.display = 'block';
    status.className = 'processing';
    status.textContent = 'Uploading and scanning images...';
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
        
        // Display scanned images
        results.innerHTML = uploadResult.processed_files.map(file => `
            <div class="processed-image">
                <img src="${file}" alt="Processed note">
            </div>
        `).join('');

        status.textContent = 'Processing with AI...';
        
        // Step 2: Process notes with AI
        const processResponse = await fetch(`/process-notes/${uploadResult.session_id}`, {
            method: 'POST'
        });
        
        if (!processResponse.ok) {
            throw new Error(`AI processing failed: ${processResponse.statusText}`);
        }
        
        const processResult = await processResponse.json();
        
        // Update status and display results
        status.className = 'success';
        status.textContent = 'Files processed successfully!';
        
        results.innerHTML += `
            <div>
                <h3>${processResult.title}</h3>
                <p><em>${processResult.summary}</em></p>
                <div class="generated-links">
                    ${processResult.files.map(file => `
                        <a href="${file.file}" target="_blank">
                            View ${file.type.charAt(0).toUpperCase() + file.type.slice(1)}
                        </a>
                    `).join('')}
                </div>
            </div>
        `;

    } catch (error) {
        status.className = 'error';
        status.textContent = 'Error: ' + error.message;
    } finally {
        uploadButton.disabled = false;
        spinner.style.display = 'none';
    }
}