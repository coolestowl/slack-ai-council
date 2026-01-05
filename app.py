"""
Slack AI Council Bot - Main Application

This is the main application file that initializes the Slack bot and handles
incoming messages. It coordinates between multiple AI models to provide
multi-perspective responses in Slack threads.
"""

import os
import re
import asyncio
import random
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

# Global cache for event deduplication
processed_events = set()



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
            limit=100,
            include_all_metadata=True
        )
        return result.get("messages", [])
    except Exception as e:
        print(f"Error fetching thread messages: {e}")
        return []


def split_text(text: str, limit: int = 2500) -> List[str]:
    """
    Split text into chunks of maximum limit characters.
    Tries to split at newlines or spaces to avoid breaking words.
    """
    chunks = []
    while len(text) > limit:
        # Find a suitable split point (newline or space)
        # Look for the last newline within the limit
        split_index = text.rfind('\n', 0, limit)
        
        if split_index == -1:
            # If no newline, look for the last space
            split_index = text.rfind(' ', 0, limit)
        
        if split_index == -1:
            # No suitable split point, force split at limit
            split_index = limit
            
        chunks.append(text[:split_index])
        # Remove the split character (newline or space) if it was used
        if split_index < len(text) and text[split_index] in ['\n', ' ']:
            text = text[split_index+1:]
        else:
            text = text[split_index:]
        
    if text:
        chunks.append(text)
    return chunks


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
        
        # Split text if it's too long for a single block
        chunks = split_text(response_text)
        
        for i, chunk in enumerate(chunks):
            is_last = (i == len(chunks) - 1)
            
            # Create blocks with response text
            blocks = [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": chunk
                    }
                }
            ]
            
            # Add follow-up button only to the last chunk
            if is_last:
                blocks.append({
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
                })
            
            # Add model information to metadata for filtering
            metadata = {
                "event_type": "ai_response",
                "event_payload": {
                    "model_key": adapter.adapter_key,
                    "model_username": adapter.username
                }
            }
            
            await app.client.chat_postMessage(
                channel=channel,
                thread_ts=thread_ts,
                text=chunk,  # Fallback text for notifications
                blocks=blocks,
                username=display_config["username"],
                icon_emoji=display_config["icon_emoji"],
                metadata=metadata
            )
    except Exception as e:
        print(f"Error sending message from {adapter.username}: {e}")


async def process_model_response(
    adapter: LLMAdapter,
    channel: str,
    thread_ts: str,
    thread_messages: List[Dict[str, Any]],
    mode: str,
    role: str = None
):
    """
    Process and send response from a single AI model
    
    Args:
        adapter: LLM adapter to use
        channel: Channel ID
        thread_ts: Thread timestamp
        thread_messages: List of thread messages
        mode: Current operation mode
        role: Optional role for debate mode
    """
    try:
        # Build prompt with filtered context
        system_prompt = create_default_system_prompt(adapter.username, mode, role)
        messages = context_filter.build_prompt_with_context(
            thread_messages,
            adapter.username,
            system_prompt,
            mode
        )
        
        # Log messages being sent to the model
        print(f"\n=== Sending messages to {adapter.username} ===")
        for msg in messages:
            role = msg.get('role', 'unknown')
            content = msg.get('content', '(no content)')
            print(f"[{role}]: {content}")
        print("========================================\n")

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
    thread_messages: List[Dict[str, Any]],
    specific_adapters: List[LLMAdapter] = None
):
    """
    Handle message in Compare mode (concurrent responses)
    
    Args:
        channel: Channel ID
        thread_ts: Thread timestamp
        thread_messages: List of thread messages
        specific_adapters: Optional list of specific adapters to use
    """
    adapters = specific_adapters if specific_adapters else llm_manager.get_all_adapters()
    
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
    thread_messages: List[Dict[str, Any]],
    specific_adapters: List[LLMAdapter] = None
):
    """
    Handle message in Debate mode (sequential responses)
    
    Args:
        channel: Channel ID
        thread_ts: Thread timestamp
        thread_messages: List of thread messages
        specific_adapters: Optional list of specific adapters to use
    """
    adapters = specific_adapters if specific_adapters else llm_manager.get_all_adapters()
    
    if not adapters:
        await app.client.chat_postMessage(
            channel=channel,
            thread_ts=thread_ts,
            text="No AI models are configured. Please check your API keys."
        )
        return

    if len(adapters) < 2:
        await app.client.chat_postMessage(
            channel=channel,
            thread_ts=thread_ts,
            text="Debate mode requires at least 2 AI models."
        )
        return
    
    # Shuffle adapters for random order
    random.shuffle(adapters)
    
    # Limit to 5 models if more are present
    if len(adapters) > 5:
        adapters = adapters[:5]
        
    count = len(adapters)
    debate_plan = []
    
    if count == 2:
        # A(Pro), B(Con), A(Judge), B(Judge)
        debate_plan = [
            (adapters[0], "Pro"),
            (adapters[1], "Con"),
            (adapters[0], "Judge"),
            (adapters[1], "Judge")
        ]
    elif count == 3:
        # A(Pro), B(Con), C(Judge)
        debate_plan = [
            (adapters[0], "Pro"),
            (adapters[1], "Con"),
            (adapters[2], "Judge")
        ]
    elif count == 4:
        # A(Pro), B(Con), C(Judge), D(Judge)
        debate_plan = [
            (adapters[0], "Pro"),
            (adapters[1], "Con"),
            (adapters[2], "Judge"),
            (adapters[3], "Judge")
        ]
    elif count == 5:
        # A(Pro), B(Pro), C(Con), D(Con), E(Judge)
        debate_plan = [
            (adapters[0], "Pro"),
            (adapters[1], "Pro"),
            (adapters[2], "Con"),
            (adapters[3], "Con"),
            (adapters[4], "Judge")
        ]
    
    # Process models sequentially according to plan
    for adapter, role in debate_plan:
        # Fetch updated thread messages before each response
        updated_messages = await fetch_thread_messages(channel, thread_ts)
        
        await process_model_response(
            adapter,
            channel,
            thread_ts,
            updated_messages,
            "debate",
            role
        )





