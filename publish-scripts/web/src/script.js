
// Mock data for Home Assistant scripts
const scripts = [
    {
        id: 'script.notify_family_dinner_is_ready',
        name: 'Notify: Dinner is Ready',
        public_url: null
    },
    {
        id: 'script.good_morning_routine',
        name: 'Good Morning Routine',
        public_url: 'https://public-hook.io/abc987xyz'
    },
    {
        id: 'script.movie_time_scene',
        name: 'Set Movie Time Scene',
        public_url: null
    },
    {
        id: 'script.goodnight_all_off',
        name: 'Goodnight - Turn Everything Off',
        public_url: null
    }
];

// State management
let scriptsData = [...scripts];
let filteredScripts = [...scripts];

// DOM utility functions
function $(selector) {
    return document.querySelector(selector);
}

function createElement(tag, className = '', textContent = '') {
    const element = document.createElement(tag);
    if (className) element.className = className;
    if (textContent) element.textContent = textContent;
    return element;
}

// Search functionality
function filterScripts(searchTerm) {
    const term = searchTerm.toLowerCase().trim();
    
    if (term === '') {
        filteredScripts = [...scriptsData];
    } else {
        filteredScripts = scriptsData.filter(script => {
            return script.name.toLowerCase().includes(term) || 
                   script.id.toLowerCase().includes(term);
        });
    }
    
    renderScripts();
    console.log('Filtered scripts:', filteredScripts.length, 'of', scriptsData.length);
}

// Setup search input listener
function setupSearch() {
    const searchInput = $('#search-input');
    if (searchInput) {
        searchInput.addEventListener('input', (event) => {
            filterScripts(event.target.value);
        });
    }
}

// Generate a random public URL for simulation
function generatePublicUrl() {
    const randomId = Math.random().toString(36).substring(2, 15);
    return `https://public-hook.io/${randomId}`;
}

// Copy text to clipboard with visual feedback
async function copyToClipboard(text, button) {
    try {
        await navigator.clipboard.writeText(text);
        
        const originalHtml = button.innerHTML;
        button.innerHTML = '✓';
        button.classList.add('copied');
        
        setTimeout(() => {
            button.innerHTML = originalHtml;
            button.classList.remove('copied');
        }, 2000);
        
        console.log('URL copied to clipboard:', text);
    } catch (error) {
        console.error('Failed to copy to clipboard:', error);
        
        // Fallback for older browsers
        const textArea = document.createElement('textarea');
        textArea.value = text;
        document.body.appendChild(textArea);
        textArea.select();
        document.execCommand('copy');
        document.body.removeChild(textArea);
        
        const originalHtml = button.innerHTML;
        button.innerHTML = '✓';
        button.classList.add('copied');
        
        setTimeout(() => {
            button.innerHTML = originalHtml;
            button.classList.remove('copied');
        }, 2000);
    }
}

// Simulate API call with loading state
function simulateApiCall(duration = 1000) {
    return new Promise(resolve => {
        setTimeout(resolve, duration);
    });
}

// Create URL section HTML
function createUrlSection(script) {
    if (!script.public_url) return '';
    
    return `
        <div class="url-section">
            <div class="url-label-container">
                <div class="url-label">Public URL:</div>
                <button class="btn btn-copy" onclick="copyToClipboard('${script.public_url}', this)" title="Copy URL">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                        <rect width="14" height="14" x="8" y="8" rx="2" ry="2"/>
                        <path d="m4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2"/>
                    </svg>
                </button>
            </div>
            <div class="url-text">${script.public_url}</div>
        </div>
    `;
}

