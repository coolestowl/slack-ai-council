"""
Context Filter - Message History Management

This module provides functionality to filter message history for AI models,
ensuring each model only sees:
1. User messages
2. Its own previous responses (not responses from other AI models)
"""

import re
from typing import List, Dict, Any, Optional


class ContextFilter:
    """Filter message history for context isolation between AI models"""
    
    # Compiled regex pattern for removing Slack mentions at the beginning of text
    # Matches format: <@USERID> where USERID can contain word characters (letters, digits, underscores)
    # The ^ anchor ensures we only match mentions at the start of the text
    # Note: Slack user IDs are typically uppercase alphanumeric (e.g., U12345, USLACKBOT)
    # but we use \w+ to be slightly more permissive for edge cases
    MENTION_PATTERN = re.compile(r'^<@\w+>\s*')
    
    def __init__(self, bot_user_id: str, llm_manager=None):
        """
        Initialize context filter
        
        Args:
            bot_user_id: The Slack bot's user ID
            llm_manager: Optional LLMManager instance to auto-populate model usernames
        """
        self.bot_user_id = bot_user_id
        # Map of model usernames to identify which model sent which message
        if llm_manager:
            # Auto-populate from LLMManager
            self.model_usernames = llm_manager.get_username_mapping()
        else:
            # Fallback to empty dict if no manager provided
            # This is mainly for backward compatibility and testing
            self.model_usernames = {}
    
    def remove_bot_mention(self, text: str) -> str:
        """
        Remove any user mention from the beginning of message text
        
        Slack mentions look like "<@U12345>" where U12345 is the user ID.
        This method removes any mention from the beginning of the text, which
        is typically the bot's mention when triggered via @mention.
        
        Mentions in the middle or end of the text are preserved.
        
        Args:
            text: Original message text that may contain a mention
        
        Returns:
            Text with leading mention removed
        """
        # Remove mentions (format: <@USERID>) from the beginning of text only
        # The ^ anchor ensures we only match at the start
        cleaned_text = self.MENTION_PATTERN.sub('', text).strip()
        return cleaned_text
    
    def filter_messages_for_model(
        self,
        messages: List[Dict[str, Any]],
        target_model_username: str
    ) -> List[Dict[str, str]]:
        """
        Filter thread messages for a specific model.
        
        Rules:
        - Include all user messages (non-bot messages)
        - Include only the target model's own previous responses
        - Exclude other AI models' responses
        - Remove bot mentions from user messages
        
        Args:
            messages: List of Slack message objects from thread history
            target_model_username: Username of the target model (e.g., "GPT-4o")
        
        Returns:
            List of filtered messages in OpenAI chat format
        """
        filtered_messages = []
        
        # Get target model key from username
        target_model_key = self.model_usernames.get(target_model_username)
        
        for msg in messages:
            # Skip messages without text
            if "text" not in msg:
                continue
            
            text = msg["text"]
            user_id = msg.get("user", "")
            username = msg.get("username", "")
            
            # Check if this is a bot message
            is_bot = msg.get("bot_id") or msg.get("subtype") == "bot_message"
            
            # Check for metadata indicating this is a user question echo
            is_echo_user_question = False
            if "metadata" in msg:
                metadata = msg["metadata"]
                if metadata.get("event_type") == "slack_ai_council_echo":
                    payload = metadata.get("event_payload", {})
                    if payload.get("is_user_question"):
                        is_echo_user_question = True

            if is_echo_user_question:
                # Check if this question is intended for the target model
                payload = msg["metadata"].get("event_payload", {})
                msg_target_model_key = payload.get("target_model_key")
                
                # If target_model_key is present in metadata, it must match the current target model
                # If not present (legacy messages), we might include it or exclude it. 
                # Assuming we want to be strict if the key is present.
                if msg_target_model_key and target_model_key and msg_target_model_key != target_model_key:
                    continue

                # Treat as user message
                # Use the original question from metadata if available, otherwise use text
                content = text
                if "question" in payload:
                    content = payload["question"]
                
                filtered_messages.append({
                    "role": "user",
                    "content": content
                })
            elif is_bot:
                # Only include if it's from the target model
                if username == target_model_username:
                    filtered_messages.append({
                        "role": "assistant",
                        "content": text
                    })
            else:
                # Include all user messages, but remove bot mentions
                cleaned_text = self.remove_bot_mention(text)
                filtered_messages.append({
                    "role": "user",
                    "content": cleaned_text
                })
        
        return filtered_messages
    
    def extract_user_question(self, messages: List[Dict[str, Any]]) -> str:
        """
        Extract the original user question from the thread
        
        Args:
            messages: List of Slack message objects
        
        Returns:
            The first user message text (the original question) with mentions removed
        """
        for msg in messages:
            if "text" in msg and not msg.get("bot_id"):
                return self.remove_bot_mention(msg["text"])
        return ""
    
    def is_bot_message(self, message: Dict[str, Any]) -> bool:
        """
        Check if a message is from a bot
        
        Args:
            message: Slack message object
        
        Returns:
            True if message is from a bot, False otherwise
        """
        return bool(message.get("bot_id") or message.get("subtype") == "bot_message")
    
    def get_model_from_username(self, username: str) -> str:
        """
        Get model identifier from username
        
        Args:
            username: The username from Slack message
        
        Returns:
            Model identifier (e.g., "openai", "gemini", "grok")
        """
        return self.model_usernames.get(username, "unknown")
    
    def get_model_from_metadata(self, message: Dict[str, Any]) -> Optional[str]:
        """
        Extract model identifier from message metadata
        
        Args:
            message: Slack message object
        
        Returns:
            Model identifier (e.g., "openai", "gemini", "grok") or None if not found
        """
        metadata = message.get("metadata", {})
        if metadata.get("event_type") == "ai_response":
            event_payload = metadata.get("event_payload", {})
            return event_payload.get("model_key")
        return None
    
    def get_models_in_thread(self, messages: List[Dict[str, Any]]) -> set:
        """
        Get set of model identifiers that have responded in the thread
        
        Args:
            messages: List of Slack message objects from thread
        
        Returns:
            Set of model identifiers that have responded
        """
        models = set()
        for msg in messages:
            # Try to get model from metadata first (preferred)
            model_key = self.get_model_from_metadata(msg)
            if model_key:
                models.add(model_key)
            # Fallback to username-based detection for backwards compatibility
            elif self.is_bot_message(msg):
                username = msg.get("username", "")
                if username:
                    model_key = self.get_model_from_username(username)
                    if model_key != "unknown":
                        models.add(model_key)
        return models
    
    def build_prompt_with_context(
        self,
        thread_messages: List[Dict[str, Any]],
        target_model_username: str,
        system_prompt: str = None
    ) -> List[Dict[str, str]]:
        """
        Build a complete prompt with system message and filtered context
        
        Args:
            thread_messages: List of Slack message objects from thread
            target_model_username: Username of the target model
            system_prompt: Optional system prompt to prepend
        
        Returns:
            Complete list of messages ready for AI API
        """
        messages = []
        
        # Add system prompt if provided
        if system_prompt:
            messages.append({
                "role": "system",
                "content": system_prompt
            })
        
        # Add filtered messages
        filtered = self.filter_messages_for_model(thread_messages, target_model_username)
        messages.extend(filtered)
        
        return messages


