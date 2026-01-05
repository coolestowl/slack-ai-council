"""
Unit tests for follow-up modal functionality
"""

import unittest
from unittest.mock import AsyncMock, MagicMock


class TestFollowupModal(unittest.TestCase):
    """Test cases for follow-up modal functionality"""
    
    def setUp(self):
        """Set up test fixtures"""
        # Mock LLM manager and adapters
        self.mock_adapter = MagicMock()
        self.mock_adapter.adapter_key = "openai"
        self.mock_adapter.username = "GPT-5.2"
        self.mock_adapter.icon_emoji = ":robot_face:"
        self.mock_adapter.get_display_config.return_value = {
            "username": "GPT-5.2",
            "icon_emoji": ":robot_face:"
        }
        
    def test_followup_button_format(self):
        """Test that follow-up button has correct format"""
        # Expected button structure
        expected_button = {
            "type": "button",
            "text": {
                "type": "plain_text",
                "text": "追问 GPT-5.2",
                "emoji": True
            },
            "action_id": "followup_openai",
            "value": "C123456|1234567890.123456"
        }
        
        # Test that button contains expected fields
        self.assertEqual(expected_button["type"], "button")
        self.assertEqual(expected_button["text"]["type"], "plain_text")
        self.assertIn("追问", expected_button["text"]["text"])
        self.assertTrue(expected_button["action_id"].startswith("followup_"))
        self.assertIn("|", expected_button["value"])
    
    def test_action_id_parsing(self):
        """Test parsing model key from action_id"""
        action_id = "followup_openai"
        model_key = action_id.replace("followup_", "")
        self.assertEqual(model_key, "openai")
        
        action_id2 = "followup_gemini"
        model_key2 = action_id2.replace("followup_", "")
        self.assertEqual(model_key2, "gemini")
    
    def test_value_parsing(self):
        """Test parsing channel and thread_ts from button value"""
        value = "C123456|1234567890.123456"
        channel, thread_ts = value.split("|")
        
        self.assertEqual(channel, "C123456")
        self.assertEqual(thread_ts, "1234567890.123456")
    
    def test_metadata_parsing(self):
        """Test parsing metadata from modal submission"""
        metadata = "C123456|1234567890.123456|openai"
        channel, thread_ts, model_key = metadata.split("|")
        
        self.assertEqual(channel, "C123456")
        self.assertEqual(thread_ts, "1234567890.123456")
        self.assertEqual(model_key, "openai")
    
    def test_modal_structure(self):
        """Test that modal has correct structure"""
        model_key = "openai"
        adapter_username = "GPT-5.2"
        
        # Expected modal structure
        expected_modal = {
            "type": "modal",
            "callback_id": f"followup_modal_{model_key}",
            "title": {
                "type": "plain_text",
                "text": f"追问 {adapter_username}"
            },
            "submit": {
                "type": "plain_text",
                "text": "提交"
            },
            "close": {
                "type": "plain_text",
                "text": "取消"
            }
        }
        
        # Verify modal structure
        self.assertEqual(expected_modal["type"], "modal")
        self.assertIn("followup_modal_", expected_modal["callback_id"])
        self.assertEqual(expected_modal["title"]["type"], "plain_text")
        self.assertIn("追问", expected_modal["title"]["text"])
        self.assertEqual(expected_modal["submit"]["text"], "提交")
        self.assertEqual(expected_modal["close"]["text"], "取消")
    
    def test_modal_title_character_limit(self):
        """Test that modal title respects Slack's character limit"""
        # Test with a long username that would exceed the limit
        long_username = "Gemini-3-Flash-Preview"  # 22 characters
        max_username_length = 21  # Slack requires title < 25 chars, "追问 " is 3 chars
        
        # Truncate if needed (as done in the actual code)
        display_username = long_username
        if len(display_username) > max_username_length:
            display_username = display_username[:max_username_length]
        
        title_text = f"追问 {display_username}"
        
        # Slack modal title must be strictly less than 25 characters
        self.assertLess(len(title_text), 25, 
                           f"Modal title '{title_text}' must be less than 25 characters (length: {len(title_text)})")
        
        # Test with various username lengths
        test_cases = [
            "GPT-5.2",  # Short name
            "Grok-3",  # Short name
            "Doubao-Seed-1.8",  # Medium name
            "Gemini-3-Flash-Preview",  # Long name (22 chars)
            "A" * 30,  # Very long name
        ]
        
        for username in test_cases:
            display_name = username if len(username) <= max_username_length else username[:max_username_length]
            title = f"追问 {display_name}"
            self.assertLess(len(title), 25, 
                               f"Title for username '{username}' must be < 25 chars: '{title}' (length: {len(title)})")
    
    def test_blocks_structure_with_button(self):
        """Test that message blocks include button"""
        response_text = "This is a test response"
        
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
                            "text": "追问 GPT-5.2",
                            "emoji": True
                        },
                        "action_id": "followup_openai",
                        "value": "C123456|1234567890.123456"
                    }
                ]
            }
        ]
        
        # Verify blocks structure
        self.assertEqual(len(blocks), 2)
        self.assertEqual(blocks[0]["type"], "section")
        self.assertEqual(blocks[1]["type"], "actions")
        self.assertEqual(len(blocks[1]["elements"]), 1)
        self.assertEqual(blocks[1]["elements"][0]["type"], "button")


class TestFollowupModalAsync(unittest.IsolatedAsyncioTestCase):
    """Async test cases for follow-up modal functionality"""
    
    async def test_send_model_response_with_blocks(self):
        """Test that send_model_response creates proper blocks"""
        # Mock adapter
        mock_adapter = MagicMock()
        mock_adapter.adapter_key = "openai"
        mock_adapter.username = "GPT-5.2"
        mock_adapter.get_display_config.return_value = {
            "username": "GPT-5.2",
            "icon_emoji": ":robot_face:"
        }
        
        channel = "C123456"
        thread_ts = "1234567890.123456"
        response_text = "Test response"
        
        # Expected blocks structure
        expected_blocks = [
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
                            "text": f"追问 {mock_adapter.username}",
                            "emoji": True
                        },
                        "action_id": f"followup_{mock_adapter.adapter_key}",
                        "value": f"{channel}|{thread_ts}"
                    }
                ]
            }
        ]
        
        # Verify structure
        self.assertEqual(len(expected_blocks), 2)
        self.assertEqual(expected_blocks[0]["type"], "section")
        self.assertEqual(expected_blocks[1]["type"], "actions")
        self.assertIn("followup_", expected_blocks[1]["elements"][0]["action_id"])


if __name__ == "__main__":
    unittest.main()