async def handle_thread_reply(
    channel: str,
    thread_ts: str,
    thread_messages: List[Dict[str, Any]],
    models_in_thread: set,
    mode: str
):
    """
    Handle reply in existing thread by forwarding to models that participated
    
    Args:
        channel: Channel ID
        thread_ts: Thread timestamp
        thread_messages: List of thread messages
        models_in_thread: Set of model keys that have participated in thread
        mode: Operation mode ("compare" or "debate")
    """
    # Get adapters for models that have participated in the thread
    adapters = []
    for model_key in models_in_thread:
        try:
            adapter = llm_manager.get_adapter(model_key)
            adapters.append(adapter)
        except KeyError:
            print(f"Warning: Model {model_key} not found in available adapters")
    
    if not adapters:
        await app.client.chat_postMessage(
            channel=channel,
            thread_ts=thread_ts,
            text="No AI models are available to respond."
        )
        return
    
    # Process based on mode
    if mode == "compare":
        # Process all participating models concurrently
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
    elif mode == "debate":
        # Use the standardized debate handler
        await handle_debate_mode(
            channel,
            thread_ts,
            thread_messages,
            specific_adapters=adapters
        )


async def handle_request_by_mode(
    request_mode: str, 
    channel: str, 
    thread_ts: str, 
    thread_messages: List[Dict[str, Any]],
    specific_adapters: List[LLMAdapter] = None
):
    """
    Handle request based on the specified mode
    
    Args:
        request_mode: Mode to use ("compare" or "debate")
        channel: Channel ID
        thread_ts: Thread timestamp
        thread_messages: List of thread messages
        specific_adapters: Optional list of specific adapters to use
    """
    if request_mode == "compare":
        await handle_compare_mode(channel, thread_ts, thread_messages, specific_adapters)
    elif request_mode == "debate":
        await handle_debate_mode(channel, thread_ts, thread_messages, specific_adapters)


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
            # Post the follow-up question to the thread (for visibility)
            # Include the model name to show which model is being asked
            await client.chat_postMessage(
                channel=channel,
                thread_ts=thread_ts,
                text=f"<@{user_id}> 追问 {adapter.username}: {question}",
                metadata={
                    "event_type": "slack_ai_council_echo",
                    "event_payload": {
                        "is_user_question": True,
                        "user_id": user_id,
                        "question": question,
                        "target_model_key": model_key
                    }
                }
            )
        except KeyError:
            # Post the question without model name if adapter lookup fails
            await client.chat_postMessage(
                channel=channel,
                thread_ts=thread_ts,
                text=f"<@{user_id}> 追问: {question}",
                metadata={
                    "event_type": "slack_ai_council_echo",
                    "event_payload": {
                        "is_user_question": True,
                        "user_id": user_id,
                        "question": question
                    }
                }
            )
            # Handle invalid or unknown model keys with a clear message
            await client.chat_postMessage(
                channel=channel,
                thread_ts=thread_ts,
                text=f"无法找到指定的模型（model_key='{model_key}'）。请联系管理员或重试选择模型。"
            )
            return
        
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


