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
        'XAI_API_KEY': 'test-xai-key'
    })
    def test_manager_initialization_with_keys(self):
        """Test manager initialization when all API keys are present"""
        from llm_manager import LLMManager
        
        manager = LLMManager()
        
        # Should have all three adapters
        self.assertIn("openai", manager.get_adapter_names())
        self.assertIn("gemini", manager.get_adapter_names())
        self.assertIn("grok", manager.get_adapter_names())
    
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
        self.assertEqual(adapter.username, "GPT-4o")
    
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
        self.assertEqual(config["username"], "GPT-4o")


class TestAdapterStructure(unittest.TestCase):
    """Test adapter structure and interface"""
    
    @patch.dict(os.environ, {'OPENAI_API_KEY': 'test-key'})
    def test_openai_adapter_structure(self):
        """Test OpenAI adapter structure"""
        from llm_manager import OpenAIAdapter
        
        adapter = OpenAIAdapter()
        
        self.assertEqual(adapter.model_name, "gpt-4o")
        self.assertEqual(adapter.username, "GPT-4o")
        self.assertEqual(adapter.icon_emoji, ":robot_face:")
    
    @patch.dict(os.environ, {'GOOGLE_API_KEY': 'test-key'})
    def test_gemini_adapter_structure(self):
        """Test Gemini adapter structure"""
        from llm_manager import GeminiAdapter
        
        adapter = GeminiAdapter()
        
        self.assertEqual(adapter.model_name, "gemini-1.5-pro")
        self.assertEqual(adapter.username, "Gemini-1.5-Pro")
        self.assertEqual(adapter.icon_emoji, ":gem:")
    
    @patch.dict(os.environ, {'XAI_API_KEY': 'test-key'})
    def test_grok_adapter_structure(self):
        """Test Grok adapter structure"""
        from llm_manager import GrokAdapter
        
        adapter = GrokAdapter()
        
        self.assertEqual(adapter.model_name, "grok-beta")
        self.assertEqual(adapter.username, "Grok")
        self.assertEqual(adapter.icon_emoji, ":lightning:")
    
    def test_adapter_missing_key(self):
        """Test adapter initialization without API key"""
        from llm_manager import OpenAIAdapter
        
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(ValueError):
                OpenAIAdapter()


if __name__ == "__main__":
    unittest.main()
