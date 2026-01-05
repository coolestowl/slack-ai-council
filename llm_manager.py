"""
LLM Manager - Adapter Pattern for Multiple AI Models

This module provides a unified interface for interacting with different AI models:
- OpenAI (GPT-5.2)
- Google Gemini (3 Flash Preview)
- X.AI (Grok 3)
- ByteDance (Doubao Seed 1.8)
"""

import os
import inspect
import sys
from abc import ABC, abstractmethod
from typing import List, Dict, Any
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class LLMAdapter(ABC):
    """Abstract base class for LLM adapters"""
    
    # Class variable to store the adapter key for auto-registration
    adapter_key: str = None
    
    def __init__(self, model_name: str, username: str, icon_emoji: str):
        """
        Initialize LLM adapter
        
        Args:
            model_name: Name of the model (e.g., "gpt-4o", "gemini-1.5-pro")
            username: Display name for Slack messages
            icon_emoji: Emoji icon for Slack messages
        """
        self.model_name = model_name
        self.username = username
        self.icon_emoji = icon_emoji
    
    @abstractmethod
    async def generate_response(self, messages: List[Dict[str, str]]) -> str:
        """
        Generate a response from the AI model
        
        Args:
            messages: List of message dictionaries with 'role' and 'content'
        
        Returns:
            Generated response text
        """
        pass
    
    def get_display_config(self) -> Dict[str, str]:
        """Get Slack display configuration for this model"""
        return {
            "username": self.username,
            "icon_emoji": self.icon_emoji
        }


class OpenAIAdapter(LLMAdapter):
    """Adapter for OpenAI API"""
    
    adapter_key = "openai"
    
    def __init__(self, model_name: str = None, username: str = None):
        self.api_key = os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY not found in environment variables")
            
        if model_name is None:
            model_name = os.getenv("OPENAI_MODEL", "gpt-5.2")
            
        if username is None:
            username = os.getenv("OPENAI_USERNAME", model_name)
            
        self.prompt_id = os.getenv("OPENAI_PROMPT_ID")
            
        super().__init__(
            model_name=model_name,
            username=username,
            icon_emoji=":robot_face:"
        )
    
    async def generate_response(self, messages: List[Dict[str, str]]) -> str:
        """Generate response using OpenAI API"""
        try:
            from openai import AsyncOpenAI
            client = AsyncOpenAI(api_key=self.api_key)
            
            kwargs = {
                "model": self.model_name,
                "input": messages,
                "text": {
                    "format": {
                        "type": "text"
                    }
                },
                "reasoning": {},
                "max_output_tokens": 2048,
                "store": False,
                "include": [
                    "reasoning.encrypted_content",
                    "web_search_call.action.sources"
                ]
            }
            
            if self.prompt_id:
                kwargs["prompt"] = {"id": self.prompt_id, "version": "1"}
            
            response = await client.responses.create(**kwargs)
            
            target_obj = next(filter(lambda x: x.type == 'message', response.output), None)
            return target_obj.content[0].text
        except Exception as e:
            return f"Error generating response from {self.username}: {str(e)}"


class GeminiAdapter(LLMAdapter):
    """Adapter for Google Gemini API (3 Flash Preview)"""
    
    adapter_key = "gemini"
    
    def __init__(self, model_name: str = None, username: str = None):
        if model_name is None:
            model_name = os.getenv("GEMINI_MODEL", "gemini-3-flash-preview")
            
        if username is None:
            username = os.getenv("GEMINI_USERNAME", "Gemini-3-Flash-Preview")
            
        super().__init__(
            model_name=model_name,
            username=username,
            icon_emoji=":gem:"
        )
        self.api_key = os.getenv("GOOGLE_API_KEY")
        if not self.api_key:
            raise ValueError("GOOGLE_API_KEY not found in environment variables")
    
    async def generate_response(self, messages: List[Dict[str, str]]) -> str:
        """Generate response using Google Gemini API"""
        try:
            from google import genai
            
            # Create async client
            client = genai.Client(api_key=self.api_key)
            
            # Convert messages to Gemini format
            prompt = self._convert_messages_to_prompt(messages)
            
            # Generate response using async API
            response = await client.aio.models.generate_content(
                model=self.model_name,
                contents=prompt
            )
            
            return response.text
        except Exception as e:
            return f"Error generating response from {self.username}: {str(e)}"
    
    def _convert_messages_to_prompt(self, messages: List[Dict[str, str]]) -> str:
        """Convert chat messages to a single prompt for Gemini"""
        prompt_parts = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role == "system":
                prompt_parts.append(f"System: {content}")
            elif role == "user":
                prompt_parts.append(f"User: {content}")
            elif role == "assistant":
                prompt_parts.append(f"Assistant: {content}")
        return "\n\n".join(prompt_parts)


class GrokAdapter(LLMAdapter):
    """Adapter for X.AI Grok API (Grok 3)"""
    
    adapter_key = "grok"
    
    def __init__(self, model_name: str = None, username: str = None):
        if model_name is None:
            model_name = os.getenv("GROK_MODEL", "grok-3")
            
        if username is None:
            username = os.getenv("GROK_USERNAME", "Grok-3")
            
        super().__init__(
            model_name=model_name,
            username=username,
            icon_emoji=":lightning:"
        )
        self.api_key = os.getenv("XAI_API_KEY")
        if not self.api_key:
            raise ValueError("XAI_API_KEY not found in environment variables")
    
    async def generate_response(self, messages: List[Dict[str, str]]) -> str:
        """Generate response using X.AI Grok API"""
        try:
            import aiohttp
            
            # X.AI uses OpenAI-compatible API
            url = "https://api.x.ai/v1/chat/completions"
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            payload = {
                "model": self.model_name,
                "messages": messages,
                "temperature": 0.7,
                "max_tokens": 1000
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=headers, json=payload) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data["choices"][0]["message"]["content"]
                    else:
                        error_text = await response.text()
                        return f"Error from {self.username}: HTTP {response.status} - {error_text}"
        except Exception as e:
            return f"Error generating response from {self.username}: {str(e)}"


