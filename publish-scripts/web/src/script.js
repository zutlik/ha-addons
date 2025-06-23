// API configuration - No longer needed, using relative paths

// State management
let scriptsData = [];
let filteredScripts = [];
let activeTunnelScriptId = null; // Track which script has the active tunnel

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
        const response = await fetch(`scripts/`);
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
        const timeoutInput = $('#timeout-input');
        const timeout_minutes = timeoutInput ? parseInt(timeoutInput.value, 10) : 15;

        const response = await fetch(`tunnels/create`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ 
                script_id: scriptId,
                timeout_minutes: timeout_minutes
            })
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
        const response = await fetch(`tunnels/${scriptId}`, {
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
        const response = await fetch(`tunnels/`);
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
    }, 5000);
}

// Pinning logic
function getPinnedScripts() {
    try {
        const pinned = localStorage.getItem('pinnedScripts');
        console.log('Retrieved from localStorage:', pinned);
        return JSON.parse(pinned || '[]');
    } catch(e) {
        console.error('Error parsing pinned scripts from localStorage', e);
        return [];
    }
}

function setPinnedScripts(pinned) {
    console.log('Saving to localStorage:', JSON.stringify(pinned));
    localStorage.setItem('pinnedScripts', JSON.stringify(pinned));
}

function isScriptPinned(scriptId) {
    return getPinnedScripts().includes(scriptId);
}

function pinScript(scriptId) {
    console.log('Attempting to pin script:', scriptId);
    const pinned = getPinnedScripts();
    if (!pinned.includes(scriptId)) {
        pinned.push(scriptId);
        setPinnedScripts(pinned);
        console.log('Pinning successful, re-rendering all scripts.');
        renderScripts();
    } else {
        console.log('Script already pinned.');
    }
}

function unpinScript(scriptId) {
    console.log('Attempting to unpin script:', scriptId);
    let pinned = getPinnedScripts();
    if (pinned.includes(scriptId)) {
        pinned = pinned.filter(id => id !== scriptId);
        setPinnedScripts(pinned);
        console.log('Unpinning successful, re-rendering all scripts.');
        renderScripts();
    } else {
        console.log('Script not found in pinned list.');
    }
}

