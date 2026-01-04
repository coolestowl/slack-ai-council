"""
Mode Manager - Inline Mode Specification

This module provides utility for parsing inline mode specification:
- Compare Mode: All AI models respond concurrently (default)
- Debate Mode: AI models respond sequentially
"""

import re
from typing import Dict, Any


class ModeCommand:
    """Helper class for parsing inline mode specification"""
    
    @staticmethod
    def extract_inline_mode(text: str) -> Dict[str, Any]:
        """
        Extract inline mode specification from message text
        
        Supports format: "mode=debate your question here" or "mode=compare your question"
        
        Args:
            text: Message text from user
        
        Returns:
            Dictionary with 'mode' and 'question' keys, or empty dict if no inline mode
        """
        # Match "mode=compare" or "mode=debate" at the start of the message (case insensitive)
        # Apply to original text to preserve case in question
        pattern = r'^mode=(compare|debate)\s+(.*)'
        match = re.match(pattern, text.strip(), re.IGNORECASE)
        
        if match:
            mode = match.group(1).lower()  # Normalize mode to lowercase
            question = match.group(2)  # Preserve original case in question
            
            return {
                "mode": mode,
                "question": question
            }
        
        return {}
