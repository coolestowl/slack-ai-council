"""
Mode Manager - Compare vs Debate Mode

This module manages the operation mode of the AI Council:
- Compare Mode: All AI models respond concurrently to the user's question
- Debate Mode: AI models respond sequentially, seeing each other's responses
"""

from enum import Enum
from typing import List, Dict, Any


class OperationMode(Enum):
    """Enum for operation modes"""
    COMPARE = "compare"
    DEBATE = "debate"


class ModeManager:
    """Manager for operation modes (Compare vs Debate)"""
    
    def __init__(self, default_mode: str = "compare"):
        """
        Initialize mode manager
        
        Args:
            default_mode: Default operation mode ("compare" or "debate")
        """
        self.default_mode = self._parse_mode(default_mode)
        self.current_mode = self.default_mode
    
    def _parse_mode(self, mode_str: str) -> OperationMode:
        """
        Parse mode string to OperationMode enum
        
        Args:
            mode_str: Mode string ("compare" or "debate")
        
        Returns:
            OperationMode enum value
        """
        mode_str = mode_str.lower()
        if mode_str == "compare":
            return OperationMode.COMPARE
        elif mode_str == "debate":
            return OperationMode.DEBATE
        else:
            print(f"Unknown mode '{mode_str}', defaulting to COMPARE")
            return OperationMode.COMPARE
    
    def set_mode(self, mode: str) -> bool:
        """
        Set the current operation mode
        
        Args:
            mode: Mode string ("compare" or "debate")
        
        Returns:
            True if mode was set successfully, False otherwise
        """
        try:
            self.current_mode = self._parse_mode(mode)
            return True
        except Exception:
            return False
    
    def get_mode(self) -> OperationMode:
        """Get current operation mode"""
        return self.current_mode
    
    def is_compare_mode(self) -> bool:
        """Check if current mode is Compare"""
        return self.current_mode == OperationMode.COMPARE
    
    def is_debate_mode(self) -> bool:
        """Check if current mode is Debate"""
        return self.current_mode == OperationMode.DEBATE
    
    def get_mode_description(self) -> str:
        """Get description of current mode"""
        if self.is_compare_mode():
            return "Compare Mode: All AI models respond concurrently"
        elif self.is_debate_mode():
            return "Debate Mode: AI models respond sequentially"
        return "Unknown mode"
    
    def should_filter_other_models(self) -> bool:
        """
        Determine if other AI models' responses should be filtered
        
        Returns:
            True for Compare mode (filter others), False for Debate mode (include others)
        """
        return self.is_compare_mode()
    
    def get_execution_strategy(self) -> str:
        """
        Get execution strategy based on mode
        
        Returns:
            "concurrent" for Compare mode, "sequential" for Debate mode
        """
        if self.is_compare_mode():
            return "concurrent"
        elif self.is_debate_mode():
            return "sequential"
        return "concurrent"


class ModeCommand:
    """Helper class for parsing mode-related commands"""
    
    @staticmethod
    def parse_command(text: str) -> Dict[str, Any]:
        """
        Parse user command for mode changes
        
        Args:
            text: Message text from user
        
        Returns:
            Dictionary with command info or empty dict if no command
        """
        text = text.lower().strip()
        
        # Check for mode change commands
        if text.startswith("/mode"):
            parts = text.split()
            if len(parts) >= 2:
                mode = parts[1]
                if mode in ["compare", "debate"]:
                    return {
                        "command": "set_mode",
                        "mode": mode
                    }
                elif mode == "status":
                    return {
                        "command": "get_mode"
                    }
        
        return {}
    
    @staticmethod
    def is_mode_command(text: str) -> bool:
        """Check if text is a mode command"""
        return text.lower().strip().startswith("/mode")
