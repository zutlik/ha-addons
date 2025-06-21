// API configuration
const API_BASE_URL = window.location.origin; // Use the same origin as the add-on

// State management
let scriptsData = [];
let filteredScripts = [];

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

// API functions
async function fetchScripts() {
    try {
        const response = await fetch(`${API_BASE_URL}/scripts/`);
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        const data = await response.json();
        console.log('Fetched scripts from API:', data);
        return data.scripts || [];
    } catch (error) {
        console.error('Error fetching scripts:', error);
        showError('Failed to load scripts from Home Assistant');
        return [];
    }
}

async function createTunnel(scriptId) {
    try {
        const response = await fetch(`${API_BASE_URL}/tunnels/create`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ script_id: scriptId })
        });
        
        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.detail || `HTTP error! status: ${response.status}`);
        }
        
        const data = await response.json();
        return data;
    } catch (error) {
        console.error('Error creating tunnel:', error);
        throw error;
    }
}

async function deleteTunnel(scriptId) {
    try {
        const response = await fetch(`${API_BASE_URL}/tunnels/${scriptId}`, {
            method: 'DELETE'
        });
        
        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.detail || `HTTP error! status: ${response.status}`);
        }
        
        const data = await response.json();
        return data;
    } catch (error) {
        console.error('Error deleting tunnel:', error);
        throw error;
    }
}

async function fetchTunnels() {
    try {
        const response = await fetch(`${API_BASE_URL}/tunnels/`);
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        const data = await response.json();
        console.log('Fetched tunnels from API:', data);
        return data.tunnels || [];
    } catch (error) {
        console.error('Error fetching tunnels:', error);
        return [];
    }
}

