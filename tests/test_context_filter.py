"""
Unit tests for Context Filter module
"""

import unittest
from unittest.mock import Mock
from context_filter import ContextFilter, create_default_system_prompt


class TestContextFilter(unittest.TestCase):
    """Test cases for ContextFilter class"""
    
    def setUp(self):
        """Set up test fixtures"""
        # Create a mock LLMManager with username mappings
        mock_llm_manager = Mock()
        mock_llm_manager.get_username_mapping.return_value = {
            "GPT-4o": "openai",
            "Gemini-2.0-Flash": "gemini",
            "Grok-2": "grok",
            "Doubao": "doubao"
        }
        self.filter = ContextFilter(bot_user_id="BOT123", llm_manager=mock_llm_manager)
    
    def test_filter_user_messages_only(self):
        """Test filtering when only user messages exist"""
        messages = [
            {"text": "Hello, how are you?", "user": "U123"},
            {"text": "What's the weather?", "user": "U123"}
        ]
        
        result = self.filter.filter_messages_for_model(messages, "GPT-4o")
        
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["role"], "user")
        self.assertEqual(result[0]["content"], "Hello, how are you?")
        self.assertEqual(result[1]["role"], "user")
    
    def test_remove_bot_mention(self):
        """Test that bot mentions are removed from user messages"""
        messages = [
            {"text": "<@U12345> What is AI?", "user": "U123"},
            {"text": "<@BOTID123> Explain quantum computing", "user": "U456"}
        ]
        
        result = self.filter.filter_messages_for_model(messages, "GPT-4o")
        
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["role"], "user")
        self.assertEqual(result[0]["content"], "What is AI?")
        self.assertEqual(result[1]["role"], "user")
        self.assertEqual(result[1]["content"], "Explain quantum computing")
    
    def test_remove_bot_mention_lowercase(self):
        """Test that bot mentions with lowercase IDs are removed"""
        messages = [
            {"text": "<@u12345> What is AI?", "user": "U123"},
            {"text": "<@Uabc123> Explain ML", "user": "U456"}
        ]
        
        result = self.filter.filter_messages_for_model(messages, "GPT-4o")
        
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["role"], "user")
        self.assertEqual(result[0]["content"], "What is AI?")
        self.assertEqual(result[1]["role"], "user")
        self.assertEqual(result[1]["content"], "Explain ML")
    
    def test_remove_bot_mention_with_underscore(self):
        """Test that bot mentions with underscores in IDs are removed"""
        messages = [
            {"text": "<@U_12345> What is AI?", "user": "U123"},
            {"text": "<@Bot_ID_123> Tell me more", "user": "U456"}
        ]
        
        result = self.filter.filter_messages_for_model(messages, "GPT-4o")
        
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["role"], "user")
        self.assertEqual(result[0]["content"], "What is AI?")
        self.assertEqual(result[1]["role"], "user")
        self.assertEqual(result[1]["content"], "Tell me more")
    
    def test_remove_bot_mention_with_mode(self):
        """Test that bot mentions are removed even with inline mode specification"""
        messages = [
            {"text": "<@U12345> mode=debate What is the future of AI?", "user": "U123"}
        ]
        
        result = self.filter.filter_messages_for_model(messages, "GPT-4o")
        
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["role"], "user")
        self.assertEqual(result[0]["content"], "mode=debate What is the future of AI?")
    
    def test_message_without_mention(self):
        """Test that messages without mentions are not affected"""
        messages = [
            {"text": "This is a regular message", "user": "U123"}
        ]
        
        result = self.filter.filter_messages_for_model(messages, "GPT-4o")
        
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["role"], "user")
        self.assertEqual(result[0]["content"], "This is a regular message")
    
    def test_mention_in_middle_preserved(self):
        """Test that mentions in the middle of messages are preserved"""
        messages = [
            {"text": "<@BOT123> Hey, ask <@USER456> about this", "user": "U123"},
            {"text": "This is about <@USER789> not at the start", "user": "U456"}
        ]
        
        result = self.filter.filter_messages_for_model(messages, "GPT-4o")
        
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["role"], "user")
        # Leading mention removed, but middle mention preserved
        self.assertEqual(result[0]["content"], "Hey, ask <@USER456> about this")
        self.assertEqual(result[1]["role"], "user")
        # No leading mention, so text preserved as-is
        self.assertEqual(result[1]["content"], "This is about <@USER789> not at the start")
    
    def test_filter_includes_own_responses(self):
        """Test that model sees its own previous responses"""
        messages = [
            {"text": "What's AI?", "user": "U123"},
            {"text": "AI is artificial intelligence", "bot_id": "B123", "username": "GPT-4o"},
            {"text": "Tell me more", "user": "U123"}
        ]
        
        result = self.filter.filter_messages_for_model(messages, "GPT-4o")
        
        self.assertEqual(len(result), 3)
        self.assertEqual(result[0]["role"], "user")
        self.assertEqual(result[1]["role"], "assistant")
        self.assertEqual(result[1]["content"], "AI is artificial intelligence")
        self.assertEqual(result[2]["role"], "user")
    
    def test_filter_excludes_other_models(self):
        """Test that model doesn't see other models' responses"""
        messages = [
            {"text": "What's AI?", "user": "U123"},
            {"text": "Response from GPT", "bot_id": "B123", "username": "GPT-4o"},
            {"text": "Response from Gemini", "bot_id": "B123", "username": "Gemini-2.0-Flash"},
            {"text": "Follow-up question", "user": "U123"}
        ]
        
        result = self.filter.filter_messages_for_model(messages, "GPT-4o")
        
        # Should include: user question, own response, follow-up question
        # Should exclude: Gemini's response
        self.assertEqual(len(result), 3)
        self.assertEqual(result[0]["role"], "user")
        self.assertEqual(result[1]["role"], "assistant")
        self.assertEqual(result[1]["content"], "Response from GPT")
        self.assertEqual(result[2]["role"], "user")
    
    def test_extract_user_question(self):
        """Test extracting the original user question"""
        messages = [
            {"text": "What's the best programming language?", "user": "U123"},
            {"text": "Python is great", "bot_id": "B123", "username": "GPT-4o"}
        ]
        
        question = self.filter.extract_user_question(messages)
        
        self.assertEqual(question, "What's the best programming language?")
    
    def test_is_bot_message(self):
        """Test bot message detection"""
        bot_msg = {"text": "Hello", "bot_id": "B123"}
        user_msg = {"text": "Hello", "user": "U123"}
        
        self.assertTrue(self.filter.is_bot_message(bot_msg))
        self.assertFalse(self.filter.is_bot_message(user_msg))
    
    def test_get_model_from_username(self):
        """Test model identification from username"""
        self.assertEqual(self.filter.get_model_from_username("GPT-4o"), "openai")
        self.assertEqual(self.filter.get_model_from_username("Gemini-2.0-Flash"), "gemini")
        self.assertEqual(self.filter.get_model_from_username("Grok-2"), "grok")
        self.assertEqual(self.filter.get_model_from_username("Doubao"), "doubao")
        self.assertEqual(self.filter.get_model_from_username("Unknown"), "unknown")
    
    def test_build_prompt_with_context(self):
        """Test building complete prompt with system message"""
        messages = [
            {"text": "Hello AI", "user": "U123"}
        ]
        
        result = self.filter.build_prompt_with_context(
            messages,
            "GPT-4o",
            "You are a helpful assistant"
        )
        
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["role"], "system")
        self.assertEqual(result[0]["content"], "You are a helpful assistant")
        self.assertEqual(result[1]["role"], "user")


class TestSystemPrompt(unittest.TestCase):
    """Test cases for system prompt generation"""
    
    def test_compare_mode_prompt(self):
        """Test system prompt for compare mode"""
        prompt = create_default_system_prompt("GPT-4o", "compare")
        
        self.assertIn("GPT-4o", prompt)
        self.assertIn("comparison", prompt.lower())
    
    def test_debate_mode_prompt(self):
        """Test system prompt for debate mode"""
        prompt = create_default_system_prompt("Gemini", "debate")
        
        self.assertIn("Gemini", prompt)
        self.assertIn("debate", prompt.lower())
    
    def test_unknown_mode_prompt(self):
        """Test system prompt for unknown mode"""
        prompt = create_default_system_prompt("Grok", "unknown")
        
        self.assertIn("Grok", prompt)
        self.assertIn("assistant", prompt.lower())


if __name__ == "__main__":
    unittest.main()
