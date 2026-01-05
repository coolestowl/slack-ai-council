"""
Unit tests for message metadata functionality
"""

import unittest
from unittest.mock import Mock
from context_filter import ContextFilter


class TestMetadataFunctionality(unittest.TestCase):
    """Test cases for message metadata extraction and filtering"""
    
    def setUp(self):
        """Set up test fixtures"""
        # Create a mock LLMManager with username mappings
        mock_llm_manager = Mock()
        mock_llm_manager.get_username_mapping.return_value = {
            "GPT-5.2": "openai",
            "Gemini-3-Flash-Preview": "gemini",
            "Grok-3": "grok",
            "Doubao-Seed-1.8": "doubao"
        }
        self.filter = ContextFilter(bot_user_id="BOT123", llm_manager=mock_llm_manager)
    
    def test_get_model_from_metadata_with_valid_metadata(self):
        """Test extracting model key from message metadata"""
        message = {
            "text": "This is a response",
            "bot_id": "B123",
            "username": "GPT-5.2",
            "metadata": {
                "event_type": "ai_response",
                "event_payload": {
                    "model_key": "openai",
                    "model_username": "GPT-5.2"
                }
            }
        }
        
        model_key = self.filter.get_model_from_metadata(message)
        self.assertEqual(model_key, "openai")
    
    def test_get_model_from_metadata_without_metadata(self):
        """Test that None is returned when message has no metadata"""
        message = {
            "text": "This is a response",
            "bot_id": "B123",
            "username": "GPT-5.2"
        }
        
        model_key = self.filter.get_model_from_metadata(message)
        self.assertIsNone(model_key)
    
    def test_get_model_from_metadata_wrong_event_type(self):
        """Test that None is returned for wrong event type"""
        message = {
            "text": "This is a response",
            "metadata": {
                "event_type": "other_event",
                "event_payload": {
                    "model_key": "openai"
                }
            }
        }
        
        model_key = self.filter.get_model_from_metadata(message)
        self.assertIsNone(model_key)
    
    def test_get_models_in_thread_from_metadata(self):
        """Test extracting models from thread with metadata"""
        messages = [
            {"text": "User question", "user": "U123"},
            {
                "text": "GPT response",
                "bot_id": "B123",
                "username": "GPT-5.2",
                "metadata": {
                    "event_type": "ai_response",
                    "event_payload": {
                        "model_key": "openai",
                        "model_username": "GPT-5.2"
                    }
                }
            },
            {
                "text": "Gemini response",
                "bot_id": "B124",
                "username": "Gemini-3-Flash-Preview",
                "metadata": {
                    "event_type": "ai_response",
                    "event_payload": {
                        "model_key": "gemini",
                        "model_username": "Gemini-3-Flash-Preview"
                    }
                }
            },
            {"text": "Follow-up question", "user": "U123"}
        ]
        
        models = self.filter.get_models_in_thread(messages)
        self.assertEqual(models, {"openai", "gemini"})
    
    def test_get_models_in_thread_from_username_fallback(self):
        """Test extracting models from thread using username fallback"""
        messages = [
            {"text": "User question", "user": "U123"},
            {
                "text": "GPT response",
                "bot_id": "B123",
                "username": "GPT-5.2"
            },
            {
                "text": "Grok response",
                "bot_id": "B125",
                "username": "Grok-3"
            }
        ]
        
        models = self.filter.get_models_in_thread(messages)
        self.assertEqual(models, {"openai", "grok"})
    
    def test_get_models_in_thread_mixed_metadata_and_username(self):
        """Test extracting models from thread with both metadata and username"""
        messages = [
            {"text": "User question", "user": "U123"},
            {
                "text": "GPT response with metadata",
                "bot_id": "B123",
                "username": "GPT-5.2",
                "metadata": {
                    "event_type": "ai_response",
                    "event_payload": {
                        "model_key": "openai",
                        "model_username": "GPT-5.2"
                    }
                }
            },
            {
                "text": "Gemini response without metadata",
                "bot_id": "B124",
                "username": "Gemini-3-Flash-Preview"
            }
        ]
        
        models = self.filter.get_models_in_thread(messages)
        self.assertEqual(models, {"openai", "gemini"})
    
    def test_get_models_in_thread_no_ai_messages(self):
        """Test extracting models from thread with no AI messages"""
        messages = [
            {"text": "User question 1", "user": "U123"},
            {"text": "User question 2", "user": "U456"}
        ]
        
        models = self.filter.get_models_in_thread(messages)
        self.assertEqual(models, set())
    
    def test_get_models_in_thread_unknown_bot(self):
        """Test extracting models from thread with unknown bot"""
        messages = [
            {"text": "User question", "user": "U123"},
            {
                "text": "Unknown bot response",
                "bot_id": "B999",
                "username": "UnknownBot"
            }
        ]
        
        models = self.filter.get_models_in_thread(messages)
        # Unknown bots should not be included
        self.assertEqual(models, set())


if __name__ == "__main__":
    unittest.main()
