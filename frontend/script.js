document.addEventListener('DOMContentLoaded', () => {
    const chatHistory = document.getElementById('chatHistory');
    const userInput = document.getElementById('userInput');
    const sendButton = document.getElementById('sendButton');

    if (!chatHistory || !userInput || !sendButton) {
        console.error('Chat elements not found');
        return;
    }

    // Get API URL - use relative path for production
    const API_URL = '/chat';
    let lastChatId = null; // Track last chat_id for feedback

    // Allow sending message with Enter key
    userInput.addEventListener('keypress', function(e) {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });

    // Send button click handler
    sendButton.addEventListener('click', sendMessage);

function addMessage(content, isUser = false, chatId = null, followupSuggestions = null) {
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
    
    // Add feedback buttons for bot messages
    if (!isUser && chatId) {
        lastChatId = chatId;
        const feedbackDiv = document.createElement('div');
        feedbackDiv.className = 'chat-feedback';
        feedbackDiv.style.cssText = 'margin-top: 8px; display: flex; gap: 8px; align-items: center;';
        
        const helpfulBtn = document.createElement('button');
        helpfulBtn.textContent = '👍 Helpful';
        helpfulBtn.style.cssText = 'padding: 4px 12px; font-size: 12px; border: 1px solid #ddd; border-radius: 4px; background: white; cursor: pointer;';
        helpfulBtn.onclick = () => sendFeedback(chatId, 'helpful');
        
        const notHelpfulBtn = document.createElement('button');
        notHelpfulBtn.textContent = '👎 Not helpful';
        notHelpfulBtn.style.cssText = 'padding: 4px 12px; font-size: 12px; border: 1px solid #ddd; border-radius: 4px; background: white; cursor: pointer;';
        notHelpfulBtn.onclick = () => sendFeedback(chatId, 'not_helpful');
        
        feedbackDiv.appendChild(helpfulBtn);
        feedbackDiv.appendChild(notHelpfulBtn);
        messageDiv.appendChild(feedbackDiv);
    }
    
    // Add follow-up suggestions
    if (!isUser && followupSuggestions && followupSuggestions.length > 0) {
        const suggestionsDiv = document.createElement('div');
        suggestionsDiv.className = 'chat-suggestions';
        suggestionsDiv.style.cssText = 'margin-top: 12px; padding-top: 12px; border-top: 1px solid #eee;';
        
        const suggestionsTitle = document.createElement('div');
        suggestionsTitle.textContent = 'Suggested follow-ups:';
        suggestionsTitle.style.cssText = 'font-size: 12px; color: #666; margin-bottom: 8px;';
        suggestionsDiv.appendChild(suggestionsTitle);
        
        followupSuggestions.forEach(suggestion => {
            const suggestionBtn = document.createElement('button');
            suggestionBtn.textContent = suggestion;
            suggestionBtn.style.cssText = 'display: block; width: 100%; padding: 8px 12px; margin-bottom: 6px; font-size: 12px; text-align: left; border: 1px solid #667eea; border-radius: 4px; background: #f8f9ff; color: #667eea; cursor: pointer;';
            suggestionBtn.onmouseover = () => suggestionBtn.style.background = '#eef0ff';
            suggestionBtn.onmouseout = () => suggestionBtn.style.background = '#f8f9ff';
            suggestionBtn.onclick = () => {
                userInput.value = suggestion;
                sendMessage();
            };
            suggestionsDiv.appendChild(suggestionBtn);
        });
        
        messageDiv.appendChild(suggestionsDiv);
    }
    
    chatHistory.appendChild(messageDiv);
    chatHistory.scrollTop = chatHistory.scrollHeight;
}

// Send feedback function
async function sendFeedback(chatId, feedback) {
    try {
        const response = await fetch('/chat', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                message: '', // Empty for feedback
                context: 'full_chat',
                chat_id: chatId,
                feedback: feedback
            })
        });
        
        const data = await response.json();
        if (data.success) {
            // Hide feedback buttons after feedback is sent
            const feedbackDivs = document.querySelectorAll('.chat-feedback');
            feedbackDivs.forEach(div => {
                if (div.querySelector(`button[onclick*="${chatId}"]`)) {
                    div.style.display = 'none';
                }
            });
        }
    } catch (error) {
        console.error('Error sending feedback:', error);
    }
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
    messageContent.innerHTML = '<div class="typing-indicator"><span></span><span></span><span></span></div>';
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
        sendButton.innerHTML = 'Sending...';

        // Show loading indicator
        showLoading();

        try {
            const response = await fetch(API_URL, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ 
                    message: message,
                    context: "full_chat"
                })
            });

            if (!response.ok) {
                let errorText = `HTTP error! status: ${response.status}`;
                try {
                    const errorData = await response.json();
                    errorText = errorData.detail || errorData.message || errorText;
                } catch (e) {
                    errorText = await response.text() || errorText;
                }
                throw new Error(errorText);
            }

            const data = await response.json();

            removeLoading();

            if (data && data.response) {
                // Track implicit feedback: if user asks a follow-up, previous response was likely not fully helpful
                if (lastChatId && message.toLowerCase().includes('?')) {
                    // User asked a follow-up question - implicit negative feedback
                    sendFeedback(lastChatId, 'not_helpful').catch(() => {});
                }
                
                addMessage(
                    data.response, 
                    false, 
                    data.chat_id || null,
                    data.followup_suggestions || null
                );
            } else if (data && data.success === false) {
                addMessage(data.response || `Sorry, I encountered an error: ${data.detail || 'Unknown error'}`);
            } else {
                addMessage('Sorry, I received an unexpected response. Please try again.');
            }
        } catch (error) {
            removeLoading();
            addMessage(`Error: Could not connect to the server. ${error.message || 'Please check if the backend is running.'}`);
            console.error('Error:', error);
        } finally {
            userInput.disabled = false;
            sendButton.disabled = false;
            sendButton.innerHTML = 'Send';
            userInput.focus();
        }
    }

    // Add welcome message
    addMessage('Hello! I can help you with tanker information, analytics, and predictions. What would you like to know?', false);

    // Focus input on load
    userInput.focus();
});

