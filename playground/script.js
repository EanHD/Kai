// Configuration
const API_BASE_URL = 'http://localhost:8000/api/v1';

// State
let currentSessionId = null;
let conversations = [];
let totalCost = 0;
let isProcessing = false;

// DOM Elements
const elements = {
    messages: document.getElementById('messages'),
    messageInput: document.getElementById('messageInput'),
    sendBtn: document.getElementById('sendBtn'),
    status: document.getElementById('status'),
    costBtn: document.getElementById('costBtn'),
    costModal: document.getElementById('costModal'),
    closeCostModal: document.getElementById('closeCostModal'),
    newChatBtn: document.getElementById('newChatBtn'),
    conversationList: document.getElementById('conversationList'),
    modelSelect: document.getElementById('modelSelect'),
    showThinking: document.getElementById('showThinking'),
    showCitations: document.getElementById('showCitations'),
};

// Initialize
async function init() {
    await checkAPIStatus();
    startNewConversation();
    attachEventListeners();
    
    // Auto-resize textarea
    elements.messageInput.addEventListener('input', autoResizeTextarea);
}

// Check API Status
async function checkAPIStatus() {
    try {
        const response = await fetch(`${API_BASE_URL}/health`);
        if (response.ok) {
            updateStatus('connected', 'Connected');
        } else {
            updateStatus('error', 'API Error');
        }
    } catch (error) {
        updateStatus('error', 'Disconnected');
        console.error('API health check failed:', error);
    }
}

// Update Status Indicator
function updateStatus(status, text) {
    const statusDot = elements.status.querySelector('.status-dot');
    const statusText = elements.status.querySelector('.status-text');
    
    statusDot.className = 'status-dot';
    if (status === 'connected') {
        statusDot.classList.add('connected');
    }
    statusText.textContent = text;
}

// Event Listeners
function attachEventListeners() {
    elements.sendBtn.addEventListener('click', sendMessage);
    elements.messageInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });
    
    elements.costBtn.addEventListener('click', () => {
        elements.costModal.classList.add('active');
        updateCostBreakdown();
    });
    
    elements.closeCostModal.addEventListener('click', () => {
        elements.costModal.classList.remove('active');
    });
    
    elements.newChatBtn.addEventListener('click', startNewConversation);
    
    // Close modal on outside click
    elements.costModal.addEventListener('click', (e) => {
        if (e.target === elements.costModal) {
            elements.costModal.classList.remove('active');
        }
    });
}

// Start New Conversation
function startNewConversation() {
    currentSessionId = generateSessionId();
    
    const conversation = {
        id: currentSessionId,
        title: 'New Chat',
        messages: [],
        createdAt: new Date(),
    };
    
    conversations.unshift(conversation);
    updateConversationList();
    clearMessages();
}

