"""
Test runner for all unit tests
"""

import unittest
import sys

# Discover and run all tests
if __name__ == "__main__":
    loader = unittest.TestLoader()
    start_dir = 'tests'
    suite = loader.discover(start_dir, pattern='test_*.py')
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Exit with non-zero status if tests failed
    sys.exit(not result.wasSuccessful())
