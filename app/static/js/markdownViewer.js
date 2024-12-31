// app/static/js/markdownViewer.js
class MarkdownViewer {
    constructor() {
        this.setupKeyboardNavigation();
    }

    viewContent(url) {
        const overlay = document.querySelector('.markdown-viewer-overlay');
        overlay.style.display = 'flex'; // Use 'flex' for centering
        document.body.classList.add('no-scroll'); // Prevent background scrolling
        this.fetchAndDisplayContent(url);
    }

    async fetchAndDisplayContent(url) {
        try {
            const response = await fetch(url);
            if (!response.ok) throw new Error('Failed to load content');
            const text = await response.text();
            document.getElementById('markdownContent').innerHTML = this.formatMarkdown(text);
        } catch (error) {
            console.error('Error loading markdown:', error);
        }
    }

    closeViewer() {
        const overlay = document.querySelector('.markdown-viewer-overlay');
        overlay.style.display = 'none';
        document.body.classList.remove('no-scroll'); // Restore scrolling
    }

    formatMarkdown(text) {
        // First pass: Handle LaTeX
        text = text.replace(/\$\$(.*?)\$\$/g, (match, formula) => {
            try {
                return katex.renderToString(formula, { displayMode: true });
            } catch (e) {
                console.error('KaTeX error:', e);
                return match;
            }
        });
        
        text = text.replace(/\$(.*?)\$/g, (match, formula) => {
            try {
                return katex.renderToString(formula, { displayMode: false });
            } catch (e) {
                console.error('KaTeX error:', e);
                return match;
            }
        });
    
        // Second pass: Handle markdown
        return text.split('\n').map(line => {
            if (line.startsWith('# ')) {
                return `<h1>${line.slice(2)}</h1>`;
            }
            if (line.startsWith('## ')) {
                return `<h2>${line.slice(3)}</h2>`;
            }
            if (line.startsWith('### ')) {
                return `<h3>${line.slice(4)}</h3>`;
            }
            if (line.startsWith('*') && line.endsWith('*')) {
                return `<em>${line.slice(1, -1)}</em>`;
            }
            if (line.trim() === '---') {
                return '<hr>';
            }
            if (line.trim() === '') {
                return '<br>';
            }
            return `<p>${line}</p>`;
        }).join('');
    }

    setupKeyboardNavigation() {
        document.addEventListener('keydown', (event) => {
            if (document.querySelector('.markdown-viewer-overlay').style.display === 'block') {
                if (event.key === 'Escape') this.closeViewer();
            }
        });
    }
}

// Initialize the viewer
const markdownViewer = new MarkdownViewer();