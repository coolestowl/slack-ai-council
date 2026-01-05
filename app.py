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
from mode_manager import ModeCommand

# Load environment variables
load_dotenv()

# Initialize Slack app
app = AsyncApp(token=os.getenv("SLACK_BOT_TOKEN"))

# Initialize managers
llm_manager = LLMManager()
context_filter = None  # Will be initialized after getting bot user ID


async def initialize_context_filter():
    """Initialize context filter with bot user ID"""
    global context_filter
    try:
        auth_response = await app.client.auth_test()
        bot_user_id = auth_response["user_id"]
        context_filter = ContextFilter(bot_user_id, llm_manager)
        print(f"✓ Context filter initialized with bot user ID: {bot_user_id}")
    except Exception as e:
        print(f"✗ Error initializing context filter: {e}")
        # Create a fallback context filter
        context_filter = ContextFilter("UNKNOWN", llm_manager)


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
    Send a response to Slack with custom username and icon, plus a follow-up button
    
    Args:
        channel: Channel ID
        thread_ts: Thread timestamp
        adapter: LLM adapter with display config
        response_text: Response text to send
    """
    try:
        display_config = adapter.get_display_config()
        
        # Create blocks with response text and follow-up button
        blocks = [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": response_text
                }
            },
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": f"追问 {display_config['username']}",
                            "emoji": True
                        },
                        "action_id": f"followup_{adapter.adapter_key}",
                        "value": f"{channel}|{thread_ts}"
                    }
                ]
            }
        ]
        
        await app.client.chat_postMessage(
            channel=channel,
            thread_ts=thread_ts,
            text=response_text,  # Fallback text for notifications
            blocks=blocks,
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
        Mode string ("compare" or "debate"), defaults to "compare"
    """
    # Check for inline mode specification (e.g., "mode=debate What is AI?")
    inline_mode = ModeCommand.extract_inline_mode(text)
    
    if inline_mode:
        # Use inline specified mode for this request
        mode = inline_mode["mode"]
        print(f"Using inline mode '{mode}' for this request")
        return mode
    else:
        # Default to compare mode
        return "compare"


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


@app.action(re.compile(r"^followup_.*"))
async def handle_followup_button(ack, body, client):
    """
    Handle follow-up button clicks
    
    Args:
        ack: Acknowledge function
        body: Request body
        client: Slack client
    """
    await ack()
    
    try:
        # Extract action information
        action = body["actions"][0]
        action_id = action["action_id"]
        value = action["value"]  # Format: "channel|thread_ts"
        
        # Parse model key from action_id (format: "followup_modelkey")
        model_key = action_id.replace("followup_", "")
        
        # Parse channel and thread_ts from value safely
        parts = value.split("|")
        if len(parts) != 2:
            raise ValueError(f"Unexpected follow-up button value format: {value!r}")
        channel, thread_ts = parts
        
        # Get the adapter for this model
        try:
            adapter = llm_manager.get_adapter(model_key)
        except KeyError:
            # Adapter is missing or configuration changed; inform the user
            await client.chat_postEphemeral(
                channel=channel,
                user=body.get("user", {}).get("id"),
                text="所选模型当前不可用，请重新发送问题或稍后再试。"
            )
            return
        
        # Truncate username for modal title to fit Slack's character limit
        # Slack requires title text to be strictly less than 25 characters
        # "追问 " is 3 characters, leaving 21 for the username
        max_username_length = 21
        display_username = adapter.username
        if len(display_username) > max_username_length:
            display_username = display_username[:max_username_length]
        
        # Open modal for follow-up question
        await client.views_open(
            trigger_id=body["trigger_id"],
            view={
                "type": "modal",
                "callback_id": f"followup_modal_{model_key}",
                "title": {
                    "type": "plain_text",
                    "text": f"追问 {display_username}"
                },
                "submit": {
                    "type": "plain_text",
                    "text": "提交"
                },
                "close": {
                    "type": "plain_text",
                    "text": "取消"
                },
                "blocks": [
                    {
                        "type": "input",
                        "block_id": "question_block",
                        "element": {
                            "type": "plain_text_input",
                            "action_id": "question_input",
                            "multiline": True,
                            "placeholder": {
                                "type": "plain_text",
                                "text": f"输入你想追问 {adapter.username} 的问题..."
                            }
                        },
                        "label": {
                            "type": "plain_text",
                            "text": "你的问题"
                        }
                    },
                    {
                        "type": "context",
                        "elements": [
                            {
                                "type": "mrkdwn",
                                "text": f"此问题将只由 *{adapter.username}* 回答"
                            }
                        ]
                    }
                ],
                "private_metadata": f"{channel}|{thread_ts}|{model_key}"
            }
        )
    except Exception as e:
        print(f"Error in handle_followup_button: {e}")


