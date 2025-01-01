// app/static/js/markdownViewer.js
class MarkdownViewer {
    constructor() {
        this.initializeLibraries();
        this.setupKeyboardNavigation();
        this.currentUrl = null;
    }
    
    async initializeLibraries() {
        // Load marked.js from CDN
        await this.loadScript('https://cdnjs.cloudflare.com/ajax/libs/marked/9.1.6/marked.min.js');
        
        // Configure marked to preserve line breaks
        marked.setOptions({
            breaks: true,  // This enables single line breaks
            gfm: true     // GitHub Flavored Markdown
        });
        
        // Load KaTeX
        await this.loadScript('https://cdnjs.cloudflare.com/ajax/libs/KaTeX/0.16.9/katex.min.js');
        await this.loadStylesheet('https://cdnjs.cloudflare.com/ajax/libs/KaTeX/0.16.9/katex.min.css');
        await this.loadScript('https://cdnjs.cloudflare.com/ajax/libs/KaTeX/0.16.9/contrib/auto-render.min.js');
    }

    async initializeViewer() {
        console.log('Initializing viewer...');
        try {
            await this.initializeKaTeX();
            this.setupKeyboardNavigation();
            this.initialized = true;
            console.log('Viewer initialization complete');
        } catch (error) {
            console.error('Error initializing viewer:', error);
        }
    }

    async initializeKaTeX() {
        // Load KaTeX from CDN
        await this.loadScript('https://cdnjs.cloudflare.com/ajax/libs/KaTeX/0.16.9/katex.min.js');
        await this.loadStylesheet('https://cdnjs.cloudflare.com/ajax/libs/KaTeX/0.16.9/katex.min.css');
        await this.loadScript('https://cdnjs.cloudflare.com/ajax/libs/KaTeX/0.16.9/contrib/auto-render.min.js');
    }

    async loadScript(url) {
        return new Promise((resolve, reject) => {
            const script = document.createElement('script');
            script.src = url;
            script.onload = resolve;
            script.onerror = reject;
            document.head.appendChild(script);
        });
    }

    async loadStylesheet(url) {
        return new Promise((resolve, reject) => {
            const link = document.createElement('link');
            link.rel = 'stylesheet';
            link.href = url;
            link.onload = resolve;
            link.onerror = reject;
            document.head.appendChild(link);
        });
    }

    setupKeyboardNavigation() {
        document.addEventListener('keydown', (event) => {
            if (document.querySelector('.markdown-viewer-overlay').style.display === 'block') {
                if (event.key === 'Escape') this.closeViewer();
            }
        });
    }

    async viewMarkdown(url, title = 'Document') {
        console.log('ViewMarkdown called:', { url, title });
        if (!this.initialized) {
            console.log('Viewer not initialized, waiting...');
            await this.initializeViewer();
        }

        this.currentUrl = url;
        try {
            const response = await fetch(url);
            if (!response.ok) {
                throw new Error(`Failed to load markdown: ${response.statusText}`);
            }
            const content = await response.text();
            this.showViewer(content, title);
        } catch (error) {
            console.error('Error loading markdown:', error);
            this.showViewer(`Error loading document: ${error.message}`, 'Error');
        }
    }

    showViewer(content, title) {
        const viewer = document.querySelector('.markdown-viewer-overlay');
        const contentDiv = document.querySelector('.markdown-viewer-content');
        const titleDiv = document.querySelector('.markdown-viewer-title');
        
        titleDiv.textContent = title;
        
        // Use marked to parse the markdown
        contentDiv.innerHTML = marked.parse(content);
        
        viewer.style.display = 'block';
        document.body.classList.add('overlay-open');
        
        // Then render math
        if (window.renderMathInElement) {
            window.renderMathInElement(contentDiv, {
                delimiters: [
                    {left: "$$", right: "$$", display: true},
                    {left: "$", right: "$", display: false}
                ]
            });
        }
    }
    
    closeViewer() {
        document.querySelector('.markdown-viewer-overlay').style.display = 'none';
        document.body.classList.remove('overlay-open');  // Add this line
    }

    openFullPage() {
        if (this.currentUrl) {
            window.open(`/view${this.currentUrl}`, '_blank');
        }
    }

    renderMarkdown(content) {
        return marked.parse(content);
    }

    openInCurrentTab() {
        if (this.currentUrl) {
            window.location.href = `/view${this.currentUrl}`;
        }
    }

    openInNewTab() {
        if (this.currentUrl) {
            window.open(`/view${this.currentUrl}`, '_blank');
        }
    }

}

console.log('Setting up MarkdownViewer...');
window.markdownViewer = new MarkdownViewer();