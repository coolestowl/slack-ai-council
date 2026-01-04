"""
Unit tests for LLM Manager module

Note: These tests focus on the structure and initialization logic.
API integration tests are excluded to avoid requiring actual API keys.
"""

import unittest
from unittest.mock import patch, MagicMock
import os


class TestLLMManager(unittest.TestCase):
    """Test cases for LLMManager class"""
    
    @patch.dict(os.environ, {
        'OPENAI_API_KEY': 'test-openai-key',
        'GOOGLE_API_KEY': 'test-google-key',
        'XAI_API_KEY': 'test-xai-key',
        'DOUBAO_API_KEY': 'test-doubao-key'
    })
    def test_manager_initialization_with_keys(self):
        """Test manager initialization when all API keys are present"""
        from llm_manager import LLMManager
        
        manager = LLMManager()
        
        # Should have all four adapters
        self.assertIn("openai", manager.get_adapter_names())
        self.assertIn("gemini", manager.get_adapter_names())
        self.assertIn("grok", manager.get_adapter_names())
        self.assertIn("doubao", manager.get_adapter_names())
    
    @patch.dict(os.environ, {}, clear=True)
    def test_manager_initialization_without_keys(self):
        """Test manager initialization when no API keys are present"""
        from llm_manager import LLMManager
        
        manager = LLMManager()
        
        # Should have no adapters
        self.assertEqual(len(manager.get_adapter_names()), 0)
    
    @patch.dict(os.environ, {'OPENAI_API_KEY': 'test-key'})
    def test_get_adapter(self):
        """Test getting a specific adapter"""
        from llm_manager import LLMManager
        
        manager = LLMManager()
        adapter = manager.get_adapter("openai")
        
        self.assertIsNotNone(adapter)
        self.assertEqual(adapter.username, "GPT-5.2")
    
    @patch.dict(os.environ, {'OPENAI_API_KEY': 'test-key'})
    def test_get_nonexistent_adapter(self):
        """Test getting an adapter that doesn't exist"""
        from llm_manager import LLMManager
        
        manager = LLMManager()
        
        with self.assertRaises(KeyError):
            manager.get_adapter("nonexistent")
    
    @patch.dict(os.environ, {'OPENAI_API_KEY': 'test-key'})
    def test_get_all_adapters(self):
        """Test getting all adapters"""
        from llm_manager import LLMManager
        
        manager = LLMManager()
        adapters = manager.get_all_adapters()
        
        self.assertIsInstance(adapters, list)
        self.assertEqual(len(adapters), 1)  # Only OpenAI key provided
    
    @patch.dict(os.environ, {'OPENAI_API_KEY': 'test-key'})
    def test_adapter_display_config(self):
        """Test adapter display configuration"""
        from llm_manager import LLMManager
        
        manager = LLMManager()
        adapter = manager.get_adapter("openai")
        config = adapter.get_display_config()
        
        self.assertIn("username", config)
        self.assertIn("icon_emoji", config)
        self.assertEqual(config["username"], "GPT-5.2")


class TestAdapterStructure(unittest.TestCase):
    """Test adapter structure and interface"""
    
    @patch.dict(os.environ, {'OPENAI_API_KEY': 'test-key'})
    def test_openai_adapter_structure(self):
        """Test OpenAI adapter structure"""
        from llm_manager import OpenAIAdapter
        
        adapter = OpenAIAdapter()
        
        self.assertEqual(adapter.model_name, "gpt-5.2")
        self.assertEqual(adapter.username, "GPT-5.2")
        self.assertEqual(adapter.icon_emoji, ":robot_face:")
    
    @patch.dict(os.environ, {'GOOGLE_API_KEY': 'test-key'})
    def test_gemini_adapter_structure(self):
        """Test Gemini adapter structure"""
        from llm_manager import GeminiAdapter
        
        adapter = GeminiAdapter()
        
        self.assertEqual(adapter.model_name, "gemini-2.5-pro")
        self.assertEqual(adapter.username, "Gemini-2.5-Pro")
        self.assertEqual(adapter.icon_emoji, ":gem:")
    
    @patch.dict(os.environ, {'XAI_API_KEY': 'test-key'})
    def test_grok_adapter_structure(self):
        """Test Grok adapter structure"""
        from llm_manager import GrokAdapter
        
        adapter = GrokAdapter()
        
        self.assertEqual(adapter.model_name, "grok-3")
        self.assertEqual(adapter.username, "Grok-3")
        self.assertEqual(adapter.icon_emoji, ":lightning:")
    
    @patch.dict(os.environ, {'DOUBAO_API_KEY': 'test-key'})
    def test_doubao_adapter_structure(self):
        """Test Doubao adapter structure"""
        from llm_manager import DoubaoAdapter
        
        adapter = DoubaoAdapter()
        
        self.assertEqual(adapter.model_name, "doubao-seed-1-8-251215")
        self.assertEqual(adapter.username, "Doubao-Seed-1.8")
        self.assertEqual(adapter.icon_emoji, ":coffee:")
    
    def test_adapter_missing_key(self):
        """Test adapter initialization without API key"""
        from llm_manager import OpenAIAdapter
        
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(ValueError):
                OpenAIAdapter()


class TestOpenAIParameterUpdate(unittest.TestCase):
    """Test OpenAI API parameter compatibility"""
    
    @patch.dict(os.environ, {'OPENAI_API_KEY': 'test-key'})
    def test_openai_uses_max_completion_tokens(self):
        """Test that OpenAI adapter uses max_completion_tokens parameter for GPT-5.2"""
        from llm_manager import OpenAIAdapter
        from unittest.mock import AsyncMock, MagicMock, patch
        import asyncio
        
        async def run_test():
            adapter = OpenAIAdapter()
            
            # Mock the OpenAI client
            mock_response = MagicMock()
            mock_response.choices = [MagicMock()]
            mock_response.choices[0].message.content = "Test response"
            
            mock_client = MagicMock()
            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
            
            # Patch AsyncOpenAI from the openai module, not llm_manager
            with patch('openai.AsyncOpenAI', return_value=mock_client):
                messages = [{"role": "user", "content": "Hello"}]
                result = await adapter.generate_response(messages)
                
                # Verify the correct parameter was used
                mock_client.chat.completions.create.assert_called_once()
                call_kwargs = mock_client.chat.completions.create.call_args[1]
                
                # Assert max_completion_tokens is used, not max_tokens
                self.assertIn('max_completion_tokens', call_kwargs)
                self.assertNotIn('max_tokens', call_kwargs)
                self.assertEqual(call_kwargs['max_completion_tokens'], 1000)
                self.assertEqual(result, "Test response")
        
        # Run the async test
        asyncio.run(run_test())


if __name__ == "__main__":
    unittest.main()
