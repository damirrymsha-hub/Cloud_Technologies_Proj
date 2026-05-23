"""
Root-level pytest configuration.

Adds the project root to sys.path so that test files can import project
modules (data, features, models, api) regardless of where pytest is invoked from.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(__file__))
