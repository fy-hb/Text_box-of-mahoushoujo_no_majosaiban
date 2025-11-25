import sys
import os
import unittest

# Add src to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

class TestImports(unittest.TestCase):
    def test_imports(self):
        try:
            from src.utils.platform_utils import PlatformUtils
            from src.core.image_processor import ImageProcessor
            from src.config import CHARACTERS
            from src.main import Application
        except ImportError as e:
            self.fail(f"Import failed: {e}")

    def test_resource_path(self):
        from src.utils.resource_utils import get_resource_path
        path = get_resource_path("resources")
        self.assertTrue(os.path.exists(path), f"Resources path not found: {path}")

if __name__ == '__main__':
    unittest.main()
