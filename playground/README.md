# Kai Playground 🤖

A modern, sleek web interface for interacting with the Kai LLM Orchestrator.

## Features

- 🎨 **Modern Dark UI** - Clean, professional interface with purple accents
- 💬 **Multi-Conversation** - Manage multiple chat sessions simultaneously
- 💰 **Cost Tracking** - Real-time cost monitoring for API usage
- 🎯 **Smart Routing** - Visual feedback when using local vs external models
- 📊 **Citations** - View web search sources and references
- 💭 **Thinking Display** - See Kai's reasoning process (toggle on/off)
- ⚙️ **Settings Panel** - Customize model selection and display options
- 📱 **Responsive Design** - Works on desktop and mobile

## Quick Start

### 1. Start the Kai API

```bash
cd /home/eanhd/projects/kai
python -m src.api.main
```

The API should be running on `http://localhost:8000`

### 2. Open the Playground

Simply open `playground/index.html` in your web browser:

```bash
# Using default browser
xdg-open playground/index.html

# Or with a specific browser
firefox playground/index.html
google-chrome playground/index.html
```

### 3. Start Chatting!

The playground will automatically connect to your local Kai API instance.

## Usage

### Basic Chat
1. Type your message in the input box
2. Press Enter or click the send button
3. Watch Kai process and respond

### Keyboard Shortcuts
- `Enter` - Send message
- `Shift + Enter` - New line in message

### Features

#### New Conversation
Click the "➕ New Chat" button to start a fresh conversation

#### Switch Conversations
Click any conversation in the sidebar to switch between chats

#### View Costs
Click the "💰 Cost" button to see detailed cost breakdown

#### Settings
- **Model Selection**: Choose between Auto, Local Only, or Grok Only
- **Show Thinking**: Toggle display of Kai's reasoning process
- **Show Citations**: Toggle display of web search sources

## API Endpoints Used

- `GET /api/v1/health` - Check API status
- `POST /api/v1/query` - Send queries to Kai

## Configuration

The playground connects to `http://localhost:8000` by default. To change this, edit the `API_BASE_URL` in `script.js`:

```javascript
const API_BASE_URL = 'http://your-api-url:port/api/v1';
```

## Browser Support

- ✅ Chrome/Edge (recommended)
- ✅ Firefox
- ✅ Safari
- ✅ Opera

## Screenshots

### Main Chat Interface
Clean, modern dark theme with conversation sidebar and message input.

### Cost Tracking
Real-time cost monitoring with detailed breakdowns per message.

### Multi-Conversation
Manage multiple chat sessions with easy switching.

## Troubleshooting

### "Disconnected" Status
- Ensure the Kai API is running on port 8000
- Check that Ollama is running (for local models)
- Verify no firewall is blocking localhost:8000

### Messages Not Sending
- Check browser console for errors (F12)
- Verify API is responding: `curl http://localhost:8000/api/v1/health`
- Ensure you have a valid session

### CORS Errors
If running the API on a different port/domain, you may need to enable CORS in the API configuration.

## Development

The playground is built with vanilla JavaScript - no frameworks required!

### File Structure
```
playground/
├── index.html    # Main HTML structure
├── style.css     # Styling and theming
├── script.js     # JavaScript logic
└── README.md     # This file
```

### Customization

#### Colors
Edit CSS variables in `style.css`:
```css
:root {
    --accent: #8b5cf6;  /* Purple accent */
    --bg-primary: #0f0f0f;  /* Dark background */
    /* ... */
}
```

#### API Configuration
Edit `API_BASE_URL` in `script.js`

## Future Enhancements

- [ ] Streaming responses
- [ ] Conversation export (JSON, Markdown)
- [ ] File upload support
- [ ] Voice input
- [ ] Dark/Light theme toggle
- [ ] Conversation search
- [ ] Message editing
- [ ] Regenerate responses

## License

Part of the Kai LLM Orchestrator project.
