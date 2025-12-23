const chatHistory = document.getElementById('chatHistory');
const userInput = document.getElementById('userInput');
const sendButton = document.getElementById('sendButton');

// Get API URL - use relative path for production
const API_URL = '/chat';

// Allow sending message with Enter key
userInput.addEventListener('keypress', function(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
    }
});

function addMessage(content, isUser = false) {
    const messageDiv = document.createElement('div');
    messageDiv.className = isUser ? 'message user-message' : 'message bot-message';
    
    const messageContent = document.createElement('div');
    messageContent.className = 'message-content';
    
    // Format message content (preserve line breaks)
    const formattedContent = content.split('\n').map(line => {
        if (line.trim() === '') return '<br>';
        return `<p>${escapeHtml(line)}</p>`;
    }).join('');
    
    messageContent.innerHTML = formattedContent;
    messageDiv.appendChild(messageContent);
    
    chatHistory.appendChild(messageDiv);
    chatHistory.scrollTop = chatHistory.scrollHeight;
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function showLoading() {
    const loadingDiv = document.createElement('div');
    loadingDiv.className = 'message bot-message';
    loadingDiv.id = 'loading-message';
    
    const messageContent = document.createElement('div');
    messageContent.className = 'message-content';
    messageContent.innerHTML = '<p class="loading">Thinking...</p>';
    loadingDiv.appendChild(messageContent);
    
    chatHistory.appendChild(loadingDiv);
    chatHistory.scrollTop = chatHistory.scrollHeight;
}

function removeLoading() {
    const loadingMessage = document.getElementById('loading-message');
    if (loadingMessage) {
        loadingMessage.remove();
    }
}

async function sendMessage() {
    const message = userInput.value.trim();
    
    if (!message) {
        return;
    }

    // Add user message to chat
    addMessage(message, true);
    userInput.value = '';
    userInput.disabled = true;
    sendButton.disabled = true;
    sendButton.innerHTML = '<span>Sending...</span>';

    // Show loading indicator
    showLoading();

    try {
        const response = await fetch(API_URL, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ message: message })
        });

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const data = await response.json();

        removeLoading();

        if (data.success) {
            addMessage(data.response);
        } else {
            addMessage(`Sorry, I encountered an error: ${data.detail || data.error || 'Unknown error'}`);
        }
    } catch (error) {
        removeLoading();
        addMessage(`Error: Could not connect to the server. Please check if the backend is running.`);
        console.error('Error:', error);
    } finally {
        userInput.disabled = false;
        sendButton.disabled = false;
        sendButton.innerHTML = '<span>Send</span>';
        userInput.focus();
    }
}

// Focus input on load
window.addEventListener('load', () => {
    userInput.focus();
});

