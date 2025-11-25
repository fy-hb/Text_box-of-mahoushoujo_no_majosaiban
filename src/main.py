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
from src.utils.kitty_utils import display_image
from src.core.image_processor import ImageProcessor
from src.config import CHARACTERS, TEXT_CONFIGS, WINDOW_WHITELIST, MAHOSHOJO_POSITION, MAHOSHOJO_OVER, OPERATION_TIMEOUT

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class Application:
    def __init__(self):
        self.running = True
        self.current_character_index = 2 # Default to Sherri
        self.character_list = list(CHARACTERS.keys())
        self.next_expression: Optional[int] = None
        self.next_background: Optional[int] = None
        self.expression: Optional[int] = None
        self.background: Optional[int] = None
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
        self._roll_next_randoms()
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
            self._roll_next_randoms()
            threading.Thread(target=self.generate_and_save_images, args=(char_name,)).start()
        else:
            logger.warning(f"Invalid character index: {index}")

    def switch_expression(self, index):
        char_name = self.get_current_character()
        emotion_count = CHARACTERS[char_name]["emotion_count"]
        if 1 <= index <= emotion_count:
            logger.info(f"已切换至第{index}个表情")
            self.expression = index
            self.print_info()
        else:
            logger.warning(f"Invalid expression index: {index}")

    def switch_background(self, index):
        if 1 <= index <= 16:
            logger.info(f"已切换至第{index}个背景")
            self.background = index
            self.print_info()
        else:
            logger.warning(f"Invalid background index: {index}")

    def _roll_next_randoms(self):
        char_name = self.get_current_character()
        emotion_count = CHARACTERS[char_name]["emotion_count"]
        
        # Roll expression
        emotion_idx = random.randint(0, emotion_count - 1)
        if self.last_image_index != -1 and emotion_count > 1:
             last_emotion = (self.last_image_index - 1) // 16
             for _ in range(5):
                 if emotion_idx != last_emotion:
                     break
                 emotion_idx = random.randint(0, emotion_count - 1)
        self.next_expression = emotion_idx + 1
        
        # Roll background
        self.next_background = random.randint(1, 16)

    def print_help(self):
        print("Available commands:")
        print("  char [name|index]  Switch character. No arg to cycle.")
        print("  expr [index]       Switch expression. No arg to cycle. '0' or 'random' for random.")
        print("  bg [index]         Switch background. No arg to cycle. '0' or 'random' for random.")
        print("  info               Show current settings and preview.")
        print("  help               Show this help.")
        print("  exit / quit        Exit application.")

    def print_info(self):
        char_name = self.get_current_character()
        
        if self.expression:
            expr_str = str(self.expression)
        else:
            if self.next_expression is None: self._roll_next_randoms()
            expr_str = f"Random (Next: {self.next_expression})"
            
        if self.background:
            bg_str = str(self.background)
        else:
            if self.next_background is None: self._roll_next_randoms()
            bg_str = f"Random (Next: {self.next_background})"
        
        print(f"\n=== Current Status ===")
        print(f"Character:  {char_name} ({self.current_character_index + 1}/{len(self.character_list)})")
        print(f"Expression: {expr_str}")
        print(f"Background: {bg_str}")
        
        # Preview
        # We generate a temporary path or just use get_random_base_image logic to find a file
        # that represents current state.
        preview_path = self.get_random_base_image()
        if os.path.exists(preview_path):
            print("Preview:")
            display_image(preview_path)
        else:
            print("(Preview not available - image not generated yet)")
        print("======================\n")

    def handle_char_cmd(self, args):
        if not args:
            # Cycle
            new_index = (self.current_character_index + 1) % len(self.character_list)
            self.switch_character(new_index + 1) # switch_character takes 1-based index
            self.print_info()
            return

        arg = args[0]
        if arg.isdigit():
            idx = int(arg)
            self.switch_character(idx)
            self.print_info()
        else:
            # Try to find by name
            try:
                idx = self.character_list.index(arg)
                self.switch_character(idx + 1)
                self.print_info()
            except ValueError:
                print(f"Character '{arg}' not found.")

    def handle_expr_cmd(self, args):
        char_name = self.get_current_character()
        emotion_count = CHARACTERS[char_name]["emotion_count"]
        
        if not args:
            # Cycle
            current = self.expression if self.expression else 0
            new_expr = (current % emotion_count) + 1
            self.switch_expression(new_expr)
            return

        arg = args[0].lower()
        if arg in ['random', '0']:
            self.expression = None
            self._roll_next_randoms()
            logger.info("Expression set to Random")
            self.print_info()
        elif arg.isdigit():
            self.switch_expression(int(arg))
        else:
            print("Invalid expression argument.")

    def handle_bg_cmd(self, args):
        if not args:
            # Cycle
            current = self.background if self.background else 0
            new_bg = (current % 16) + 1
            self.switch_background(new_bg)
            return

        arg = args[0].lower()
        if arg in ['random', '0']:
            self.background = None
            self._roll_next_randoms()
            logger.info("Background set to Random")
            self.print_info()
        elif arg.isdigit():
            self.switch_background(int(arg))
        else:
            print("Invalid background argument.")


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
        
        # Determine emotion index (0-based)
        if self.expression:
            emotion_idx = self.expression - 1
        else:
            if self.next_expression is None:
                self._roll_next_randoms()
            emotion_idx = self.next_expression - 1

        # Determine background index (0-based)
        if self.background:
            bg_idx = self.background - 1
        else:
            if self.next_background is None:
                self._roll_next_randoms()
            bg_idx = self.next_background - 1

        # Calculate image number (1-based)
        img_num = emotion_idx * 16 + bg_idx + 1
        
        return os.path.join(self.magic_cut_folder, f"{char_name} ({img_num}).jpg")

    def process_generation(self):
        if time.time() - self.last_generation_end_time < 0.5:
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

            # Extract img_num for updating state later
            try:
                filename = os.path.basename(base_image_path)
                # format: Name (123).jpg
                img_num_str = filename.rsplit('(', 1)[1].split(')')[0]
                current_img_num = int(img_num_str)
            except:
                current_img_num = -1

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
                time.sleep(OPERATION_TIMEOUT)
                PlatformUtils.simulate_paste()
                time.sleep(OPERATION_TIMEOUT)
                PlatformUtils.simulate_enter()
                logger.info("Done.")
                
                # Update state
                self.last_image_index = current_img_num
                self._roll_next_randoms()
            else:
                logger.error("Generation failed.")

        except Exception as e:
            logger.error(f"Task error: {e}", exc_info=True)

    def run(self):
        logger.info("Starting application...")
        
        # Start hotkey listener in a separate thread
        hotkey_thread = threading.Thread(target=self.start_hotkey_listener, daemon=True)
        hotkey_thread.start()
        
        self.print_help()
        self.print_info()
        
        while self.running:
            try:
                # Use input() for command loop
                cmd_input = input("> ")
                cmd_line = cmd_input.strip().split()
                if not cmd_line: continue
                
                cmd = cmd_line[0].lower()
                args = cmd_line[1:]
                
                if cmd == 'help':
                    self.print_help()
                elif cmd == 'char':
                    self.handle_char_cmd(args)
                elif cmd == 'expr':
                    self.handle_expr_cmd(args)
                elif cmd == 'bg':
                    self.handle_bg_cmd(args)
                elif cmd == 'info':
                    self.print_info()
                elif cmd == 'clear':
                    self.clear_images()
                elif cmd in ['exit', 'quit']:
                    self.running = False
                    logger.info("Exiting...")
                    os._exit(0)
                else:
                    print("Unknown command. Type 'help' for list.")
            except (EOFError, KeyboardInterrupt):
                self.running = False
                print("\nExiting...")
                os._exit(0)
            except Exception as e:
                logger.error(f"Error in command loop: {e}")

    def start_hotkey_listener(self):
        platform_name = PlatformUtils.get_platform()
        
        if platform_name == 'windows':
            try:
                import keyboard
                # Only keep generation hotkey
                keyboard.add_hotkey('alt+enter', self.process_generation)
                keyboard.wait()
            except ImportError:
                logger.error("Keyboard module not found. Please install it.")
        else:
            try:
                from pynput import keyboard
                
                def on_activate_gen():
                    self.process_generation()
                
                hotkeys = {
                    '<alt>+<enter>': on_activate_gen,
                }
                
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
