import sys
import os

def get_resource_path(relative_path: str) -> str:
    """
    Get absolute path to resource, works for dev and for PyInstaller.
    """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS # type: ignore
    except AttributeError:
        # In dev, resources are in the project root or resources folder
        # We assume this file is in src/utils/
        # So project root is ../../
        # But wait, the user moved resources to `resources/` folder in root.
        # If we are running from source, we should look relative to the script or CWD.
        # Let's assume CWD is project root for now, or find the root.
        base_path = os.path.abspath(".")
    
    return os.path.join(base_path, relative_path)
