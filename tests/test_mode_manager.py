"""
Unit tests for Mode Manager module
"""

import unittest
from mode_manager import ModeCommand


class TestModeCommand(unittest.TestCase):
    """Test cases for ModeCommand class"""
    
    def test_extract_inline_mode_debate(self):
        """Test extracting inline debate mode"""
        result = ModeCommand.extract_inline_mode("mode=debate What is AI?")
        
        self.assertEqual(result["mode"], "debate")
        self.assertEqual(result["question"], "What is AI?")
    
    def test_extract_inline_mode_compare(self):
        """Test extracting inline compare mode"""
        result = ModeCommand.extract_inline_mode("mode=compare Explain quantum computing")
        
        self.assertEqual(result["mode"], "compare")
        self.assertEqual(result["question"], "Explain quantum computing")
    
    def test_extract_inline_mode_case_insensitive(self):
        """Test inline mode extraction is case insensitive"""
        result1 = ModeCommand.extract_inline_mode("MODE=DEBATE test question")
        result2 = ModeCommand.extract_inline_mode("Mode=Debate test question")
        
        self.assertEqual(result1["mode"], "debate")
        self.assertEqual(result2["mode"], "debate")
    
    def test_extract_inline_mode_preserves_question_case(self):
        """Test that question text case is preserved"""
        result = ModeCommand.extract_inline_mode("mode=debate What Is AI Technology?")
        
        self.assertEqual(result["question"], "What Is AI Technology?")
    
    def test_extract_inline_mode_no_match(self):
        """Test extracting inline mode when not present"""
        result = ModeCommand.extract_inline_mode("What is AI?")
        
        self.assertEqual(result, {})
    
    def test_extract_inline_mode_invalid_mode(self):
        """Test extracting inline mode with invalid mode"""
        result = ModeCommand.extract_inline_mode("mode=invalid What is AI?")
        
        self.assertEqual(result, {})


if __name__ == "__main__":
    unittest.main()