def extract_target_model(text: str) -> tuple[str, List[str]]:
    """
    Extract target models from text if specified (e.g., "model=GPT-4o" or "model=Grok,Gemini")
    
    Args:
        text: Message text
        
    Returns:
        Tuple of (cleaned_text, target_model_usernames)
        target_model_usernames is empty list if not specified
    """
    target_models = []
    cleaned_text = text
    
    # Find all occurrences of model=...
    # We use a while loop to find and remove them one by one
    while True:
        match = re.search(r'model=([^\s]+)', cleaned_text)
        if not match:
            break
            
        models_str = match.group(1)
        # Split by comma for cases like model=Grok,Gemini
        found_models = [m.strip() for m in models_str.split(',') if m.strip()]
        target_models.extend(found_models)
        
        # Remove the matched part from text
        cleaned_text = cleaned_text.replace(match.group(0), "", 1).strip()
        
    return cleaned_text, target_models


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
        event_ts = event["ts"]
        
        # Deduplication check
        event_key = f"{channel}:{event_ts}"
        if event_key in processed_events:
            print(f"Skipping duplicate event: {event_key}")
            return
        
        processed_events.add(event_key)
        # Simple cleanup to prevent memory leak
        if len(processed_events) > 1000:
            processed_events.pop()
            
        thread_ts = event.get("thread_ts")
        text = event.get("text", "")
        
        # Remove bot mention from text for parsing
        # Slack mentions look like "<@U12345> message text"
        text_without_mention = re.sub(r'<@[A-Z0-9]+>\s*', '', text, count=1).strip()
        
        # Extract target model if specified
        text_without_mention, target_model_usernames = extract_target_model(text_without_mention)
        
        # Determine which mode to use for this request (compare by default)
        # Also cleans the mode command from the text
        text_without_mention, request_mode = ModeCommand.extract_mode(text_without_mention)
        
        # Check if we have specific target models
        target_adapters = []
        if target_model_usernames:
            username_mapping = llm_manager.get_username_mapping()
            
            for target_model_username in target_model_usernames:
                # Try exact match first
                adapter_key = username_mapping.get(target_model_username)
                
                if not adapter_key:
                    # Try case-insensitive match
                    target_lower = target_model_username.lower()
                    for username, key in username_mapping.items():
                        if username.lower() == target_lower:
                            adapter_key = key
                            break
                
                if adapter_key:
                    target_adapters.append(llm_manager.get_adapter(adapter_key))
                else:
                    # If specified model not found, warn user
                    await say(
                        text=f"找不到指定的模型 '{target_model_username}'。可用模型: {', '.join(username_mapping.keys())}",
                        thread_ts=thread_ts or event_ts
                    )
                    return

        # Check if this is a new channel message or a thread reply
        if thread_ts is None:
            # This is a new message in the channel, start a new conversation
            print(f"New channel message, starting new conversation in thread {event_ts}")
            thread_ts = event_ts
            thread_messages = await fetch_thread_messages(channel, thread_ts)
            
            if target_adapters:
                # Handle with only the specified models
                await handle_request_by_mode(request_mode, channel, thread_ts, thread_messages, target_adapters)
            else:
                # Handle with all models
                await handle_request_by_mode(request_mode, channel, thread_ts, thread_messages)
        else:
            # This is a reply in an existing thread
            print(f"Reply in existing thread {thread_ts}, filtering by models")
            thread_messages = await fetch_thread_messages(channel, thread_ts)
            
            if target_adapters:
                # User explicitly requested models in the thread
                await handle_request_by_mode(request_mode, channel, thread_ts, thread_messages, target_adapters)
            else:
                # Get models that have already participated in this thread
                models_in_thread = context_filter.get_models_in_thread(thread_messages)
                print(f"Models in thread: {models_in_thread}")
                
                if not models_in_thread:
                    # No AI models have responded yet, treat as new conversation
                    print("No models found in thread, starting new conversation")
                    await handle_request_by_mode(request_mode, channel, thread_ts, thread_messages)
                else:
                    # Filter and forward to only the models that have participated
                    await handle_thread_reply(
                        channel,
                        thread_ts,
                        thread_messages,
                        models_in_thread,
                        request_mode
                    )
    
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