@app.view(re.compile(r"^followup_modal_.*"))
async def handle_followup_modal_submission(ack, body, client, view):
    """
    Handle follow-up modal submission
    
    Args:
        ack: Acknowledge function
        body: Request body
        client: Slack client
        view: View payload
    """
    # Initialize variables for error handling
    channel = None
    thread_ts = None
    
    try:
        # Extract the question from modal input
        question = view["state"]["values"]["question_block"]["question_input"]["value"]
        
        # Validate question is not empty or whitespace-only
        if not question or not question.strip():
            # Return validation error in modal
            await ack(response_action="errors", errors={
                "question_block": "问题不能为空，请输入有效的问题。"
            })
            return
        
        # Acknowledge successful submission
        await ack()
        
        # Parse metadata (expected format: "channel|thread_ts|model_key")
        metadata = view["private_metadata"]
        parts = metadata.split("|", 2)
        if len(parts) != 3:
            raise ValueError(f"Invalid private_metadata format: {metadata!r}")
        channel, thread_ts, model_key = parts
        
        # Get user info
        user_id = body["user"]["id"]
        
        # Get the adapter for this model
        try:
            adapter = llm_manager.get_adapter(model_key)
        except KeyError:
            # Handle invalid or unknown model keys with a clear message
            await client.chat_postMessage(
                channel=channel,
                thread_ts=thread_ts,
                text=f"无法找到指定的模型（model_key='{model_key}'）。请联系管理员或重试选择模型。"
            )
            return
        
        # Post the follow-up question to the thread (for visibility)
        # Include the model name to show which model is being asked
        await client.chat_postMessage(
            channel=channel,
            thread_ts=thread_ts,
            text=f"<@{user_id}> 追问 {adapter.username}: {question}"
        )
        
        # Fetch thread messages including the new question
        thread_messages = await fetch_thread_messages(channel, thread_ts)
        
        # Process the follow-up with only the specified model
        await process_model_response(
            adapter,
            channel,
            thread_ts,
            thread_messages,
            "compare"  # Use compare mode for context isolation
        )
        
    except Exception as e:
        print(f"Error in handle_followup_modal_submission: {e}")
        # Try to send error message to thread if possible
        if channel is not None and thread_ts is not None:
            try:
                await client.chat_postMessage(
                    channel=channel,
                    thread_ts=thread_ts,
                    text=f"处理追问时出错: {str(e)}"
                )
            except Exception as notify_error:
                # Swallow secondary notification errors to avoid masking the original exception
                print(f"Failed to send error notification to Slack: {notify_error}")


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
        
        # Determine which mode to use for this request (compare by default)
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


async def main():
    """Main function to start the bot"""
    # Initialize context filter
    await initialize_context_filter()
    
    # Print configuration
    print("\n" + "="*50)
    print("Slack AI Council Bot Starting")
    print("="*50)
    print(f"Configured AI Models: {', '.join(llm_manager.get_adapter_names())}")
    print(f"Default Mode: COMPARE")
    print(f"Use 'mode=debate' inline to switch to debate mode for individual requests")
    print("="*50 + "\n")
    
    # Start Socket Mode handler
    handler = AsyncSocketModeHandler(app, os.getenv("SLACK_APP_TOKEN"))
    await handler.start_async()


if __name__ == "__main__":
    asyncio.run(main())