// Create script card HTML
function createScriptCard(script) {
    const hasUrl = script.public_url !== null;
    
    // Always show title container with action buttons on the right
    const titleSection = `
        <div class="script-title-container">
            <h3 class="script-name">${script.name}</h3>
            <div style="display: flex; gap: 0.75rem;">
                ${hasUrl ? `<button class="btn btn-secondary" onclick="revokeUrl('${script.id}', this)">Revoke</button>` : ''}
                ${!hasUrl ? `<button class="btn btn-primary" onclick="shareScript('${script.id}', this)">Share</button>` : ''}
            </div>
        </div>
    `;
    
    return `
        <div class="script-card" data-script-id="${script.id}">
            ${titleSection}
            <div class="script-id">${script.id}</div>
            ${createUrlSection(script)}
        </div>
    `;
}

// Share script functionality
async function shareScript(scriptId, button) {
    console.log('Sharing script:', scriptId);
    
    // Add loading state
    button.classList.add('loading');
    button.disabled = true;
    
    try {
        // Simulate API call
        await simulateApiCall(800);
        
        // Find and update the script
        const scriptIndex = scriptsData.findIndex(s => s.id === scriptId);
        if (scriptIndex !== -1) {
            const newUrl = generatePublicUrl();
            scriptsData[scriptIndex].public_url = newUrl;
            
            console.log('Generated URL for', scriptId, ':', newUrl);
            
            // Update filtered scripts as well
            const filteredIndex = filteredScripts.findIndex(s => s.id === scriptId);
            if (filteredIndex !== -1) {
                filteredScripts[filteredIndex].public_url = newUrl;
            }
            
            // Re-render the specific card
            renderScriptCard(scriptsData[scriptIndex]);
        }
    } catch (error) {
        console.error('Error sharing script:', error);
    } finally {
        // Remove loading state
        button.classList.remove('loading');
        button.disabled = false;
    }
}

// Revoke URL functionality
async function revokeUrl(scriptId, button) {
    console.log('Revoking URL for script:', scriptId);
    
    // Add loading state
    button.classList.add('loading');
    button.disabled = true;
    
    try {
        // Simulate API call
        await simulateApiCall(600);
        
        // Find and update the script
        const scriptIndex = scriptsData.findIndex(s => s.id === scriptId);
        if (scriptIndex !== -1) {
            scriptsData[scriptIndex].public_url = null;
            
            console.log('Revoked URL for', scriptId);
            
            // Update filtered scripts as well
            const filteredIndex = filteredScripts.findIndex(s => s.id === scriptId);
            if (filteredIndex !== -1) {
                filteredScripts[filteredIndex].public_url = null;
            }
            
            // Re-render the specific card
            renderScriptCard(scriptsData[scriptIndex]);
        }
    } catch (error) {
        console.error('Error revoking URL:', error);
    } finally {
        // Remove loading state
        button.classList.remove('loading');
        button.disabled = false;
    }
}

// Render a single script card
function renderScriptCard(script) {
    const container = $('#scripts-container');
    const existingCard = container.querySelector(`[data-script-id="${script.id}"]`);
    
    const cardElement = createElement('div');
    cardElement.innerHTML = createScriptCard(script);
    const newCard = cardElement.firstElementChild;
    
    if (existingCard) {
        container.replaceChild(newCard, existingCard);
    } else {
        container.appendChild(newCard);
    }
}

// Render all script cards
function renderScripts() {
    const container = $('#scripts-container');
    container.innerHTML = '';
    
    filteredScripts.forEach(script => {
        renderScriptCard(script);
    });
    
    console.log('Rendered', filteredScripts.length, 'script cards');
}

// Initialize the application
function init() {
    console.log('Initializing Home Assistant Script Manager');
    console.log('Loaded scripts:', scriptsData);
    
    // Setup search functionality
    setupSearch();
    
    // Render initial scripts
    renderScripts();
    
    // Add global error handling
    window.addEventListener('error', (event) => {
        console.error('Global error:', event.error);
    });
    
    console.log('Application initialized successfully');
}

// Make functions available globally for onclick handlers
window.shareScript = shareScript;
window.revokeUrl = revokeUrl;
window.copyToClipboard = copyToClipboard;

// Initialize when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
} else {
    init();
}
