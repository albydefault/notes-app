// app/static/js/sessions.js
class SessionManager {
    constructor() {
        console.log('SessionManager constructor starting');
        this.sessionImages = {};
        console.log('Setting up event listeners...');
        this.setupEventListeners();
        console.log('Loading sessions...');
        this.loadSessions();
        console.log('SessionManager constructor complete');
    }

    formatDate(dateString) {
        return new Date(dateString).toLocaleString();
    }

    getStatusClass(status) {
        const statusClasses = {
            'completed': 'status-completed',
            'processing': 'status-processing',
            'error': 'status-error',
            'pending': 'status-pending'
        };
        return statusClasses[status] || 'status-pending';
    }

    createFileLinks(files) {
        if (!files) return '';

        let html = '<div class="files-container">';
        
        // Handle scanned images
        if (files.scanned && files.scanned.length > 0) {
            const buttonId = 'view-images-' + Date.now();
            this.sessionImages[buttonId] = files.scanned;
            
            html += `
                <div class="file-section">
                    <h4>📸 Scanned Images</h4>
                    <button id="${buttonId}" 
                            onclick="event.stopPropagation(); imageViewer.viewImages(sessionManager.sessionImages['${buttonId}'])" 
                            class="view-images-btn">
                        View Images (${files.scanned.length})
                    </button>
                </div>
            `;
        }

        // Handle generated content
        if (files.generated && files.generated.length > 0) {
            html += this.createGeneratedContent(files.generated);
        }

        return html + '</div>';
    }

    createGeneratedContent(files) {
        return `
            <div class="file-section">
                <h4>📝 Generated Content</h4>
                ${files.map(file => this.createFileLink(file)).join('')}
            </div>
        `;
    }

    // In the createFileLink function in sessions.js
    createFileLink(file) {
        const icons = {
            'transcription': '📝',
            'exposition': '📚',
            'questions': '❓'
        };
        const labels = {
            'transcription': 'Transcription',
            'exposition': 'Detailed Explanation',
            'questions': 'Study Questions'
        };
    
        const linkHtml = `
            <a href="#" 
               data-markdown-file="${file.file}"
               data-markdown-title="${labels[file.file_type] || file.filename}"
               class="file-link markdown-link">
                ${icons[file.file_type] || '📄'} ${labels[file.file_type] || file.filename}
            </a>
        `;
        console.log('Created link HTML:', linkHtml);  // Add this line
        return linkHtml;
    }

    async loadSession(sessionId, element) {
        const fileList = element.querySelector(`#files-${sessionId}`);
        fileList.innerHTML = '<div class="loading">Loading...</div>';
        
        try {
            const response = await fetch(`/sessions/${sessionId}`);
            if (!response.ok) throw new Error('Failed to load session');
            
            const session = await response.json();
            this.updateSessionUI(session, element);

            if (session.status === 'processing') {
                setTimeout(() => this.loadSession(sessionId, element), 5000);
            }
        } catch (error) {
            this.showError(fileList, sessionId);
        }
    }

    updateSessionUI(session, element) {
        const titleEl = element.querySelector('.session-title');
        const summaryEl = element.querySelector('.session-summary');
        const statusEl = element.querySelector('.session-status');
        const fileList = element.querySelector(`#files-${session.id}`);
        
        titleEl.textContent = session.title || 'Untitled Notes';
        summaryEl.textContent = session.summary || 'No summary available';
        statusEl.className = `session-status ${this.getStatusClass(session.status)}`;
        statusEl.textContent = session.status;
        fileList.innerHTML = this.createFileLinks(session.files);
    }

    showError(element, sessionId) {
        element.innerHTML = `
            <div class="error">
                Failed to load session details. 
                <button onclick="sessionManager.loadSession('${sessionId}', this.closest('.session-card'))">
                    Retry
                </button>
            </div>
        `;
    }

    async loadSessions() {
        const sessionList = document.getElementById('sessionList');
        sessionList.innerHTML = '<div class="loading">Loading sessions...</div>';
        
        try {
            const response = await fetch('/sessions');
            if (!response.ok) throw new Error('Failed to load sessions');
            
            const data = await response.json();
            this.renderSessions(data.sessions);
        } catch (error) {
            this.showLoadError();
        }
    }

    renderSessions(sessions) {
        const sessionList = document.getElementById('sessionList');
        
        if (sessions.length === 0) {
            sessionList.innerHTML = this.getEmptyState();
            return;
        }

        sessionList.innerHTML = sessions.map(session => this.createSessionCard(session)).join('');
    }

    createSessionCard(session) {
        return `
            <div class="session-card" onclick="sessionManager.toggleSession(this, '${session.id}')">
                <div class="session-header">
                    <h3 class="session-title">${session.title || 'Untitled Notes'}</h3>
                    <span class="session-status ${this.getStatusClass(session.status)}">
                        ${session.status}
                    </span>
                </div>
                <div class="session-date">${this.formatDate(session.created_at)}</div>
                <div class="session-summary">${session.summary || 'No summary available'}</div>
                <div class="file-list" id="files-${session.id}"></div>
            </div>
        `;
    }

    getEmptyState() {
        return `
            <div class="empty-state">
                No sessions found. <a href="/">Create your first notes</a>
            </div>
        `;
    }

    showLoadError() {
        document.getElementById('sessionList').innerHTML = `
            <div class="error">
                Failed to load sessions. 
                <button onclick="sessionManager.loadSessions()">Retry</button>
            </div>
        `;
    }

    toggleSession(element, sessionId) {
        const wasExpanded = element.classList.contains('expanded');
        
        // Close all other sessions
        document.querySelectorAll('.session-card.expanded').forEach(card => {
            if (card !== element) card.classList.remove('expanded');
        });

        element.classList.toggle('expanded');
        
        if (!wasExpanded) {
            this.loadSession(sessionId, element);
        }
    }

    setupEventListeners() {
        document.addEventListener('click', (e) => {
            console.log('Click event:', e.target);  // Add this line
            const link = e.target.closest('.markdown-link');
            if (link) {
                console.log('Found markdown link:', link);  // Add this line
                e.preventDefault();
                const file = link.dataset.markdownFile;
                const title = link.dataset.markdownTitle;
                console.log('Markdown link clicked:', { file, title });
                
                if (window.markdownViewer) {
                    window.markdownViewer.viewMarkdown(file, title);
                } else {
                    console.error('MarkdownViewer not initialized');
                }
            }
        });
    }
}

// Initialize the session manager
const sessionManager = new SessionManager();