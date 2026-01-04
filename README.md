# Slack AI Council Bot 🤖

A Slack bot that integrates multiple AI models (OpenAI GPT-4o, Google Gemini 1.5 Pro, X.AI Grok) to provide multi-perspective responses in a single thread. Built with Python and the Slack Bolt framework.

## ✨ Features

### Core Functionality

1. **Multi-Model Integration** 🔌
   - Support for OpenAI (GPT-4o), Google Gemini (1.5 Pro), and X.AI (Grok)
   - Adapter pattern for easy extensibility (Claude, etc.)
   - Unified interface for all AI models

2. **Dynamic Identity Override** 🎭
   - Single Slack bot token with multiple AI personas
   - Custom username and emoji for each model
   - Requires `chat:write.customize` permission

3. **Context Isolation & Filtering** 🔒
   - Each AI model only sees:
     - User messages
     - Its own previous responses
   - Other AI models' responses are filtered out in Compare mode

4. **Async Concurrent Responses** ⚡
   - Multiple AI models respond simultaneously
   - Non-blocking execution for fast responses

5. **Operation Modes** 🎮
   - **Compare Mode** (default): All models respond concurrently to user questions
   - **Debate Mode**: Models respond sequentially, seeing each other's responses

## 🏗️ Architecture

```
slack-ai-council/
├── app.py                 # Main Slack bot application
├── llm_manager.py         # LLM adapter pattern implementation
├── context_filter.py      # Message filtering for context isolation
├── mode_manager.py        # Compare vs Debate mode management
├── requirements.txt       # Python dependencies
├── .env.example          # Environment variables template
└── README.md             # This file
```

### Design Patterns

- **Adapter Pattern**: `llm_manager.py` provides a unified interface for different AI APIs
- **Strategy Pattern**: `mode_manager.py` handles different execution strategies (Compare vs Debate)
- **Filter Pattern**: `context_filter.py` filters messages based on model context needs

## 🚀 Setup

### Prerequisites

- Python 3.10 or higher
- Slack workspace with admin access
- API keys for desired AI models:
  - OpenAI API key
  - Google API key (for Gemini)
  - X.AI API key (for Grok)

### 1. Clone the Repository

```bash
git clone https://github.com/coolestowl/slack-ai-council.git
cd slack-ai-council
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Create Slack App

1. Go to [Slack API Apps](https://api.slack.com/apps)
2. Click "Create New App" → "From scratch"
3. Name it "AI Council" and select your workspace

#### Configure Bot Scopes

In **OAuth & Permissions**, add these Bot Token Scopes:
- `app_mentions:read` - Read mentions
- `channels:history` - Read channel messages
- `chat:write` - Send messages
- `chat:write.customize` - Customize message appearance (username/icon)
- `im:history` - Read DM history
- `im:write` - Send DMs

#### Enable Socket Mode

1. Go to **Socket Mode** and enable it
2. Generate an app-level token with `connections:write` scope
3. Save the token (starts with `xapp-`)

#### Enable Events

1. Go to **Event Subscriptions** and enable events
2. Subscribe to bot events:
   - `app_mention`
   - `message.im`

#### Install App

1. Go to **Install App**
2. Install to your workspace
3. Copy the Bot User OAuth Token (starts with `xoxb-`)

### 4. Configure Environment Variables

```bash
cp .env.example .env
```

Edit `.env` and add your tokens and API keys:

```env
# Slack Configuration
SLACK_BOT_TOKEN=xoxb-your-bot-token-here
SLACK_APP_TOKEN=xapp-your-app-token-here

# AI Model API Keys
OPENAI_API_KEY=sk-your-openai-key
GOOGLE_API_KEY=your-google-api-key
XAI_API_KEY=your-xai-key