class DoubaoAdapter(LLMAdapter):
    """Adapter for ByteDance Doubao API (Seed 1.8)"""
    
    adapter_key = "doubao"
    
    def __init__(self, model_name: str = None, username: str = None):
        if model_name is None:
            model_name = os.getenv("DOUBAO_MODEL", "doubao-seed-1-8-251215")
            
        if username is None:
            username = os.getenv("DOUBAO_USERNAME", "Doubao-Seed-1.8")
            
        super().__init__(
            model_name=model_name,
            username=username,
            icon_emoji=":coffee:"
        )
        self.api_key = os.getenv("DOUBAO_API_KEY")
        if not self.api_key:
            raise ValueError("DOUBAO_API_KEY not found in environment variables")
    
    async def generate_response(self, messages: List[Dict[str, str]]) -> str:
        """Generate response using ByteDance Doubao API"""
        try:
            from openai import AsyncOpenAI
            
            # Initialize AsyncOpenAI client for Doubao
            client = AsyncOpenAI(
                base_url="https://ark.cn-beijing.volces.com/api/v3/bots",
                api_key=self.api_key
            )
            
            response = await client.chat.completions.create(
                model=self.model_name,
                messages=messages
            )
            
            content = response.choices[0].message.content
            
            # Check for references if available (optional logging or appending)
            if hasattr(response, "references"):
                print(f"References from {self.username}: {response.references}")
                
            return content
        except Exception as e:
            return f"Error generating response from {self.username}: {str(e)}"


class LLMManager:
    """Manager class to handle multiple LLM adapters"""
    
    def __init__(self):
        """Initialize LLM manager with available adapters"""
        self.adapters: Dict[str, LLMAdapter] = {}
        self._initialize_adapters()
    
    def _initialize_adapters(self):
        """Initialize all available LLM adapters by auto-discovering adapter classes"""
        # Get all classes in the current module that are subclasses of LLMAdapter
        current_module = sys.modules[__name__]
        adapter_classes = []
        seen_keys = {}
        
        for name, obj in inspect.getmembers(current_module, inspect.isclass):
            # Check if it's a subclass of LLMAdapter but not LLMAdapter itself
            if issubclass(obj, LLMAdapter) and obj is not LLMAdapter:
                # Check if it has an adapter_key defined
                if hasattr(obj, 'adapter_key') and obj.adapter_key is not None:
                    # Check for duplicate keys
                    if obj.adapter_key in seen_keys:
                        print(f"⚠ Warning: Duplicate adapter_key '{obj.adapter_key}' found in {name} and {seen_keys[obj.adapter_key]}. Skipping {name}.")
                        continue
                    seen_keys[obj.adapter_key] = name
                    adapter_classes.append((obj.adapter_key, obj))
        
        # Initialize each adapter
        for adapter_key, adapter_class in adapter_classes:
            try:
                self.adapters[adapter_key] = adapter_class()
                print(f"✓ Initialized {adapter_key} adapter")
            except ValueError as e:
                print(f"✗ Skipping {adapter_key} adapter: {e}")
            except Exception as e:
                print(f"✗ Error initializing {adapter_key} adapter: {e}")
    
    def get_adapter(self, model_name: str) -> LLMAdapter:
        """
        Get an LLM adapter by name
        
        Args:
            model_name: Name of the model ("openai", "gemini", "grok")
        
        Returns:
            LLMAdapter instance
        
        Raises:
            KeyError: If adapter not found
        """
        if model_name not in self.adapters:
            raise KeyError(f"LLM adapter '{model_name}' not found")
        return self.adapters[model_name]
    
    def get_all_adapters(self) -> List[LLMAdapter]:
        """Get all initialized adapters"""
        return list(self.adapters.values())
    
    def get_adapter_names(self) -> List[str]:
        """Get names of all initialized adapters"""
        return list(self.adapters.keys())
    
    def get_username_mapping(self) -> Dict[str, str]:
        """
        Get mapping of model usernames to adapter keys
        
        Returns:
            Dictionary mapping username (e.g., "GPT-4o") to adapter key (e.g., "openai")
        """
        mapping = {}
        for adapter_key, adapter in self.adapters.items():
            mapping[adapter.username] = adapter_key
        return mapping
    
    async def generate_response(self, model_name: str, messages: List[Dict[str, str]]) -> str:
        """
        Generate response from a specific model
        
        Args:
            model_name: Name of the model to use
            messages: List of message dictionaries
        
        Returns:
            Generated response text
        """
        adapter = self.get_adapter(model_name)
        
        print(f"\n=== Sending messages to {model_name} ===")
        for msg in messages:
            role = msg.get('role', 'unknown')
            content = msg.get('content', '(no content)')
            print(f"[{role}]: {content}")
        print("========================================\n")

        return await adapter.generate_response(messages)