// Create URL section HTML
function createUrlSection(script, tunnelInfo) {
    if (!tunnelInfo) {
        return `
            <div class="url-section" style="border-color: #64748b; background: #1e293b80;">
                <div class="url-label-container">
                    <div class="url-label" style="color: #64748b;">No public URL</div>
                </div>
                <div class="url-text" style="color: #64748b;">Click "Share" to create a public URL for this script</div>
            </div>
        `;
    }
    
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

// Single tunnel enforcement
function setActiveTunnel(scriptId) {
    activeTunnelScriptId = scriptId;
    updateShareButtons();
}

function clearActiveTunnel() {
    activeTunnelScriptId = null;
    updateShareButtons();
}

function updateShareButtons() {
    // Update all share buttons based on active tunnel state
    const shareButtons = document.querySelectorAll('.btn-primary');
    shareButtons.forEach(button => {
        const scriptId = button.getAttribute('data-script-id');
        if (activeTunnelScriptId && scriptId !== activeTunnelScriptId) {
            button.disabled = true;
            button.textContent = 'Share (Tunnel Active)';
            button.title = 'Another tunnel is currently active. Revoke it first.';
        } else {
            button.disabled = false;
            button.textContent = 'Share';
            button.title = 'Create a public URL for this script';
        }
    });
}

// Create script card HTML
function createScriptCard(script, tunnelInfo) {
    const hasTunnel = tunnelInfo !== null;
    const scriptName = script.name || script.entity_id;
    const scriptState = script.state || 'unknown';
    const isPinned = isScriptPinned(script.entity_id);
    const isLoading = script.isLoading || false;

    let actionButtonHTML;
    if (isLoading) {
        actionButtonHTML = `<button class="btn btn-primary loading" disabled>Loading...</button>`;
    } else if (hasTunnel) {
        actionButtonHTML = `<button class="btn btn-secondary" onclick="revokeUrl('${script.entity_id}')">Revoke</button>`;
    } else {
        const isDisabled = activeTunnelScriptId && activeTunnelScriptId !== script.entity_id;
        const buttonText = isDisabled ? 'Share (Tunnel Active)' : 'Share';
        actionButtonHTML = `<button class="btn btn-primary" data-script-id="${script.entity_id}" onclick="shareScript('${script.entity_id}')" ${isDisabled ? 'disabled' : ''}>${buttonText}</button>`;
    }

    const card = createElement('div', 'script-card');
    card.setAttribute('data-script-id', script.entity_id);
    if (hasTunnel) card.classList.add('has-active-tunnel');
    if (isPinned) card.classList.add('pinned');
    
    card.innerHTML = `
        <div class="script-title-container">
            <div style="display: flex; align-items: center; gap: 0.5rem; flex: 1;">
                <button class="btn btn-pin" title="${isPinned ? 'Unpin this script' : 'Pin this script'}" aria-label="${isPinned ? 'Unpin' : 'Pin'}">${isPinned ? '📌' : '📍'}</button>
                <h3 class="script-name">${scriptName}</h3>
            </div>
            <div class="card-actions-container" style="display: flex; gap: 0.75rem;">
                ${actionButtonHTML}
            </div>
        </div>
        <div class="script-id">${script.entity_id}</div>
        <div class="script-state">State: ${scriptState}</div>
        ${createUrlSection(script, tunnelInfo)}
    `;

    // Attach event listener directly - this is more reliable
    const pinButton = card.querySelector('.btn-pin');
    if (pinButton) {
        pinButton.addEventListener('click', (e) => {
            e.stopPropagation();
            if (isScriptPinned(script.entity_id)) {
                unpinScript(script.entity_id);
            } else {
                pinScript(script.entity_id);
            }
        });
    }
    
    return card;
}

// Show retry indicator
function showRetryIndicator(message) {
    // Remove any existing retry indicator
    const existingIndicator = document.querySelector('.retry-indicator');
    if (existingIndicator) {
        existingIndicator.remove();
    }
    
    const indicator = document.createElement('div');
    indicator.className = 'retry-indicator';
    indicator.textContent = message;
    document.body.appendChild(indicator);
    
    // Auto-remove after 3 seconds
    setTimeout(() => {
        if (indicator.parentNode) {
            indicator.remove();
        }
    }, 3000);
}

// Retry mechanism for tunnel creation
async function createTunnelWithRetry(scriptId, maxRetries = 3, delayMs = 1000) {
    let lastError;
    
    for (let attempt = 1; attempt <= maxRetries; attempt++) {
        try {
            console.log(`Attempt ${attempt}/${maxRetries} to create tunnel for ${scriptId}`);
            
            if (attempt > 1) {
                // Show retry notification
                showRetryIndicator(`Retrying tunnel creation... (${attempt}/${maxRetries})`);
                // Wait before retry
                await new Promise(resolve => setTimeout(resolve, delayMs));
            }
            
            const result = await createTunnel(scriptId);
            console.log(`Tunnel created successfully on attempt ${attempt}`);
            return result;
            
        } catch (error) {
            lastError = error;
            console.error(`Attempt ${attempt} failed:`, error.message);
            
            if (attempt === maxRetries) {
                throw new Error(`Failed to create tunnel after ${maxRetries} attempts. Last error: ${error.message}`);
            }
        }
    }
}

// Share script functionality
async function shareScript(scriptId) {
    // Enforce only one tunnel at a time
    if (activeTunnelScriptId && activeTunnelScriptId !== scriptId) {
        showError('Only one tunnel can be active at a time. Please revoke the existing tunnel before creating a new one.');
        return;
    }
    const scriptIndex = scriptsData.findIndex(s => s.entity_id === scriptId);
    if (scriptIndex === -1) return;

    // Set loading state and re-render
    scriptsData[scriptIndex].isLoading = true;
    renderScriptCard(scriptsData[scriptIndex]);

    try {
        const result = await createTunnelWithRetry(scriptId);
        scriptsData[scriptIndex].tunnelInfo = {
            tunnel_url: result.tunnel_url,
            complete_url: result.complete_url
        };
        const filteredIndex = filteredScripts.findIndex(s => s.entity_id === scriptId);
        if (filteredIndex !== -1) {
            filteredScripts[filteredIndex].tunnelInfo = { ...scriptsData[scriptIndex].tunnelInfo };
        }
        setActiveTunnel(scriptId);
        showSuccess('Tunnel created successfully!');
    } catch (error) {
        console.error('Error sharing script:', error);
        showError(`Failed to create tunnel: ${error.message}`);
    } finally {
        scriptsData[scriptIndex].isLoading = false;
        renderScriptCard(scriptsData[scriptIndex]);
    }
}

// Update card content without full re-render
function updateCardContent(script) {
    const cardElement = $(`[data-script-id="${script.entity_id}"]`);
    if (!cardElement) return;
    
    // Update the URL section
    const urlSection = cardElement.querySelector('.url-section');
    if (urlSection) {
        const newUrlSection = createUrlSection(script, script.tunnelInfo);
        const tempDiv = document.createElement('div');
        tempDiv.innerHTML = newUrlSection;
        urlSection.replaceWith(tempDiv.firstElementChild);
    }
    
    // Update the action buttons
    const titleContainer = cardElement.querySelector('.script-title-container');
    if (titleContainer) {
        const actionButtons = titleContainer.querySelector('div');
        if (actionButtons) {
            if (script.tunnelInfo) {
                actionButtons.innerHTML = `<button class="btn btn-secondary" onclick="revokeUrl('${script.entity_id}')">Revoke</button>`;
            } else {
                actionButtons.innerHTML = `<button class="btn btn-primary" data-script-id="${script.entity_id}" onclick="shareScript('${script.entity_id}')" ${activeTunnelScriptId && activeTunnelScriptId !== script.entity_id ? 'disabled' : ''}>${activeTunnelScriptId && activeTunnelScriptId !== script.entity_id ? 'Share (Tunnel Active)' : 'Share'}</button>`;
            }
        }
    }
    
    // Update active tunnel visual indicator
    if (script.tunnelInfo) {
        cardElement.classList.add('has-active-tunnel');
    } else {
        cardElement.classList.remove('has-active-tunnel');
    }
}

// Retry mechanism for tunnel deletion
async function deleteTunnelWithRetry(scriptId, maxRetries = 3, delayMs = 1000) {
    let lastError;
    
    for (let attempt = 1; attempt <= maxRetries; attempt++) {
        try {
            console.log(`Attempt ${attempt}/${maxRetries} to delete tunnel for ${scriptId}`);
            
            if (attempt > 1) {
                // Show retry notification
                showRetryIndicator(`Retrying tunnel deletion... (${attempt}/${maxRetries})`);
                // Wait before retry
                await new Promise(resolve => setTimeout(resolve, delayMs));
            }
            
            const result = await deleteTunnel(scriptId);
            console.log(`Tunnel deleted successfully on attempt ${attempt}`);
            return result;
            
        } catch (error) {
            lastError = error;
            console.error(`Attempt ${attempt} failed:`, error.message);
            
            if (attempt === maxRetries) {
                throw new Error(`Failed to delete tunnel after ${maxRetries} attempts. Last error: ${error.message}`);
            }
        }
    }
}

// Revoke URL functionality
async function revokeUrl(scriptId) {
    const scriptIndex = scriptsData.findIndex(s => s.entity_id === scriptId);
    if (scriptIndex === -1) return;

    // Set loading state and re-render
    scriptsData[scriptIndex].isLoading = true;
    renderScriptCard(scriptsData[scriptIndex]);

    try {
        await deleteTunnelWithRetry(scriptId);
        
        scriptsData[scriptIndex].tunnelInfo = null;
        
        const filteredIndex = filteredScripts.findIndex(s => s.entity_id === scriptId);
        if (filteredIndex !== -1) {
            filteredScripts[filteredIndex].tunnelInfo = null;
        }
        
        clearActiveTunnel();
        showSuccess('Tunnel revoked successfully!');
    } catch (error) {
        console.error('Error revoking tunnel:', error);
        showError(`Failed to revoke tunnel: ${error.message}`);
    } finally {
       scriptsData[scriptIndex].isLoading = false;
       renderScriptCard(scriptsData[scriptIndex]);
    }
}

// Render individual script card
function renderScriptCard(script) {
    const cardElement = $(`[data-script-id="${script.entity_id}"]`);
    if (cardElement) {
        const newCard = createScriptCard(script, script.tunnelInfo);
        cardElement.replaceWith(newCard);
    }
    updateShareButtons(); // Ensure button state is updated after rendering
}

// Render all scripts
function renderScripts() {
    const container = $('#scripts-container');
    if (!container) return;
    container.innerHTML = '';
    // Sort: pinned scripts first (in pin order), then the rest
    const pinned = getPinnedScripts();
    const pinnedScripts = filteredScripts.filter(s => pinned.includes(s.entity_id));
    // Sort pinned in the order of the pinned array
    pinnedScripts.sort((a, b) => pinned.indexOf(a.entity_id) - pinned.indexOf(b.entity_id));
    const unpinnedScripts = filteredScripts.filter(s => !pinned.includes(s.entity_id));
    const all = [...pinnedScripts, ...unpinnedScripts];
    all.forEach(script => {
        const card = createScriptCard(script, script.tunnelInfo);
        container.appendChild(card);
    });
    updateShareButtons(); // Ensure button state is updated after rendering
}

// Initialize active tunnel state from existing tunnels
async function initActiveTunnel() {
    try {
        const tunnels = await fetchTunnels();
        if (tunnels.length > 0) {
            // Use the first tunnel as active (assuming single tunnel enforcement)
            setActiveTunnel(tunnels[0].script_id);
        }
    } catch (error) {
        console.error('Error initializing active tunnel:', error);
    }
}

// Initialize the application
async function init() {
    console.log('Initializing application...');
    
    try {
        // Load scripts from Home Assistant
        const scripts = await fetchScripts();
        console.log('Raw scripts from API:', scripts);
        
        // Transform scripts to include tunnel info and loading state
        scriptsData = scripts.map(script => ({
            ...script,
            tunnelInfo: null,
            isLoading: false
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
        
        // Initialize active tunnel state
        await initActiveTunnel();
        
        // Render the UI
        renderScripts();
        setupSearch();
        
        console.log('Application initialized successfully');
        console.log('Loaded', scriptsData.length, 'scripts');
        console.log('Active tunnels:', tunnels.length);
        console.log('Final scripts data:', scriptsData);
        
    } catch (error) {
        console.error('Failed to initialize:', error);
        showError('Failed to initialize the application');
    }
}

// Make functions globally available for HTML onclick attributes
window.shareScript = shareScript;
window.revokeUrl = revokeUrl;
window.copyToClipboard = copyToClipboard;

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', init);
