"""
Slack AI Council Bot - Main Application

This is the main application file that initializes the Slack bot and handles
incoming messages. It coordinates between multiple AI models to provide
multi-perspective responses in Slack threads.
"""

import os
import re
import asyncio
from typing import List, Dict, Any
from dotenv import load_dotenv
from slack_bolt.async_app import AsyncApp
from slack_bolt.adapter.socket_mode.async_handler import AsyncSocketModeHandler

from llm_manager import LLMManager, LLMAdapter
from context_filter import ContextFilter, create_default_system_prompt
from mode_manager import ModeManager, ModeCommand

# Load environment variables
load_dotenv()

# Initialize Slack app
app = AsyncApp(token=os.getenv("SLACK_BOT_TOKEN"))

# Initialize managers
llm_manager = LLMManager()
mode_manager = ModeManager(default_mode=os.getenv("DEFAULT_MODE", "compare"))
context_filter = None  # Will be initialized after getting bot user ID


async def initialize_context_filter():
    """Initialize context filter with bot user ID"""
    global context_filter
    try:
        auth_response = await app.client.auth_test()
        bot_user_id = auth_response["user_id"]
        context_filter = ContextFilter(bot_user_id)
        print(f"✓ Context filter initialized with bot user ID: {bot_user_id}")
    except Exception as e:
        print(f"✗ Error initializing context filter: {e}")
        # Create a fallback context filter
        context_filter = ContextFilter("UNKNOWN")


async def fetch_thread_messages(channel: str, thread_ts: str) -> List[Dict[str, Any]]:
    """
    Fetch all messages from a thread
    
    Args:
        channel: Channel ID
        thread_ts: Thread timestamp
    
    Returns:
        List of message objects
    """
    try:
        result = await app.client.conversations_replies(
            channel=channel,
            ts=thread_ts,
            limit=100
        )
        return result.get("messages", [])
    except Exception as e:
        print(f"Error fetching thread messages: {e}")
        return []


async def send_model_response(
    channel: str,
    thread_ts: str,
    adapter: LLMAdapter,
    response_text: str
):
    """
    Send a response to Slack with custom username and icon
    
    Args:
        channel: Channel ID
        thread_ts: Thread timestamp
        adapter: LLM adapter with display config
        response_text: Response text to send
    """
    try:
        display_config = adapter.get_display_config()
        await app.client.chat_postMessage(
            channel=channel,
            thread_ts=thread_ts,
            text=response_text,
            username=display_config["username"],
            icon_emoji=display_config["icon_emoji"]
        )
    except Exception as e:
        print(f"Error sending message from {adapter.username}: {e}")


async def process_model_response(
    adapter: LLMAdapter,
    channel: str,
    thread_ts: str,
    thread_messages: List[Dict[str, Any]],
    mode: str
):
    """
    Process and send response from a single AI model
    
    Args:
        adapter: LLM adapter to use
        channel: Channel ID
        thread_ts: Thread timestamp
        thread_messages: List of thread messages
        mode: Current operation mode
    """
    try:
        # Build prompt with filtered context
        system_prompt = create_default_system_prompt(adapter.username, mode)
        messages = context_filter.build_prompt_with_context(
            thread_messages,
            adapter.username,
            system_prompt
        )
        
        # Generate response
        response = await adapter.generate_response(messages)
        
        # Send to Slack
        await send_model_response(channel, thread_ts, adapter, response)
        
        print(f"✓ {adapter.username} responded in thread {thread_ts}")
    except Exception as e:
        error_message = f"Error processing response: {str(e)}"
        print(f"✗ {adapter.username} error: {error_message}")
        await send_model_response(channel, thread_ts, adapter, error_message)


async def handle_compare_mode(
    channel: str,
    thread_ts: str,
    thread_messages: List[Dict[str, Any]]
):
    """
    Handle message in Compare mode (concurrent responses)
    
    Args:
        channel: Channel ID
        thread_ts: Thread timestamp
        thread_messages: List of thread messages
    """
    adapters = llm_manager.get_all_adapters()
    
    if not adapters:
        await app.client.chat_postMessage(
            channel=channel,
            thread_ts=thread_ts,
            text="No AI models are configured. Please check your API keys."
        )
        return
    
    # Process all models concurrently
    tasks = [
        process_model_response(
            adapter,
            channel,
            thread_ts,
            thread_messages,
            "compare"
        )
        for adapter in adapters
    ]
    
    await asyncio.gather(*tasks, return_exceptions=True)


async def handle_debate_mode(
    channel: str,
    thread_ts: str,
    thread_messages: List[Dict[str, Any]]
):
    """
    Handle message in Debate mode (sequential responses)
    
    Args:
        channel: Channel ID
        thread_ts: Thread timestamp
        thread_messages: List of thread messages
    """
    adapters = llm_manager.get_all_adapters()
    
    if not adapters:
        await app.client.chat_postMessage(
            channel=channel,
            thread_ts=thread_ts,
            text="No AI models are configured. Please check your API keys."
        )
        return
    
    # Process models sequentially
    for adapter in adapters:
        # Fetch updated thread messages before each response
        updated_messages = await fetch_thread_messages(channel, thread_ts)
        
        await process_model_response(
            adapter,
            channel,
            thread_ts,
            updated_messages,
            "debate"
        )


