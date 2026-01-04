"""
Context Filter - Message History Management

This module provides functionality to filter message history for AI models,
ensuring each model only sees:
1. User messages
2. Its own previous responses (not responses from other AI models)
"""

import re
from typing import List, Dict, Any


class ContextFilter:
    """Filter message history for context isolation between AI models"""
    
    # Compiled regex pattern for removing Slack mentions
    # Matches format: <@USERID> where USERID can contain letters, digits, and underscores
    MENTION_PATTERN = re.compile(r'<@\w+>\s*')
    
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
        
        Args:
            text: Original message text that may contain a mention
        
        Returns:
            Text with leading mention removed
        """
        # Remove mentions (format: <@USERID>) from the beginning of text
        # Use count=1 to only remove the first mention
        cleaned_text = self.MENTION_PATTERN.sub('', text, count=1).strip()
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
        
        for msg in messages:
            # Skip messages without text
            if "text" not in msg:
                continue
            
            text = msg["text"]
            user_id = msg.get("user", "")
            username = msg.get("username", "")
            
            # Check if this is a bot message
            is_bot = msg.get("bot_id") or msg.get("subtype") == "bot_message"
            
            if is_bot:
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
            The first user message text (the original question)
        """
        for msg in messages:
            if "text" in msg and not msg.get("bot_id"):
                return msg["text"]
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
            "Be concise, helpful, and show your unique approach to problem-solving."
        )
    elif mode == "debate":
        return (
            f"You are {model_name}, participating in an AI debate. "
            "You will see arguments from other AI models. "
            "Respond thoughtfully, point out strengths and weaknesses in arguments, "
            "and build upon or challenge previous points constructively."
        )
    else:
        return f"You are {model_name}, a helpful AI assistant."