def create_default_system_prompt(model_name: str, mode: str = "compare") -> str:
    """
    Create a default system prompt based on mode
    
    Args:
        model_name: Name of the model
        mode: Operation mode ("compare" or "debate")
    
    Returns:
        System prompt string
    """
    if mode == "compare":
        return (
            f"You are {model_name}, participating in a multi-AI comparison. "
            "Provide your perspective on the user's question. "
            "Be concise, helpful, and show your unique approach to problem-solving.\n\n"
            "IMPORTANT: You are chatting in Slack. Please use Slack-compatible formatting:\n"
            "- Use *bold* for bold (not **bold**)\n"
            "- Use _italics_ for italics (not *italics*)\n"
            "- Use <url|text> for links (not [text](url))\n"
            "- Do not use # for headers, use *bold* instead"
        )
    elif mode == "debate":
        return (
            f"You are {model_name}, participating in an AI debate. "
            "You will see arguments from other AI models. "
            "Respond thoughtfully, point out strengths and weaknesses in arguments, "
            "and build upon or challenge previous points constructively.\n\n"
            "IMPORTANT: You are chatting in Slack. Please use Slack-compatible formatting:\n"
            "- Use *bold* for bold (not **bold**)\n"
            "- Use _italics_ for italics (not *italics*)\n"
            "- Use <url|text> for links (not [text](url))\n"
            "- Do not use # for headers, use *bold* instead"
        )
    else:
        return (
            f"You are {model_name}, a helpful AI assistant.\n\n"
            "IMPORTANT: You are chatting in Slack. Please use Slack-compatible formatting:\n"
            "- Use *bold* for bold (not **bold**)\n"
            "- Use _italics_ for italics (not *italics*)\n"
            "- Use <url|text> for links (not [text](url))\n"
            "- Do not use # for headers, use *bold* instead"
        )