def determine_request_mode(text: str) -> str:
    """
    Determine the operation mode for a request
    
    Args:
        text: Message text (already cleaned, without bot mentions)
    
    Returns:
        Mode string ("compare" or "debate")
    """
    # Check for inline mode specification (e.g., "mode=debate What is AI?")
    inline_mode = ModeCommand.extract_inline_mode(text)
    
    if inline_mode:
        # Use inline specified mode for this request only
        mode = inline_mode["mode"]
        print(f"Using inline mode '{mode}' for this request")
        return mode
    else:
        # Use the current global mode
        return mode_manager.get_mode().value


async def handle_request_by_mode(request_mode: str, channel: str, thread_ts: str, thread_messages: List[Dict[str, Any]]):
    """
    Handle request based on the specified mode
    
    Args:
        request_mode: Mode to use ("compare" or "debate")
        channel: Channel ID
        thread_ts: Thread timestamp
        thread_messages: List of thread messages
    """
    if request_mode == "compare":
        await handle_compare_mode(channel, thread_ts, thread_messages)
    elif request_mode == "debate":
        await handle_debate_mode(channel, thread_ts, thread_messages)


@app.event("app_mention")
async def handle_app_mention(event, say):
    """
    Handle when the bot is mentioned in a channel
    
    Args:
        event: Event data from Slack
        say: Function to send a message
    """
    try:
        channel = event["channel"]
        thread_ts = event.get("thread_ts", event["ts"])
        text = event.get("text", "")
        
        # Remove bot mention from text for parsing
        # Slack mentions look like "<@U12345> message text"
        text_without_mention = re.sub(r'<@[A-Z0-9]+>\s*', '', text, count=1).strip()
        
        # Check if this is a mode command
        command = ModeCommand.parse_command(text_without_mention)
        
        if command:
            if command["command"] == "set_mode":
                new_mode = command["mode"]
                mode_manager.set_mode(new_mode)
                await say(
                    text=f"✓ Mode changed to: {new_mode.upper()}\n{mode_manager.get_mode_description()}",
                    thread_ts=thread_ts
                )
            elif command["command"] == "get_mode":
                await say(
                    text=f"Current mode: {mode_manager.get_mode().value.upper()}\n{mode_manager.get_mode_description()}",
                    thread_ts=thread_ts
                )
            return
        
        # Determine which mode to use for this request
        request_mode = determine_request_mode(text_without_mention)
        
        # Fetch thread messages
        thread_messages = await fetch_thread_messages(channel, thread_ts)
        
        # Handle based on the determined mode
        await handle_request_by_mode(request_mode, channel, thread_ts, thread_messages)
    
    except Exception as e:
        print(f"Error in handle_app_mention: {e}")
        await say(
            text=f"Error processing request: {str(e)}",
            thread_ts=event.get("thread_ts", event["ts"])
        )


@app.event("message")
async def handle_message(event, say):
    """
    Handle direct messages to the bot
    
    Args:
        event: Event data from Slack
        say: Function to send a message
    """
    # Skip bot messages to avoid loops
    if event.get("bot_id"):
        return
    
    # Skip if message is in a channel (only handle DMs)
    if event.get("channel_type") != "im":
        return
    
    try:
        channel = event["channel"]
        thread_ts = event.get("thread_ts", event["ts"])
        text = event.get("text", "")
        
        # Check if this is a mode command
        command = ModeCommand.parse_command(text)
        
        if command:
            if command["command"] == "set_mode":
                new_mode = command["mode"]
                mode_manager.set_mode(new_mode)
                await say(
                    text=f"✓ Mode changed to: {new_mode.upper()}\n{mode_manager.get_mode_description()}",
                    thread_ts=thread_ts
                )
            elif command["command"] == "get_mode":
                await say(
                    text=f"Current mode: {mode_manager.get_mode().value.upper()}\n{mode_manager.get_mode_description()}",
                    thread_ts=thread_ts
                )
            return
        
        # Determine which mode to use for this request
        request_mode = determine_request_mode(text)
        
        # Fetch thread messages
        thread_messages = await fetch_thread_messages(channel, thread_ts)
        
        # Handle based on the determined mode
        await handle_request_by_mode(request_mode, channel, thread_ts, thread_messages)
    
    except Exception as e:
        print(f"Error in handle_message: {e}")
        await say(
            text=f"Error processing request: {str(e)}",
            thread_ts=event.get("thread_ts", event["ts"])
        )


async def main():
    """Main function to start the bot"""
    # Initialize context filter
    await initialize_context_filter()
    
    # Print configuration
    print("\n" + "="*50)
    print("Slack AI Council Bot Starting")
    print("="*50)
    print(f"Configured AI Models: {', '.join(llm_manager.get_adapter_names())}")
    print(f"Default Mode: {mode_manager.get_mode().value.upper()}")
    print(f"Mode Description: {mode_manager.get_mode_description()}")
    print("="*50 + "\n")
    
    # Start Socket Mode handler
    handler = AsyncSocketModeHandler(app, os.getenv("SLACK_APP_TOKEN"))
    await handler.start_async()


if __name__ == "__main__":
    asyncio.run(main())