# Optional Configuration
DEFAULT_MODE=compare  # compare or debate
```

**Note**: You need at least one AI API key for the bot to work. Missing API keys will be skipped with a warning.

### 5. Run the Bot

```bash
python app.py
```

You should see:
```
✓ Initialized openai adapter
✓ Initialized gemini adapter
✓ Initialized grok adapter
==================================================
Slack AI Council Bot Starting
==================================================
Configured AI Models: openai, gemini, grok
Default Mode: COMPARE
Mode Description: Compare Mode: All AI models respond concurrently
==================================================
```

## 💬 Usage

### Mention the Bot in a Channel

```
@AI Council What's the best approach to learn machine learning?
```

All configured AI models will respond in a thread with their perspectives.

### Inline Mode Specification

You can specify the mode for a single request inline with your question:

```
@AI Council mode=debate What is the future of artificial intelligence?
```

This will use debate mode for this specific request only, without changing the global mode. The default mode (compare) is used when no inline mode is specified.

### Direct Message

Send a DM to the bot with your question, and it will respond with all AI models. You can also use inline mode specification in DMs:

```
mode=compare Explain quantum computing
```

### Mode Commands

Change the global operation mode:

```
/mode compare   # Switch to Compare mode (default)
/mode debate    # Switch to Debate mode
/mode status    # Check current mode
```

**Note**: Mode commands change the global mode for all subsequent requests, while inline mode specification (`mode=debate question`) only affects that specific request.

## 🔧 Extending the Bot

### Adding New AI Models

1. Create a new adapter class in `llm_manager.py`:

```python
class ClaudeAdapter(LLMAdapter):
    def __init__(self):
        super().__init__(
            model_name="claude-3",
            username="Claude",
            icon_emoji=":brain:"
        )
        self.api_key = os.getenv("ANTHROPIC_API_KEY")
    
    async def generate_response(self, messages: List[Dict[str, str]]) -> str:
        # Implementation here
        pass
```

2. Register it in `LLMManager._initialize_adapters()`:

```python
("claude", ClaudeAdapter),
```

3. Add the username to `context_filter.py`:

```python
self.model_usernames = {
    # ... existing models ...
    "Claude": "claude"
}
```

### Customizing System Prompts

Edit the `create_default_system_prompt()` function in `context_filter.py` to customize how each model behaves.

## 🛠️ Development

### Project Structure

- **app.py**: Main entry point, Slack event handlers
- **llm_manager.py**: AI model adapters and management
- **context_filter.py**: Message filtering logic
- **mode_manager.py**: Operation mode management

### Key Functions

- `handle_app_mention()`: Processes @mentions in channels
- `handle_message()`: Processes direct messages
- `handle_compare_mode()`: Concurrent AI responses
- `handle_debate_mode()`: Sequential AI responses
- `filter_messages_for_model()`: Context isolation per model

## 📝 Notes

- The bot uses Socket Mode, so it doesn't require a public URL
- Each AI model only sees user messages and its own history (in Compare mode)
- In Debate mode, models see all previous messages including other AI responses
- Missing API keys are handled gracefully - those models are skipped

## 🐛 Troubleshooting

### "No AI models are configured"

Check that at least one API key is correctly set in your `.env` file.

### Bot doesn't respond

1. Verify Socket Mode is enabled
2. Check that Event Subscriptions are configured
3. Ensure the bot is invited to the channel: `/invite @AI Council`
4. Check the console for error messages

### Custom username not working

Ensure your Slack app has the `chat:write.customize` permission.

## 📄 License

See [LICENSE](LICENSE) file for details.

## 🤝 Contributing

Contributions welcome! Feel free to:
- Add support for more AI models
- Improve context filtering algorithms
- Enhance debate mode functionality
- Add unit tests

## 🌟 Future Enhancements

- [ ] Advanced debate mode with rounds
- [ ] Vote/rating system for best responses
- [ ] Per-channel mode configuration
- [ ] Response caching
- [ ] Streaming responses
- [ ] Web dashboard for analytics