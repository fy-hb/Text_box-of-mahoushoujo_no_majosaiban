import os
import sys
import time
import random
import threading
import logging
import getpass
import argparse
from typing import Optional
import pyperclip

# Add src to path to ensure imports work if run directly
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.utils.platform_utils import PlatformUtils
from src.utils.resource_utils import get_resource_path
from src.core.image_processor import ImageProcessor
from src.config import CHARACTERS, TEXT_CONFIGS, WINDOW_WHITELIST, MAHOSHOJO_POSITION, MAHOSHOJO_OVER

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class Application:
    def __init__(self):
        self.running = True
        self.current_character_index = 2 # Default to Sherri
        self.character_list = list(CHARACTERS.keys())
        self.expression: Optional[int] = None
        self.last_image_index = -1
        self.last_generation_end_time = 0

        # Setup paths
        username = getpass.getuser()
        if os.name == 'nt':
            self.user_documents = os.path.join('C:\\', 'Users', username, 'Documents')
        else:
            self.user_documents = os.path.expanduser('~/Documents')
        
        self.magic_cut_folder = os.path.join(self.user_documents, '魔裁')
        os.makedirs(self.magic_cut_folder, exist_ok=True)
        
        self.enable_whitelist = True
        
        # Initialize
        self.show_current_character()
        # We run generation in a separate thread to not block startup, 
        # but original code did it synchronously. We'll do it in background.
        threading.Thread(target=self.generate_and_save_images, args=(self.get_current_character(),)).start()

    def get_current_character(self):
        return self.character_list[self.current_character_index]

    def get_current_font(self):
        char_name = self.get_current_character()
        font_name = CHARACTERS[char_name]["font"]
        # Fonts are now in resources/fonts/
        return get_resource_path(os.path.join("resources", "fonts", font_name))

    def show_current_character(self):
        logger.info(f"当前角色: {self.get_current_character()}")

    def switch_character(self, index):
        # Index is 1-based from hotkey, but we store 0-based index in list
        # Logic: 1->0, 2->1 ...
        # But wait, original code: switch_character(new_index). 
        # And hotkey lambda idx=i: switch_character(idx).
        # And get_current_character uses current_character_index-1.
        # So if I pass 1, it becomes index 1, and get_current uses 0.
        # My implementation:
        # I will use 0-based index internally.
        # If input is 1-based (1-14), I subtract 1.
        
        real_index = index - 1
        if 0 <= real_index < len(self.character_list):
            self.current_character_index = real_index
            char_name = self.get_current_character()
            logger.info(f"已切换到角色: {char_name}")
            threading.Thread(target=self.generate_and_save_images, args=(char_name,)).start()
        else:
            logger.warning(f"Invalid character index: {index}")

    def switch_expression(self, index):
        char_name = self.get_current_character()
        emotion_count = CHARACTERS[char_name]["emotion_count"]
        if 1 <= index <= emotion_count:
            logger.info(f"已切换至第{index}个表情")
            self.expression = index

    def clear_images(self):
        logger.info("Clearing images...")
        try:
            for filename in os.listdir(self.magic_cut_folder):
                if filename.lower().endswith('.jpg'):
                    os.remove(os.path.join(self.magic_cut_folder, filename))
            logger.info("Images cleared.")
        except Exception as e:
            logger.error(f"Error clearing images: {e}")

    def generate_and_save_images(self, character_name):
        emotion_count = CHARACTERS[character_name]["emotion_count"]
        
        # Check if already generated (simple check)
        # Original code checks if ANY file starts with character_name.
        # I'll do the same.
        for filename in os.listdir(self.magic_cut_folder):
            if filename.startswith(character_name):
                return

        logger.info(f"正在加载角色资源: {character_name}...")
        try:
            for i in range(16): # 16 backgrounds
                for j in range(emotion_count):
                    # Resources are now in resources/
                    bg_path = get_resource_path(os.path.join("resources", "background", f"c{i+1}.png"))
                    char_path = get_resource_path(os.path.join("resources", character_name, f"{character_name} ({j+1}).png"))
                    
                    if not os.path.exists(bg_path):
                        logger.warning(f"Background not found: {bg_path}")
                        continue
                    if not os.path.exists(char_path):
                        logger.warning(f"Character image not found: {char_path}")
                        continue

                    # We use ImageProcessor to paste? No, this is pre-generation of base images.
                    # Just use PIL directly or ImageProcessor helper if suitable.
                    # Original code: paste overlay at (0, 134).
                    
                    from PIL import Image
                    background = Image.open(bg_path).convert("RGBA")
                    overlay = Image.open(char_path).convert("RGBA")
                    
                    result = background.copy()
                    result.paste(overlay, (0, 134), overlay)
                    
                    img_num = j * 16 + i + 1
                    save_path = os.path.join(self.magic_cut_folder, f"{character_name} ({img_num}).jpg")
                    result.convert("RGB").save(save_path)
            logger.info("加载完成")
        except Exception as e:
            logger.error(f"Error generating images: {e}", exc_info=True)

    def get_random_base_image(self):
        char_name = self.get_current_character()
        emotion_count = CHARACTERS[char_name]["emotion_count"]
        total_images = 16 * emotion_count
        
        if self.expression:
            # Specific expression
            # Expression is 1-based index of emotion.
            # Range for expression k: (k-1)*16 + 1 to k*16
            start = (self.expression - 1) * 16 + 1
            end = self.expression * 16
            i = random.randint(start, end)
            self.last_image_index = i
            self.expression = None # Reset after use? Original code does.
            return os.path.join(self.magic_cut_folder, f"{char_name} ({i}).jpg")
        
        # Random logic to avoid same emotion consecutively
        max_attempts = 100
        attempts = 0
        
        while attempts < max_attempts:
            i = random.randint(1, total_images)
            current_emotion = (i - 1) // 16
            last_emotion = (self.last_image_index - 1) // 16 if self.last_image_index != -1 else -1
            
            if self.last_image_index == -1 or current_emotion != last_emotion:
                self.last_image_index = i
                return os.path.join(self.magic_cut_folder, f"{char_name} ({i}).jpg")
            
            attempts += 1
        
        self.last_image_index = i
        return os.path.join(self.magic_cut_folder, f"{char_name} ({i}).jpg")

    def process_generation(self):
        if time.time() - self.last_generation_end_time < 1.0:
            logger.debug("Ignoring trigger due to cooldown.")
            return

        logger.info("Start generate...")
        
        # Check whitelist
        if self.enable_whitelist:
            active_window = PlatformUtils.get_active_window_process_name()
            if active_window and active_window not in WINDOW_WHITELIST:
                logger.info(f"当前窗口 {active_window} 不在白名单内")
                return

        # Simulate Cut
        PlatformUtils.simulate_cut()
        
        # Run in thread
        # threading.Thread(target=self._generate_task).start()
        self._generate_task()
        self.last_generation_end_time = time.time()

    def _generate_task(self):
        logger.debug("Start generating task")
        try:
            base_image_path = self.get_random_base_image()
            if not os.path.exists(base_image_path):
                logger.warning(f"Base image not found: {base_image_path}. Please wait for loading.")
                return

            char_name = self.get_current_character()
            
            # Get content from clipboard
            text = pyperclip.paste()
            image = PlatformUtils.get_image_from_clipboard()
            
            if not text and image is None:
                logger.info("No text or image in clipboard.")
                return

            png_bytes = None
            
            top_left = (MAHOSHOJO_POSITION[0], MAHOSHOJO_POSITION[1])
            bottom_right = (MAHOSHOJO_OVER[0], MAHOSHOJO_OVER[1])

            if image is not None:
                logger.info("Processing image...")
                png_bytes = ImageProcessor.paste_image(
                    image_source=base_image_path,
                    top_left=top_left,
                    bottom_right=bottom_right,
                    content_image=image,
                    align="center",
                    valign="middle",
                    padding=12,
                    allow_upscale=True,
                    role_name=char_name,
                    text_configs_dict=TEXT_CONFIGS,
                    font_path=self.get_current_font()
                )
            elif text:
                logger.info(f"Processing text: {text[:20].replace('\n', ' ')}...")
                highlight_args = {}
                if char_name == "anan":
                    highlight_args = {"bracket_color": (159, 145, 251)}
                
                bracket_color = highlight_args.get("bracket_color", (137, 177, 251))
                
                png_bytes = ImageProcessor.draw_text(
                    image_source=base_image_path,
                    top_left=top_left,
                    bottom_right=bottom_right,
                    text=text,
                    align="left",
                    valign="top",
                    color=(255, 255, 255),
                    max_font_height=145,
                    font_path=self.get_current_font(),
                    role_name=char_name,
                    text_configs_dict=TEXT_CONFIGS,
                    bracket_color=bracket_color
                )

            if png_bytes:
                logger.debug("Start copying image to clipboard")
                PlatformUtils.copy_image_to_clipboard(png_bytes)
                logger.debug("Finished copying image to clipboard")
                time.sleep(0.2)
                PlatformUtils.simulate_paste()
                time.sleep(0.2)
                PlatformUtils.simulate_enter()
                logger.info("Done.")
            else:
                logger.error("Generation failed.")

        except Exception as e:
            logger.error(f"Task error: {e}", exc_info=True)

    def run(self):
        logger.info("Starting application...")
        logger.info("Press Esc to exit.")
        
        platform_name = PlatformUtils.get_platform()
        
        if platform_name == 'windows':
            try:
                import keyboard
                # Register hotkeys
                for i in range(1, 10):
                    keyboard.add_hotkey(f'ctrl+{i}', lambda idx=i: self.switch_character(idx))
                
                keyboard.add_hotkey('ctrl+q', lambda: self.switch_character(10))
                keyboard.add_hotkey('ctrl+e', lambda: self.switch_character(11))
                keyboard.add_hotkey('ctrl+r', lambda: self.switch_character(12))
                keyboard.add_hotkey('ctrl+t', lambda: self.switch_character(13))
                keyboard.add_hotkey('ctrl+y', lambda: self.switch_character(14)) # 14th character
                
                keyboard.add_hotkey('ctrl+0', self.show_current_character)
                keyboard.add_hotkey('ctrl+tab', self.clear_images)
                
                for i in range(1, 10):
                    keyboard.add_hotkey(f'alt+{i}', lambda idx=i: self.switch_expression(idx))
                
                keyboard.add_hotkey('alt+enter', self.process_generation)
                
                keyboard.wait('esc')
            except ImportError:
                logger.error("Keyboard module not found. Please install it.")
        else:
            try:
                from pynput import keyboard
                
                def on_activate_gen():
                    self.process_generation()
                
                def make_switch(idx):
                    return lambda: self.switch_character(idx)
                
                def make_expr(idx):
                    return lambda: self.switch_expression(idx)

                hotkeys = {
                    '<ctrl>+0': self.show_current_character,
                    '<alt>+<enter>': on_activate_gen,
                    '<ctrl>+<tab>': self.clear_images,
                    '<ctrl>+q': make_switch(10),
                    '<ctrl>+e': make_switch(11),
                    '<ctrl>+r': make_switch(12),
                    '<ctrl>+t': make_switch(13),
                    '<ctrl>+y': make_switch(14),
                }
                
                for i in range(1, 10):
                    hotkeys[f'<ctrl>+{i}'] = make_switch(i)
                    hotkeys[f'<alt>+{i}'] = make_expr(i)
                
                with keyboard.GlobalHotKeys(hotkeys) as h:
                    h.join()
            except ImportError:
                logger.error("pynput module not found. Please install it.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--debug', action='store_true', help='Enable debug logging')
    args = parser.parse_args()

    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
        logger.info("Debug mode enabled")

    app = Application()
    app.run()
