import sys
import os
import time
import platform
import io
import subprocess
import tempfile
import logging
import shutil
from typing import Optional, Union
from PIL import Image
import pyperclip

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Platform detection
PLATFORM = platform.system().lower()

# Optional dependencies
HAS_WIN32 = False
HAS_PYNPUT = False

from src.config import OPERATION_TIMEOUT

if PLATFORM == 'windows':
    try:
        import win32clipboard
        import win32gui
        import win32process
        import psutil
        import keyboard as win_keyboard
        HAS_WIN32 = True
    except ImportError:
        logger.warning("Windows specific modules (pywin32, psutil, keyboard) not found.")

if PLATFORM != 'windows':
    try:
        from pynput import keyboard as pynput_keyboard
        from pynput.keyboard import Key, Controller
        HAS_PYNPUT = True
    except ImportError:
        logger.warning("pynput not found. Keyboard simulation may not work.")

class PlatformUtils:
    """
    Cross-platform utilities for clipboard operations, window management, 
    and keyboard simulation.
    """

    @staticmethod
    def get_platform() -> str:
        """Return the current platform ('windows', 'linux', 'darwin')."""
        return PLATFORM

    @staticmethod
    def copy_image_to_clipboard(png_bytes: bytes) -> bool:
        """
        Copy PNG image bytes to the system clipboard.
        """
        if PLATFORM == 'windows' and HAS_WIN32:
            return PlatformUtils._copy_image_windows(png_bytes)
        elif PLATFORM == 'darwin':
            return PlatformUtils._copy_image_macos(png_bytes)
        elif PLATFORM == 'linux':
            return PlatformUtils._copy_image_linux(png_bytes)
        else:
            logger.error(f"Unsupported platform for image copy: {PLATFORM}")
            return False

    @staticmethod
    def _copy_image_windows(png_bytes: bytes) -> bool:
        logger.debug("Start copying image to clipboard (windows)")
        try:
            image = Image.open(io.BytesIO(png_bytes))
            with io.BytesIO() as output:
                image.convert("RGB").save(output, "BMP")
                bmp_data = output.getvalue()[14:]
            
            win32clipboard.OpenClipboard()
            try:
                win32clipboard.EmptyClipboard()
                win32clipboard.SetClipboardData(win32clipboard.CF_DIB, bmp_data)
                return True
            finally:
                win32clipboard.CloseClipboard()
        except Exception as e:
            logger.error(f"Windows clipboard error: {e}")
            return False

    @staticmethod
    def _copy_image_macos(png_bytes: bytes) -> bool:
        logger.debug("Start copying image to clipboard (macOS)")
        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
                tmp.write(png_bytes)
                tmp_path = tmp.name
            
            # Use osascript to set clipboard
            cmd = f"""osascript -e 'set the clipboard to (read (POSIX file "{tmp_path}") as «class PNGf»)'"""
            subprocess.run(cmd, shell=True, check=True, capture_output=True)
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"macOS clipboard error: {e.stderr.decode()}")
            return False
        except Exception as e:
            logger.error(f"macOS clipboard error: {e}")
            return False
        finally:
            if tmp_path and os.path.exists(tmp_path):
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass

    @staticmethod
    def _copy_image_linux(png_bytes: bytes) -> bool:
        logger.debug("Start copying image to clipboard (linux)")
        # Try xclip
        if shutil.which('xclip'):
            logger.debug("trying xclip")
            try:
                process = subprocess.Popen(
                    ['xclip', '-selection', 'clipboard', '-t', 'image/png', '-i'], 
                    stdin=subprocess.PIPE, stderr=subprocess.PIPE
                )
                process.communicate(input=png_bytes, timeout=OPERATION_TIMEOUT)
                if process.returncode == 0:
                    return True
                else:
                    logger.warning("xclip failed to copy image.")
            except Exception as e:
                logger.error(f"xclip error: {e}")

        # Try wl-copy (Wayland)
        if shutil.which('wl-copy'):
            logger.debug("trying wl-copy")
            try:
                process = subprocess.Popen(
                    ['wl-copy', '-t', 'image/png'], 
                    stdin=subprocess.PIPE, stderr=subprocess.PIPE
                )
                process.communicate(input=png_bytes, timeout=OPERATION_TIMEOUT)
                if process.returncode == 0:
                    return True
                else:
                    logger.warning("wl-copy failed to copy image.")
            except Exception as e:
                logger.error(f"wl-copy error: {e}")
        
        logger.error("No suitable clipboard tool found (xclip or wl-copy required on Linux).")
        return False

    @staticmethod
    def get_image_from_clipboard() -> Optional[Image.Image]:
        """
        Retrieve an image from the clipboard. Returns PIL Image or None.
        """
        if PLATFORM == 'windows' and HAS_WIN32:
            return PlatformUtils._get_image_windows()
        elif PLATFORM == 'linux':
            return PlatformUtils._get_image_linux()
        elif PLATFORM == 'darwin':
            return PlatformUtils._get_image_macos()
        
        return None

    @staticmethod
    def _get_image_windows() -> Optional[Image.Image]:
        try:
            win32clipboard.OpenClipboard()
            try:
                if win32clipboard.IsClipboardFormatAvailable(win32clipboard.CF_DIB):
                    data = win32clipboard.GetClipboardData(win32clipboard.CF_DIB)
                    if data:
                        bmp_data = data
                        # Add BMP header
                        header = b'BM' + (len(bmp_data) + 14).to_bytes(4, 'little') + b'\x00\x00\x00\x00\x36\x00\x00\x00'
                        image = Image.open(io.BytesIO(header + bmp_data))
                        return image
            finally:
                win32clipboard.CloseClipboard()
        except Exception as e:
            logger.error(f"Windows get clipboard error: {e}")
        return None

    @staticmethod
    def _get_image_linux() -> Optional[Image.Image]:
        # Try xclip
        if shutil.which('xclip'):
            try:
                # Check if clipboard contains image
                check = subprocess.run(
                    ['xclip', '-selection', 'clipboard', '-t', 'TARGETS', '-o'], 
                    capture_output=True, text=True
                )
                if 'image/png' in check.stdout:
                    process = subprocess.Popen(
                        ['xclip', '-selection', 'clipboard', '-t', 'image/png', '-o'], 
                        stdout=subprocess.PIPE, stderr=subprocess.PIPE
                    )
                    stdout, _ = process.communicate()
                    if process.returncode == 0 and stdout:
                        return Image.open(io.BytesIO(stdout))
            except Exception:
                pass

        # Try wl-paste
        if shutil.which('wl-paste'):
            try:
                # Check types not easily possible with wl-paste without listing? 
                # Just try to paste as png
                process = subprocess.Popen(
                    ['wl-paste', '-t', 'image/png'], 
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE
                )
                stdout, stderr = process.communicate()
                if process.returncode == 0 and stdout:
                    return Image.open(io.BytesIO(stdout))
            except Exception:
                pass
        
        return None

    @staticmethod
    def _get_image_macos() -> Optional[Image.Image]:
        # Use pngpaste if available? Or osascript.
        # osascript is standard.
        try:
            # This is tricky with osascript to get bytes directly to stdout.
            # Alternative: use `pngpaste` if installed, or write to temp file.
            if shutil.which('pngpaste'):
                 process = subprocess.Popen(
                    ['pngpaste', '-'], 
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE
                )
                 stdout, _ = process.communicate()
                 if process.returncode == 0 and stdout:
                     return Image.open(io.BytesIO(stdout))
            
            # Fallback to osascript writing to temp file
            tmp_path = tempfile.mkstemp(suffix='.png')[1]
            cmd = f"""osascript -e 'write (the clipboard as «class PNGf») to (POSIX file "{tmp_path}")'"""
            subprocess.run(cmd, shell=True, check=True, capture_output=True)
            if os.path.exists(tmp_path):
                with open(tmp_path, 'rb') as f:
                    data = f.read()
                os.unlink(tmp_path)
                return Image.open(io.BytesIO(data))
        except Exception:
            pass
        return None

    @staticmethod
    def get_active_window_process_name() -> Optional[str]:
        """
        Get the process name of the currently active window (Windows only).
        """
        if PLATFORM == 'windows' and HAS_WIN32:
            try:
                hwnd = win32gui.GetForegroundWindow()
                _, pid = win32process.GetWindowThreadProcessId(hwnd)
                process = psutil.Process(pid)
                return os.path.basename(process.exe())
            except Exception:
                return None
        return None
    
    @staticmethod
    def simulate_Ctrl_(key: str):
        """Simulate Ctrl+?."""
        logger.debug(f"Start simulate Ctrl+{key}")
        if PLATFORM == 'windows' and HAS_WIN32:
            win_keyboard.send(f'ctrl+{key}')
        elif HAS_PYNPUT:
            c = Controller()
            modifier = Key.cmd if PLATFORM == 'darwin' else Key.ctrl
            with c.pressed(modifier):
                c.press(key)
                c.release(key)
        logger.debug(f"Finished simulate Ctrl+{key}")

    @staticmethod
    def simulate_cut():
        """Simulate Ctrl+A, Ctrl+X to cut text."""
        # Clear clipboard first
        pyperclip.copy("")
        __class__.simulate_Ctrl_('a')
        time.sleep(OPERATION_TIMEOUT)
        __class__.simulate_Ctrl_('x')
        time.sleep(OPERATION_TIMEOUT)

    @staticmethod
    def simulate_paste():
        """Simulate Ctrl+V to paste."""
        __class__.simulate_Ctrl_('v')

    @staticmethod
    def simulate_enter():
        """Simulate Enter key press."""
        if PLATFORM == 'windows' and HAS_WIN32:
            win_keyboard.send('enter')
        elif HAS_PYNPUT:
            c = Controller()
            c.press(Key.enter)
            c.release(Key.enter)