// Search functionality
function filterScripts(searchTerm) {
    const term = searchTerm.toLowerCase().trim();
    
    if (term === '') {
        filteredScripts = [...scriptsData];
    } else {
        filteredScripts = scriptsData.filter(script => {
            const scriptName = script.name || script.entity_id;
            return scriptName.toLowerCase().includes(term) || 
                   script.entity_id.toLowerCase().includes(term);
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

// Show error message
function showError(message) {
    // Create a simple error notification
    const errorDiv = document.createElement('div');
    errorDiv.className = 'error-notification';
    errorDiv.textContent = message;
    errorDiv.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        background: #ef4444;
        color: white;
        padding: 12px 16px;
        border-radius: 8px;
        z-index: 1000;
        box-shadow: 0 4px 12px rgba(0,0,0,0.15);
    `;
    
    document.body.appendChild(errorDiv);
    
    setTimeout(() => {
        errorDiv.remove();
    }, 5000);
}

// Show success message
function showSuccess(message) {
    const successDiv = document.createElement('div');
    successDiv.className = 'success-notification';
    successDiv.textContent = message;
    successDiv.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        background: #10b981;
        color: white;
        padding: 12px 16px;
        border-radius: 8px;
        z-index: 1000;
        box-shadow: 0 4px 12px rgba(0,0,0,0.15);
    `;
    
    document.body.appendChild(successDiv);
    
    setTimeout(() => {
        successDiv.remove();
    }, 3000);
}

// Create URL section HTML
function createUrlSection(script, tunnelInfo) {
    if (!tunnelInfo) return '';
    
    return `
        <div class="url-section">
            <div class="url-label-container">
                <div class="url-label">Public URL:</div>
                <button class="btn btn-copy" onclick="copyToClipboard('${tunnelInfo.complete_url}', this)" title="Copy URL">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                        <rect width="14" height="14" x="8" y="8" rx="2" ry="2"/>
                        <path d="m4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2"/>
                    </svg>
                </button>
            </div>
            <div class="url-text">${tunnelInfo.complete_url}</div>
        </div>
    `;
}

// Create script card HTML
function createScriptCard(script, tunnelInfo) {
    const hasTunnel = tunnelInfo !== null;
    const scriptName = script.name || script.entity_id;
    const scriptState = script.state || 'unknown';
    
    // Always show title container with action buttons on the right
    const titleSection = `
        <div class="script-title-container">
            <h3 class="script-name">${scriptName}</h3>
            <div style="display: flex; gap: 0.75rem;">
                ${hasTunnel ? `<button class="btn btn-secondary" onclick="revokeUrl('${script.entity_id}', this)">Revoke</button>` : ''}
                ${!hasTunnel ? `<button class="btn btn-primary" onclick="shareScript('${script.entity_id}', this)">Share</button>` : ''}
            </div>
        </div>
    `;
    
    return `
        <div class="script-card" data-script-id="${script.entity_id}">
            ${titleSection}
            <div class="script-id">${script.entity_id}</div>
            <div class="script-state">State: ${scriptState}</div>
            ${createUrlSection(script, tunnelInfo)}
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
        const result = await createTunnel(scriptId);
        
        // Find and update the script
        const scriptIndex = scriptsData.findIndex(s => s.entity_id === scriptId);
        if (scriptIndex !== -1) {
            // Update the script with tunnel info
            scriptsData[scriptIndex].tunnelInfo = {
                tunnel_url: result.tunnel_url,
                complete_url: result.complete_url
            };
            
            console.log('Created tunnel for', scriptId, ':', result.complete_url);
            
            // Update filtered scripts as well
            const filteredIndex = filteredScripts.findIndex(s => s.entity_id === scriptId);
            if (filteredIndex !== -1) {
                filteredScripts[filteredIndex].tunnelInfo = {
                    tunnel_url: result.tunnel_url,
                    complete_url: result.complete_url
                };
            }
            
            // Re-render the specific card
            renderScriptCard(scriptsData[scriptIndex]);
            showSuccess('Tunnel created successfully!');
        }
    } catch (error) {
        console.error('Error sharing script:', error);
        showError(`Failed to create tunnel: ${error.message}`);
    } finally {
        // Remove loading state
        button.classList.remove('loading');
        button.disabled = false;
    }
}

// Revoke URL functionality
async function revokeUrl(scriptId, button) {
    console.log('Revoking tunnel for script:', scriptId);
    
    // Add loading state
    button.classList.add('loading');
    button.disabled = true;
    
    try {
        await deleteTunnel(scriptId);
        
        // Find and update the script
        const scriptIndex = scriptsData.findIndex(s => s.entity_id === scriptId);
        if (scriptIndex !== -1) {
            scriptsData[scriptIndex].tunnelInfo = null;
            
            console.log('Revoked tunnel for', scriptId);
            
            // Update filtered scripts as well
            const filteredIndex = filteredScripts.findIndex(s => s.entity_id === scriptId);
            if (filteredIndex !== -1) {
                filteredScripts[filteredIndex].tunnelInfo = null;
            }
            
            // Re-render the specific card
            renderScriptCard(scriptsData[scriptIndex]);
            showSuccess('Tunnel revoked successfully!');
        }
    } catch (error) {
        console.error('Error revoking tunnel:', error);
        showError(`Failed to revoke tunnel: ${error.message}`);
    } finally {
        // Remove loading state
        button.classList.remove('loading');
        button.disabled = false;
    }
}

// Render individual script card
function renderScriptCard(script) {
    const cardElement = $(`[data-script-id="${script.entity_id}"]`);
    if (cardElement) {
        cardElement.outerHTML = createScriptCard(script, script.tunnelInfo);
    }
}

// Render all scripts
function renderScripts() {
    const container = $('#scripts-container');
    if (!container) return;
    
    if (filteredScripts.length === 0) {
        container.innerHTML = `
            <div class="no-scripts">
                <p>No scripts found matching your search.</p>
            </div>
        `;
        return;
    }
    
    container.innerHTML = filteredScripts.map(script => 
        createScriptCard(script, script.tunnelInfo)
    ).join('');
}

// Initialize the application
async function init() {
    console.log('Initializing Script Manager...');
    
    try {
        // Load scripts from Home Assistant
        const scripts = await fetchScripts();
        console.log('Raw scripts from API:', scripts);
        
        // Transform scripts to include tunnel info
        scriptsData = scripts.map(script => ({
            ...script,
            tunnelInfo: null // Will be populated with tunnel data
        }));
        
        // Load existing tunnels
        const tunnels = await fetchTunnels();
        console.log('Raw tunnels from API:', tunnels);
        
        // Match tunnels with scripts
        scriptsData.forEach(script => {
            const tunnel = tunnels.find(t => t.script_id === script.entity_id);
            script.tunnelInfo = tunnel ? {
                tunnel_url: tunnel.tunnel_url,
                complete_url: tunnel.complete_url
            } : null;
        });
        
        // Update filtered scripts
        filteredScripts = scriptsData.map(script => ({ ...script }));
        
        // Render the UI
        renderScripts();
        setupSearch();
        
        console.log('Script Manager initialized successfully');
        console.log('Loaded', scriptsData.length, 'scripts');
        console.log('Active tunnels:', tunnels.length);
        console.log('Final scripts data:', scriptsData);
        
    } catch (error) {
        console.error('Failed to initialize:', error);
        showError('Failed to initialize the application');
    }
}

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', init);
