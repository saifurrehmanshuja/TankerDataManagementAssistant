// Floating Chatbot Widget - Reuses exact logic from script.js
document.addEventListener('DOMContentLoaded', () => {
    const toggle = document.getElementById('chatbotToggle');
    const close = document.getElementById('chatbotClose');
    const window = document.getElementById('chatbotWindow');
    const input = document.getElementById('chatbotInput');
    const sendBtn = document.getElementById('chatbotSend');
    const messages = document.getElementById('chatbotMessages');
    
    if (!toggle || !window || !input || !sendBtn || !messages) {
        return; // Widget not present on this page
    }
    
    const API_URL = '/chat';
    let lastChatId = null; // Track last chat_id for feedback
    
    // Toggle window
    toggle.addEventListener('click', () => {
        window.classList.toggle('hidden');
        if (!window.classList.contains('hidden')) {
            input.focus();
        }
    });
    
    // Close window
    if (close) {
        close.addEventListener('click', () => {
            window.classList.add('hidden');
        });
    }
    
    // Add message function - matches script.js pattern
    function addMessage(content, isUser = false, chatId = null, followupSuggestions = null) {
        const messageDiv = document.createElement('div');
        messageDiv.className = isUser ? 'chatbot-message user' : 'chatbot-message bot';
        
        // Format message content (preserve line breaks) - exact same as script.js
        const formattedContent = content.split('\n').map(line => {
            if (line.trim() === '') return '<br>';
            return `<p style="margin: 0;">${escapeHtml(line)}</p>`;
        }).join('');
        
        messageDiv.innerHTML = formattedContent;
        
        // Add feedback buttons for bot messages
        if (!isUser && chatId) {
            lastChatId = chatId;
            const feedbackDiv = document.createElement('div');
            feedbackDiv.className = 'chatbot-feedback';
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
            suggestionsDiv.className = 'chatbot-suggestions';
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
                    input.value = suggestion;
                    sendMessage();
                };
                suggestionsDiv.appendChild(suggestionBtn);
            });
            
            messageDiv.appendChild(suggestionsDiv);
        }
        
        messages.appendChild(messageDiv);
        messages.scrollTop = messages.scrollHeight;
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
                    context: 'dashboard',
                    chat_id: chatId,
                    feedback: feedback
                })
            });
            
            const data = await response.json();
            if (data.success) {
                // Hide feedback buttons after feedback is sent
                const feedbackDivs = document.querySelectorAll('.chatbot-feedback');
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
        loadingDiv.className = 'chatbot-message bot';
        loadingDiv.id = 'loading-message';
        loadingDiv.innerHTML = '<div class="typing-indicator" style="display: flex; gap: 6px; padding: 12px 20px;"><span style="width: 8px; height: 8px; background: #667eea; border-radius: 50%; animation: typing 1.4s infinite;"></span><span style="width: 8px; height: 8px; background: #667eea; border-radius: 50%; animation: typing 1.4s infinite; animation-delay: 0.2s;"></span><span style="width: 8px; height: 8px; background: #667eea; border-radius: 50%; animation: typing 1.4s infinite; animation-delay: 0.4s;"></span></div>';
        messages.appendChild(loadingDiv);
        messages.scrollTop = messages.scrollHeight;
    }
    
    function removeLoading() {
        const loadingMessage = document.getElementById('loading-message');
        if (loadingMessage) {
            loadingMessage.remove();
        }
    }
    
    // Send message function - EXACT same pattern as script.js
    async function sendMessage() {
        const message = input.value.trim();
        
        if (!message) {
            return;
        }

        // Add user message to chat
        addMessage(message, true);
        input.value = '';
        input.disabled = true;
        sendBtn.disabled = true;
        sendBtn.textContent = 'Sending...';

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
                    context: "dashboard"
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
            input.disabled = false;
            sendBtn.disabled = false;
            sendBtn.textContent = 'Send';
            input.focus();
        }
    }
    
    // Event listeners - EXACT same as script.js
    input.addEventListener('keypress', function(e) {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });

    sendBtn.addEventListener('click', sendMessage);
    
    // Ensure send button is not a form submit button
    if (sendBtn.type === 'submit') {
        sendBtn.type = 'button';
    }
    
    // Add welcome message
    if (messages.children.length === 0) {
        addMessage('Hello! I can help you with tanker information, analytics, and predictions. What would you like to know?', false);
    }
});
