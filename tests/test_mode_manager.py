"""
Unit tests for Mode Manager module
"""

import unittest
from mode_manager import ModeManager, OperationMode, ModeCommand


class TestModeManager(unittest.TestCase):
    """Test cases for ModeManager class"""
    
    def test_default_mode(self):
        """Test default mode initialization"""
        manager = ModeManager()
        self.assertEqual(manager.get_mode(), OperationMode.COMPARE)
    
    def test_custom_default_mode(self):
        """Test custom default mode"""
        manager = ModeManager(default_mode="debate")
        self.assertEqual(manager.get_mode(), OperationMode.DEBATE)
    
    def test_set_mode_compare(self):
        """Test setting compare mode"""
        manager = ModeManager()
        result = manager.set_mode("compare")
        
        self.assertTrue(result)
        self.assertTrue(manager.is_compare_mode())
        self.assertFalse(manager.is_debate_mode())
    
    def test_set_mode_debate(self):
        """Test setting debate mode"""
        manager = ModeManager()
        result = manager.set_mode("debate")
        
        self.assertTrue(result)
        self.assertTrue(manager.is_debate_mode())
        self.assertFalse(manager.is_compare_mode())
    
    def test_invalid_mode(self):
        """Test handling of invalid mode"""
        manager = ModeManager(default_mode="invalid")
        # Should default to COMPARE
        self.assertEqual(manager.get_mode(), OperationMode.COMPARE)
    
    def test_get_mode_description(self):
        """Test mode description"""
        manager = ModeManager()
        description = manager.get_mode_description()
        
        self.assertIn("Compare", description)
        self.assertIsInstance(description, str)
    
    def test_should_filter_other_models(self):
        """Test filtering logic based on mode"""
        manager = ModeManager()
        
        # Compare mode should filter
        manager.set_mode("compare")
        self.assertTrue(manager.should_filter_other_models())
        
        # Debate mode should not filter
        manager.set_mode("debate")
        self.assertFalse(manager.should_filter_other_models())
    
    def test_get_execution_strategy(self):
        """Test execution strategy based on mode"""
        manager = ModeManager()
        
        manager.set_mode("compare")
        self.assertEqual(manager.get_execution_strategy(), "concurrent")
        
        manager.set_mode("debate")
        self.assertEqual(manager.get_execution_strategy(), "sequential")


class TestModeCommand(unittest.TestCase):
    """Test cases for ModeCommand class"""
    
    def test_parse_set_mode_compare(self):
        """Test parsing set mode to compare command"""
        result = ModeCommand.parse_command("/mode compare")
        
        self.assertEqual(result["command"], "set_mode")
        self.assertEqual(result["mode"], "compare")
    
    def test_parse_set_mode_debate(self):
        """Test parsing set mode to debate command"""
        result = ModeCommand.parse_command("/mode debate")
        
        self.assertEqual(result["command"], "set_mode")
        self.assertEqual(result["mode"], "debate")
    
    def test_parse_get_mode_status(self):
        """Test parsing get mode status command"""
        result = ModeCommand.parse_command("/mode status")
        
        self.assertEqual(result["command"], "get_mode")
    
    def test_parse_invalid_command(self):
        """Test parsing invalid command"""
        result = ModeCommand.parse_command("hello world")
        
        self.assertEqual(result, {})
    
    def test_parse_invalid_mode(self):
        """Test parsing invalid mode"""
        result = ModeCommand.parse_command("/mode invalid")
        
        self.assertEqual(result, {})
    
    def test_is_mode_command(self):
        """Test mode command detection"""
        self.assertTrue(ModeCommand.is_mode_command("/mode compare"))
        self.assertTrue(ModeCommand.is_mode_command("/mode status"))
        self.assertFalse(ModeCommand.is_mode_command("hello"))
        self.assertFalse(ModeCommand.is_mode_command("/help"))
    
    def test_case_insensitive_parsing(self):
        """Test case insensitive command parsing"""
        result1 = ModeCommand.parse_command("/MODE COMPARE")
        result2 = ModeCommand.parse_command("/mode Compare")
        
        self.assertEqual(result1["command"], "set_mode")
        self.assertEqual(result2["command"], "set_mode")


if __name__ == "__main__":
    unittest.main()
