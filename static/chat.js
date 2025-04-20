document.addEventListener('DOMContentLoaded', () => {
    const messagesContainer = document.getElementById('messages');
    const chatForm = document.getElementById('chat-form');
    const messageInput = document.getElementById('message-input');
    const typingIndicator = document.getElementById('typing');

    // Function to add copy buttons to code blocks
    function addCopyButtons(messageElement) {
        messageElement.querySelectorAll('pre').forEach(block => {
            const button = document.createElement('button');
            button.textContent = 'Copy';
            button.className = 'copy-button';
            button.onclick = () => {
                navigator.clipboard.writeText(block.querySelector('code').innerText);
                button.textContent = 'Copied!';
                setTimeout(() => button.textContent = 'Copy', 1500);
            };
            block.style.position = 'relative';
            button.style.position = 'absolute';
            button.style.top = '8px';
            button.style.right = '8px';
            block.appendChild(button);
        });
    }

    // Function to create a new message element
    function createMessageElement(content, isUser = false) {
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${isUser ? 'user' : 'assistant'}`;
        
        const contentDiv = document.createElement('div');
        contentDiv.className = 'message-content';
        
        if (isUser) {
            contentDiv.textContent = content;
        } else {
            // Parse markdown for assistant messages
            contentDiv.innerHTML = marked.parse(content);
            // Apply syntax highlighting
            contentDiv.querySelectorAll('pre code').forEach(block => {
                hljs.highlightElement(block);
            });
            // Add copy buttons to code blocks
            addCopyButtons(contentDiv);
            // Render LaTeX if present
            if (window.MathJax) {
                MathJax.typesetPromise([contentDiv]);
            }
        }
        
        messageDiv.appendChild(contentDiv);
        return messageDiv;
    }

    // Function to scroll to bottom of messages
    function scrollToBottom() {
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
    }

    // Function to show/hide typing indicator
    function setTypingIndicator(visible) {
        typingIndicator.className = `typing-indicator ${visible ? '' : 'hidden'}`;
    }

    // Function to handle the chat stream
    async function handleChatStream(response) {
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let assistantMessage = createMessageElement('', false);
        let contentDiv = assistantMessage.querySelector('.message-content');
        let fullText = '';
        
        messagesContainer.appendChild(assistantMessage);
        scrollToBottom();

        try {
            while (true) {
                const {value, done} = await reader.read();
                if (done) break;
                
                const chunk = decoder.decode(value);
                fullText += chunk;
                // Show raw text while streaming
                contentDiv.textContent = fullText;
                scrollToBottom();
            }

            // After stream completes, render the full message with Markdown
            contentDiv.innerHTML = marked.parse(fullText);
            // Apply syntax highlighting
            contentDiv.querySelectorAll('pre code').forEach(block => {
                hljs.highlightElement(block);
            });
            // Add copy buttons
            addCopyButtons(contentDiv);
            // Render LaTeX
            if (window.MathJax) {
                MathJax.typesetPromise([contentDiv]);
            }
        } catch (error) {
            contentDiv.textContent += '\n[Error: Could not complete the response]';
            console.error('Stream reading error:', error);
        } finally {
            setTypingIndicator(false);
        }
    }

    // Function to send message and handle response
    async function sendMessage(message) {
        // Add user message to chat
        const userMessage = createMessageElement(message, true);
        messagesContainer.appendChild(userMessage);
        scrollToBottom();

        // Show typing indicator
        setTypingIndicator(true);

        try {
            const response = await fetch('/api/v1/chat', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    message: message,
                    stream: true
                })
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            await handleChatStream(response);

        } catch (error) {
            console.error('Error:', error);
            const errorMessage = createMessageElement(
                'Sorry, I encountered an error processing your request.',
                false
            );
            messagesContainer.appendChild(errorMessage);
            setTypingIndicator(false);
        }

        scrollToBottom();
    }

    // Handle form submission
    chatForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const message = messageInput.value.trim();
        if (!message) return;

        messageInput.value = '';
        await sendMessage(message);
    });

    // Handle input key press (Enter to send)
    messageInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            chatForm.dispatchEvent(new Event('submit'));
            e.preventDefault();
        }
    });
}); 