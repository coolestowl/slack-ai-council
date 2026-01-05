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
    def extract_mode(text: str) -> tuple[str, str]:
        """
        Extract mode from text and return cleaned text.
        
        Args:
            text: Message text
            
        Returns:
            Tuple of (cleaned_text, mode)
            mode is "compare" (default) if not specified
        """
        mode = "compare"
        cleaned_text = text
        
        # Match mode=compare or mode=debate anywhere in the text
        match = re.search(r'mode=(compare|debate)', cleaned_text, re.IGNORECASE)
        
        if match:
            mode = match.group(1).lower()
            # Remove the mode specification
            cleaned_text = cleaned_text.replace(match.group(0), "", 1).strip()
            
        return cleaned_text, mode
