"""
This __init__.py file is kept in the root tests directory while other __init__.py files
in the test structure are removed for simplicity.

Reasons for keeping this file:
1. It ensures pytest recognizes the entire tests/ directory as a package
2. It helps with consistent import behavior across different environments
3. It prevents certain edge cases with test discovery

Since Python 3.3+, other directories can function as namespace packages without
requiring __init__.py files (PEP 420), so we can safely remove them from the
test subdirectories to reduce clutter while maintaining functionality.
"""