// Generate Session ID
function generateSessionId() {
    return `session_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
}

// Update Conversation List
function updateConversationList() {
    elements.conversationList.innerHTML = conversations.map(conv => `
        <div class="conversation-item ${conv.id === currentSessionId ? 'active' : ''}" 
             data-id="${conv.id}">
            <div class="title">${escapeHtml(conv.title)}</div>
            <div class="preview">${conv.messages.length} messages</div>
        </div>
    `).join('');
    
    // Add click handlers
    document.querySelectorAll('.conversation-item').forEach(item => {
        item.addEventListener('click', () => {
            switchConversation(item.dataset.id);
        });
    });
}

// Switch Conversation
function switchConversation(sessionId) {
    currentSessionId = sessionId;
    const conversation = conversations.find(c => c.id === sessionId);
    
    if (conversation) {
        clearMessages();
        conversation.messages.forEach(msg => {
            if (msg.role === 'user') {
                addMessage('user', msg.content);
            } else {
                addMessage('assistant', msg.content, msg.thinking, msg.citations, msg.meta);
            }
        });
        updateConversationList();
    }
}

// Clear Messages
function clearMessages() {
    elements.messages.innerHTML = '';
}

// Send Message
async function sendMessage() {
    if (isProcessing) return;
    
    const message = elements.messageInput.value.trim();
    if (!message) return;
    
    // Add user message
    addMessage('user', message);
    storeMessage('user', message);
    
    // Clear input
    elements.messageInput.value = '';
    autoResizeTextarea();
    
    // Show typing indicator
    const typingId = addTypingIndicator();
    
    isProcessing = true;
    elements.sendBtn.disabled = true;
    
    try {
        const response = await fetch(`${API_BASE_URL}/query`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                query: message,
                session_id: currentSessionId,
                stream: false,
            }),
        });
        
        if (!response.ok) {
            throw new Error(`API error: ${response.status}`);
        }
        
        const data = await response.json();
        
        // Remove typing indicator
        removeTypingIndicator(typingId);
        
        // Add assistant response
        const thinking = data.thinking || null;
        const citations = data.sources || [];
        const meta = {
            cost: data.cost || 0,
            tokens: data.token_count || 0,
            time: data.processing_time || 0,
        };
        
        addMessage('assistant', data.response, thinking, citations, meta);
        storeMessage('assistant', data.response, thinking, citations, meta);
        
        // Update cost
        if (data.cost) {
            totalCost += data.cost;
            elements.costBtn.textContent = `💰 Cost: $${totalCost.toFixed(4)}`;
        }
        
        // Update conversation title if it's the first message
        updateConversationTitle(message);
        
    } catch (error) {
        removeTypingIndicator(typingId);
        addMessage('assistant', '❌ Error: Failed to get response. Please check if the API is running.', null, [], { error: true });
        console.error('Error sending message:', error);
    } finally {
        isProcessing = false;
        elements.sendBtn.disabled = false;
        elements.messageInput.focus();
    }
}

// Store Message in Conversation
function storeMessage(role, content, thinking = null, citations = [], meta = {}) {
    const conversation = conversations.find(c => c.id === currentSessionId);
    if (conversation) {
        conversation.messages.push({ role, content, thinking, citations, meta });
    }
}

// Update Conversation Title
function updateConversationTitle(firstMessage) {
    const conversation = conversations.find(c => c.id === currentSessionId);
    if (conversation && conversation.messages.length <= 2) {
        conversation.title = firstMessage.slice(0, 30) + (firstMessage.length > 30 ? '...' : '');
        updateConversationList();
    }
}

// Add Message to Chat
function addMessage(role, content, thinking = null, citations = [], meta = {}) {
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${role}`;
    
    const avatar = role === 'user' ? '👤' : '🤖';
    
    let thinkingHtml = '';
    if (thinking && elements.showThinking.checked) {
        thinkingHtml = `<div class="message-thinking">💭 ${escapeHtml(thinking)}</div>`;
    }
    
    let citationsHtml = '';
    if (citations && citations.length > 0 && elements.showCitations.checked) {
        citationsHtml = `
            <div class="message-citations">
                <strong>Sources:</strong>
                ${citations.map((cite, i) => `
                    <a href="${cite.url || '#'}" target="_blank" class="citation">
                        [${i + 1}] ${escapeHtml(cite.title || cite.url || 'Source')}
                    </a>
                `).join('')}
            </div>
        `;
    }
    
    let metaHtml = '';
    if (meta && Object.keys(meta).length > 0 && !meta.error) {
        const parts = [];
        if (meta.cost) parts.push(`$${meta.cost.toFixed(4)}`);
        if (meta.tokens) parts.push(`${meta.tokens} tokens`);
        if (meta.time) parts.push(`${meta.time.toFixed(2)}s`);
        
        if (parts.length > 0) {
            metaHtml = `<div class="message-meta">${parts.join(' • ')}</div>`;
        }
    }
    
    messageDiv.innerHTML = `
        <div class="message-avatar">${avatar}</div>
        <div class="message-content">
            <div class="message-bubble">
                ${thinkingHtml}
                <div class="message-text">${formatMessage(content)}</div>
                ${citationsHtml}
            </div>
            ${metaHtml}
        </div>
    `;
    
    elements.messages.appendChild(messageDiv);
    scrollToBottom();
}

// Add Typing Indicator
function addTypingIndicator() {
    const id = `typing_${Date.now()}`;
    const typingDiv = document.createElement('div');
    typingDiv.className = 'message assistant';
    typingDiv.id = id;
    typingDiv.innerHTML = `
        <div class="message-avatar">🤖</div>
        <div class="message-content">
            <div class="message-bubble">
                <div class="typing-indicator">
                    <div class="typing-dot"></div>
                    <div class="typing-dot"></div>
                    <div class="typing-dot"></div>
                </div>
            </div>
        </div>
    `;
    
    elements.messages.appendChild(typingDiv);
    scrollToBottom();
    return id;
}

// Remove Typing Indicator
function removeTypingIndicator(id) {
    const element = document.getElementById(id);
    if (element) {
        element.remove();
    }
}

// Format Message (support markdown-like formatting)
function formatMessage(text) {
    let formatted = escapeHtml(text);
    
    // Code blocks
    formatted = formatted.replace(/```([\s\S]*?)```/g, '<pre><code>$1</code></pre>');
    
    // Inline code
    formatted = formatted.replace(/`([^`]+)`/g, '<code>$1</code>');
    
    // Bold
    formatted = formatted.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
    
    // Italic
    formatted = formatted.replace(/\*([^*]+)\*/g, '<em>$1</em>');
    
    // Links
    formatted = formatted.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank">$1</a>');
    
    // Line breaks
    formatted = formatted.replace(/\n/g, '<br>');
    
    return formatted;
}

// Update Cost Breakdown
function updateCostBreakdown() {
    // This would be enhanced with actual API data
    const breakdown = `
        <div class="cost-item">
            <span>Total Cost:</span>
            <span class="cost-value">$${totalCost.toFixed(4)}</span>
        </div>
        <div class="cost-item">
            <span>Current Session:</span>
            <span class="cost-value">${currentSessionId}</span>
        </div>
        <div class="cost-item">
            <span>Messages:</span>
            <span class="cost-value">${conversations.reduce((sum, c) => sum + c.messages.length, 0)}</span>
        </div>
    `;
    
    document.getElementById('costBreakdown').innerHTML = breakdown;
}

// Auto-resize Textarea
function autoResizeTextarea() {
    elements.messageInput.style.height = 'auto';
    elements.messageInput.style.height = elements.messageInput.scrollHeight + 'px';
}

// Scroll to Bottom
function scrollToBottom() {
    elements.messages.scrollTop = elements.messages.scrollHeight;
}

// Escape HTML
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Initialize on load
document.addEventListener('DOMContentLoaded', init);

// Periodic API health check
setInterval(checkAPIStatus, 30000);
