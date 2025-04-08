# combined_mc_solver.py
# Combines setup checks and main application logic for a Gemini Knowledge MC Solver.
# Windows Focused.

import sys
import os
import platform
import subprocess
import importlib
import ctypes  # For checking admin privileges on Windows
import time
import threading
import signal # Just for SIGINT (Ctrl+C)
import io

# --- Attempt to Import Core Libraries (will be installed if missing) ---
try:
    import keyboard
    import mss
    import mss.tools
    from PIL import Image
    from dotenv import load_dotenv, set_key, dotenv_values
    import google.generativeai as genai
    import google.api_core.exceptions # For specific error handling
except ImportError as e:
    print(f"Info: Initial import failed for '{e.name}'. Setup will attempt installation.")
    # Define placeholders if needed for setup phase functions
    if 'dotenv' in str(e):
        load_dotenv = None
        set_key = None
        dotenv_values = None
    # Other critical libs will be checked/installed by install_libraries()

# --- Configuration ---
# Setup Config
REQUIRED_LIBRARIES = [
    "keyboard",
    "mss",
    "Pillow",         # Note: Imported as PIL
    "google-generativeai",
    "python-dotenv"
]
ENV_FILE_NAME = ".env"
API_KEY_NAME = "GOOGLE_API_KEY"

# Main App Config
TRIGGER_KEY = '='
TOGGLE_KEY = 'caps lock'
SUPPRESS_TRIGGER = True # Prevent '=' from being typed

# AI Config (API Key loaded after setup)
GOOGLE_API_KEY = None # Will be loaded later
# --- IMPORTANT: AI Model Selection ---
# Using a multimodal model capable of reading text in images and applying knowledge.
# gemini-1.5-flash: Faster, good balance of vision/knowledge. START HERE.
# gemini-1.5-pro: More powerful reasoning/knowledge, potentially slower/more expensive. Try if Flash struggles.
# Other models like gemini-pro (text only) CANNOT process the image directly.
AI_MODEL_NAME = "gemini-1.5-flash-latest" # Use the latest flash model

# Caps Lock Signaling Config
SIGNAL_BASE = {'A': 1, 'B': 2, 'C': 3, 'D': 4, 'E': 5, 'F': 6}
SIGNAL_ON_DURATION = 0.15
SIGNAL_OFF_DURATION = 0.15
PAUSE_BETWEEN_SIGNALS = 0.5

# --- State ---
process_lock = threading.Lock()
running = True # Flag for graceful shutdown

# === SETUP FUNCTIONS (from setup_assistant.py) ===

def check_windows():
    """Checks if running on Windows."""
    print("--- Checking Operating System ---")
    if platform.system() != "Windows":
        print(f"ERROR: This script is designed ONLY for Windows.")
        print(f"Detected OS: {platform.system()}. Exiting.")
        return False
    print("Operating System: Windows (OK).")
    return True

def check_admin_privileges():
    """Checks if the script is running with Administrator privileges on Windows."""
    print("\n--- Checking Administrator Privileges ---")
    is_admin = False
    try:
        # Windows check
        is_admin = ctypes.windll.shell32.IsUserAnAdmin() != 0
    except AttributeError:
        print("  Warning: Could not perform standard Windows admin check (AttributeError).")
        # Fallback check (less reliable, might give false negatives)
        try:
             # Attempting a privileged operation that usually requires admin
             temp_dir = os.path.join(os.environ.get("SystemRoot", "C:\\Windows"), "Temp")
             os.listdir(temp_dir)
             print("  Info: Able to access System Temp directory, assuming sufficient privileges.")
             # Note: This isn't a guarantee of full admin rights
             # is_admin = True # Cautious approach: don't assume admin based on this
        except PermissionError:
             print("  Warning: Permission denied accessing System Temp directory.")
        except Exception as e:
             print(f"  Warning: Could not reliably determine admin status. Error: {e}")
    except Exception as e:
        print(f"  Warning: Could not reliably determine admin status. Error: {e}")


    if is_admin:
        print("- Script is running with Administrator privileges (Recommended).")
    else:
        print("! WARNING: Script does NOT appear to be running with Administrator privileges.")
        print("  This script needs admin rights to capture keyboard input globally")
        print("  and potentially for screenshots, especially across different applications.")
        print("  => If the script fails to respond to the trigger key ('='),")
        print("     please re-run it by:")
        print("     1. Right-clicking Command Prompt (cmd) or PowerShell.")
        print("     2. Selecting 'Run as administrator'.")
        print("     3. Navigating (cd) to this script's directory and running it:")
        print(f"        python {os.path.basename(__file__)}")
    # We don't exit here, just warn, as some systems might work without it.
    return True # Allow execution to continue

def check_python_version():
    """Checks if Python 3.8+ is being used."""
    print("\n--- Checking Python Version ---")
    if sys.version_info < (3, 8):
        print(f"ERROR: Python 3.8 or higher is recommended. You are using {platform.python_version()}.")
        print("Please upgrade your Python installation.")
        return False
    print(f"Python version {platform.python_version()} is sufficient.")
    return True

def install_libraries():
    """Installs required libraries using pip."""
    print("\n--- Checking and Installing Libraries ---")
    missing_libs = []
    for lib in REQUIRED_LIBRARIES:
        try:
            # Adjust import name if necessary (e.g., Pillow -> PIL)
            import_name = lib
            if lib == 'Pillow': import_name = 'PIL'
            elif lib == 'python-dotenv': import_name = 'dotenv'
            elif lib == 'google-generativeai': import_name = 'google.generativeai' # Already has .

            # Use find_spec for a more reliable check than import_module for installation status
            spec = importlib.util.find_spec(import_name)
            if spec is None:
                 missing_libs.append(lib)
                 print(f"- '{lib}' not found.")
            else:
                 print(f"- '{lib}' found.")
        except ModuleNotFoundError:
             missing_libs.append(lib)
             print(f"- '{lib}' not found (ModuleNotFoundError).")
        except ImportError:
             # Handle cases where the top-level package exists but a submodule doesn't
             # (less common for these specific libs, but good practice)
             missing_libs.append(lib)
             print(f"- '{lib}' partially found or import issue (ImportError).")
        except Exception as e:
             print(f"  Warning: Error checking for library '{lib}': {e}")
             # Assume it might be missing to be safe
             if lib not in missing_libs:
                 missing_libs.append(lib)


    if not missing_libs:
        print("All required libraries appear to be installed.")
        # Attempt to re-import now in case they were installed but initial import failed
        try:
            global keyboard, mss, mss_tools, Image, load_dotenv, set_key, dotenv_values, genai, google_api_core_exceptions
            import keyboard
            import mss
            import mss.tools as mss_tools
            from PIL import Image
            from dotenv import load_dotenv, set_key, dotenv_values
            import google.generativeai as genai
            import google.api_core.exceptions as google_api_core_exceptions
            print("Successfully re-imported core libraries.")
            return True
        except ImportError as e:
            print(f"ERROR: Library '{e.name}' is reported as installed but failed to import.")
            print("There might be an issue with your Python environment or the installation.")
            print("Try running: pip install --force-reinstall " + " ".join(REQUIRED_LIBRARIES))
            return False


    print(f"Attempting to install missing libraries: {', '.join(missing_libs)}")
    try:
        # Use sys.executable to ensure pip corresponds to the current Python interpreter
        subprocess.check_call([sys.executable, "-m", "pip", "install", *missing_libs],
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE) # Hide excessive output unless error
        print(f"Successfully installed missing libraries.")
        # Crucial: Reload modules after installation
        print("Reloading libraries...")
        global keyboard, mss, mss_tools, Image, load_dotenv, set_key, dotenv_values, genai, google_api_core_exceptions
        importlib.invalidate_caches() # Clear import caches
        import keyboard
        import mss
        import mss.tools as mss_tools
        from PIL import Image
        from dotenv import load_dotenv, set_key, dotenv_values
        import google.generativeai as genai
        import google.api_core.exceptions as google_api_core_exceptions
        print("Successfully loaded libraries after installation.")
        return True
    except subprocess.CalledProcessError as e:
        print(f"ERROR: Failed to install libraries using pip.")
        print(f"Command: '{' '.join(e.cmd)}'")
        # Attempt to decode stderr for more specific error messages
        stderr_output = e.stderr.decode('utf-8', errors='replace').strip() if e.stderr else "No stderr output."
        print(f"Stderr: {stderr_output}")
        print(f"\nPlease try installing them manually in an Administrator command prompt:")
        print(f"  pip install {' '.join(missing_libs)}")
        return False
    except ImportError as e:
        print(f"ERROR: Failed to import library '{e.name}' even after attempting installation.")
        return False
    except Exception as e:
         print(f"An unexpected error occurred during installation or reloading: {e}")
         return False


def configure_api_key():
    """Checks for .env file and API key, prompts if necessary."""
    global GOOGLE_API_KEY # Make sure we update the global variable

    # Ensure dotenv functions are available
    if load_dotenv is None or set_key is None or dotenv_values is None:
        print("ERROR: 'python-dotenv' library failed to load. Cannot manage API key.")
        return False

    print(f"\n--- Configuring API Key ({ENV_FILE_NAME}) ---")
    key_value = None
    # Use absolute path for reliability, especially when run from different directories
    script_dir = os.path.dirname(os.path.abspath(__file__))
    env_path = os.path.join(script_dir, ENV_FILE_NAME)


    if os.path.exists(env_path):
        print(f"- Found '{ENV_FILE_NAME}' file at '{env_path}'.")
        try:
            values = dotenv_values(env_path)
            key_value = values.get(API_KEY_NAME)
            if key_value:
                print(f"- Found '{API_KEY_NAME}' in the file.")
                GOOGLE_API_KEY = key_value
                return True # Key exists and loaded
            else:
                print(f"- Key '{API_KEY_NAME}' not found within the file.")
        except Exception as e:
             print(f"  Warning: Error reading .env file: {e}")
             # Continue to prompt for key as if it wasn't found

    if not key_value:
        print(f"- '{API_KEY_NAME}' not found or '{ENV_FILE_NAME}' is missing/unreadable/empty.")
        print("\nYou need a Google AI API Key for Gemini.")
        print("You can get one for free from: https://aistudio.google.com/app/apikey")
        while not key_value:
            key_value = input(f"Please paste your {API_KEY_NAME} here and press Enter:\n> ").strip()
            if not key_value:
                print("API Key cannot be empty. Please try again.")
            elif not key_value.startswith("AIza"):
                 print("Warning: Key doesn't look like a typical Google AI key. Ensure it's correct.")
                 confirm = input("Proceed with this key? (y/n): ").lower()
                 if confirm != 'y':
                      key_value = None # Reset to ask again

    try:
        print(f"- Saving key to '{env_path}'...")
        # Ensure the directory exists (though it should)
        os.makedirs(script_dir, exist_ok=True)
        # Use set_key which creates the file if it doesn't exist
        success = set_key(env_path, API_KEY_NAME, key_value, quote_mode='never')
        if success:
             print(f"- Successfully saved '{API_KEY_NAME}' to '{ENV_FILE_NAME}'.")
             GOOGLE_API_KEY = key_value
             return True
        else:
             # This case is less likely with set_key, maybe permissions?
             print(f"ERROR: 'set_key' failed to save the API key, but reported no exception.")
             print(f"Please check permissions for the directory: {script_dir}")
             print(f"You may need to manually create the file '{env_path}'")
             print(f"with the line: {API_KEY_NAME}={key_value}")
             return False

    except PermissionError:
         print(f"ERROR: Permission denied when trying to write to '{env_path}'.")
         print("Try running this script as Administrator.")
         print(f"Alternatively, manually create the file '{env_path}'")
         print(f"with the line: {API_KEY_NAME}={key_value}")
         return False
    except Exception as e:
        print(f"ERROR: Could not write API key to '{env_path}'. Error: {type(e).__name__}: {e}")
        print(f"Please create the '.env' file manually with the line: {API_KEY_NAME}=YOUR_KEY_HERE")
        return False

# === MAIN APPLICATION FUNCTIONS (from main_script.py) ===

def signal_answer_with_capslock(answer_letter):
    """Signals the answer letter using Caps Lock flashes."""
    global running
    answer_upper = answer_letter.upper() # Convert once
    if answer_upper not in SIGNAL_BASE:
        print(f"Cannot signal answer '{answer_letter}'. Not defined in SIGNAL_BASE.")
        return

    num_flashes = SIGNAL_BASE[answer_upper]
    print(f"Signaling answer: {answer_upper} ({num_flashes} flashes) based on AI knowledge.") # Added clarification

    try:
        for i in range(num_flashes):
            if not running:
                print(" - Signaling interrupted by shutdown.")
                break
            keyboard.press_and_release(TOGGLE_KEY)
            time.sleep(SIGNAL_ON_DURATION)
            if not running: break
            keyboard.press_and_release(TOGGLE_KEY)
            time.sleep(SIGNAL_OFF_DURATION)
            if i < num_flashes - 1:
                 time.sleep(PAUSE_BETWEEN_SIGNALS)
        print(f"Finished signaling '{answer_upper}'.")
    except Exception as e:
        print(f"Error during Caps Lock signaling: {e}")
        print("Ensure the script still has keyboard control (try running as Admin if issues persist).")


def get_answer_from_ai_knowledge(pil_image): # Renamed function for clarity
    """Sends image to Gemini, asks it to READ the question and use its KNOWLEDGE to answer."""
    global running, genai, google_api_core_exceptions # Use globals loaded/reloaded after install
    print(f"Asking AI ({AI_MODEL_NAME}) to read image and apply knowledge...")
    if not running: return None

    if genai is None or google_api_core_exceptions is None:
        print("ERROR: Google AI library not loaded correctly. Cannot proceed.")
        return None

    try:
        model = genai.GenerativeModel(AI_MODEL_NAME)
    except Exception as model_err:
        print(f"ERROR: Failed to initialize Gemini model '{AI_MODEL_NAME}': {model_err}")
        print(" - Check if the model name is correct and supported.")
        print(" - Ensure the Google AI library and API key are configured correctly.")
        return None

    # --- *** NEW KNOWLEDGE-BASED PROMPT *** ---
    prompt = """
You are an expert assistant. Analyze the provided image which contains a multiple-choice question.
1. Read the question and all the answer options (A, B, C, D, etc.) directly from the image.
2. Use your internal knowledge about the subject matter to determine the single best correct answer.
3. Respond ONLY with the capital letter of that correct option (e.g., A, B, C, D, E, F).
If you cannot accurately read the question/options from the image, if the question is nonsensical, or if you cannot determine the correct answer using your knowledge, respond ONLY with the single word: ERROR.
Do not provide any explanation, reasoning, calculations, or extra text. Just the single letter or the word ERROR.
"""

    try:
        print(f" - Sending image and knowledge prompt to Gemini model: {AI_MODEL_NAME}...")
        response = model.generate_content(
            [prompt, pil_image], # Send both prompt text and image data
            generation_config=genai.types.GenerationConfig(
                # temperature=0.1 # Keep temp low for strict format following
                temperature=0.0 # Strictest temperature for single letter / ERROR response
            ),
            # Safety settings might need adjustment if questions get blocked often
            # safety_settings={'HARASSMENT':'BLOCK_NONE', 'HATE_SPEECH': 'BLOCK_NONE', 'SEXUAL': 'BLOCK_NONE', 'DANGEROUS': 'BLOCK_NONE'},
            request_options={'timeout': 90} # Increase timeout slightly for potentially more complex reasoning
        )

        # --- Robust Response Handling ---
        ai_response_text = ""

        # Check for blocking first (common issue)
        if not response.candidates:
            block_reason = "Unknown"
            safety_ratings = "N/A"
            try:
                 # Access prompt_feedback safely
                 if hasattr(response, 'prompt_feedback') and response.prompt_feedback:
                    block_reason = response.prompt_feedback.block_reason
                    safety_ratings = response.prompt_feedback.safety_ratings
            except AttributeError: pass
            except Exception as fb_err: print(f" - Error accessing prompt feedback details: {fb_err}")

            print(f"ERROR: Gemini response was empty or blocked. Reason: {block_reason}, Safety Ratings: {safety_ratings}")
            if block_reason == 'SAFETY':
                print("  - The request might have been blocked due to safety filters.")
                print("  - Consider uncommenting and adjusting 'safety_settings' in the code if appropriate for your content.")
            elif block_reason == 'OTHER':
                 print("  - Blocked for 'OTHER' reason. This might be due to image content, prompt complexity, or internal issues.")
            else:
                 print("  - Check API key, quotas, and Gemini service status.")
            return None

        # Extract text using recommended safe access pattern
        try:
            # response.text should provide the aggregated text content directly
            ai_response_text = response.text
        except ValueError:
             # Handle case where response.text might raise ValueError if content is blocked or non-text
            print("ERROR: Could not extract text directly from Gemini response (ValueError). Checking candidates...")
            try:
                 if response.candidates and response.candidates[0].content and response.candidates[0].content.parts:
                      ai_response_text = response.candidates[0].content.parts[0].text
                 else:
                      print(" - No valid text found in candidates either.")
                      print(f" - Full Response Object: {response}") # Log the full response for debugging
                      return None
            except (AttributeError, IndexError, Exception) as resp_err:
                 print(f"ERROR: Could not extract text from Gemini response structure: {resp_err}")
                 print(f" - Full Response Object: {response}") # Log the full response for debugging
                 return None
        except Exception as resp_err:
             print(f"ERROR: Unexpected error extracting text from Gemini response: {resp_err}")
             print(f" - Full Response Object: {response}") # Log the full response for debugging
             return None


        ai_response_text_processed = ai_response_text.strip().upper()
        print(f"AI raw response: '{ai_response_text.strip()}' -> Processed: '{ai_response_text_processed}'")

        # Check response format
        if ai_response_text_processed in SIGNAL_BASE:
            return ai_response_text_processed
        elif ai_response_text_processed == "ERROR":
            print(" - AI responded with ERROR (cannot read/determine answer).")
            return None
        elif len(ai_response_text_processed) == 1 and ai_response_text_processed in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
             print(f" - Warning: AI responded with single letter '{ai_response_text_processed}' not defined in SIGNAL_BASE {list(SIGNAL_BASE.keys())}. Cannot signal.")
             return None
        else:
            # Try extracting if AI added extra words (less likely with strict prompt/temp=0 but possible)
            potential_letters = [char for char in ai_response_text_processed if char in SIGNAL_BASE]
            if len(potential_letters) == 1:
                extracted_letter = potential_letters[0]
                print(f" - Warning: AI response had extra text ('{ai_response_text.strip()}'). Extracted single valid signal letter: {extracted_letter}")
                return extracted_letter
            else:
                print(f" - AI gave an unexpected or unusable response: '{ai_response_text.strip()}'")
                print(f" - Expected one of {list(SIGNAL_BASE.keys())} or 'ERROR'.")
                return None

    # Specific Google API Error Handling
    except google_api_core_exceptions.ResourceExhausted as e:
         print(f"ERROR querying Google Gemini API: Quota Exceeded. {e}")
         print("  - Check your Google Cloud project billing and API quotas.")
         return None
    except google_api_core_exceptions.PermissionDenied as e:
         print(f"ERROR querying Google Gemini API: Permission Denied. {e}")
         print("  - Check your GOOGLE_API_KEY and ensure the Gemini API is enabled in your Google Cloud project.")
         return None
    except google_api_core_exceptions.DeadlineExceeded as e:
         print(f"ERROR querying Google Gemini API: Timeout / Deadline Exceeded ({response.request_options.get('timeout', 'default')}s). {e}")
         print("  - Check internet connection or Gemini API status.")
         print("  - The image might be too large/complex or the model took too long.")
         return None
    except google_api_core_exceptions.InvalidArgument as e:
         print(f"ERROR querying Google Gemini API: Invalid Argument. {e}")
         print(f"  - Often means an issue with the image format/data, the prompt, or the request structure.")
         print(f"  - Ensure the model '{AI_MODEL_NAME}' supports image input with this prompt.")
         return None
    except google_api_core_exceptions.InternalServerError as e:
         print(f"ERROR querying Google Gemini API: Internal Server Error. {e}")
         print("  - This is likely an issue on Google's side. Try again later.")
         return None
    except google_api_core_exceptions.ServiceUnavailable as e:
         print(f"ERROR querying Google Gemini API: Service Unavailable. {e}")
         print("  - The Gemini service might be temporarily down or overloaded. Try again later.")
         return None
    except Exception as e:
        print(f"Error during Gemini API call or processing: {type(e).__name__}: {e}")
        # import traceback # Uncomment for full debug trace
        # traceback.print_exc()
        return None


def process_screenshot_and_get_answer():
    """Takes screenshot, asks AI to use KNOWLEDGE, and signals the answer."""
    global running, mss, Image # Use globals loaded/reloaded after install
    screenshot_pil_img = None
    start_time = time.time()

    if mss is None or Image is None:
         print("ERROR: Screenshot libraries (mss, Pillow) not loaded correctly.")
         # Release lock if held, as this thread cannot proceed
         if process_lock.locked():
             try: process_lock.release()
             except RuntimeError: pass
         return

    try:
        print("Taking screenshot...")
        # Use with statement for mss for cleaner resource management
        with mss.mss() as sct:
            # Attempt to get the primary monitor (often index 1, but check)
            # sct.monitors includes the aggregate monitor at index 0.
            # Index 1 is typically the primary physical monitor.
            primary_monitor_index = 1
            if len(sct.monitors) <= primary_monitor_index:
                print(f"Warning: Monitor index {primary_monitor_index} not found. Monitors available: {sct.monitors}")
                if len(sct.monitors) > 0:
                    print("Falling back to the first available monitor (index 0 - might be the aggregate).")
                    monitor = sct.monitors[0]
                else:
                    print("FATAL: No monitors detected by mss.")
                    # Release lock
                    if process_lock.locked():
                        try: process_lock.release()
                        except RuntimeError: pass
                    return # Cannot proceed without a monitor
            else:
                 monitor = sct.monitors[primary_monitor_index]
                 print(f" - Using monitor {primary_monitor_index}: {monitor}")


            sct_img = sct.grab(monitor)
            print(f" - Screenshot captured ({sct_img.width}x{sct_img.height}).")

            # Convert the BGRA screenshot grab to RGB for PIL/Gemini
            screenshot_pil_img = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")
            print(" - Image converted for AI.")

            # Optional: Save for debugging
            # debug_filename = f"screenshot_debug_{time.strftime('%Y%m%d_%H%M%S')}.png"
            # screenshot_pil_img.save(debug_filename)
            # print(f" - Debug screenshot saved as {debug_filename}")

        if not running or screenshot_pil_img is None:
            print(" - Process interrupted or screenshot failed before AI call.")
            # Release lock
            if process_lock.locked():
                try: process_lock.release()
                except RuntimeError: pass
            return

        # *** Call the KNOWLEDGE-based function ***
        answer = get_answer_from_ai_knowledge(screenshot_pil_img)

        if not running:
             print(" - Process interrupted after AI call.")
             # Release lock
             if process_lock.locked():
                 try: process_lock.release()
                 except RuntimeError: pass
             return

        if answer:
            signal_answer_with_capslock(answer)
        else:
            print("No valid answer received from AI knowledge or process interrupted. No signal sent.")

    except mss.ScreenShotError as sc_err:
         print(f"Error taking screenshot: {sc_err}")
         print(" - Ensure no other screen capture software is interfering.")
         print(" - Running as Administrator might be required.")
         print(" - Check if the monitor selection logic is correct for your setup.")
    except AttributeError as ae:
        # Catch errors if mss or Image weren't loaded correctly
        print(f"Error during screenshot processing (likely missing library): {ae}")
        print(" - Please ensure 'mss' and 'Pillow' libraries were installed correctly.")
    except Exception as e:
        print(f"Error during screenshot processing thread: {type(e).__name__}: {e}")
        import traceback; traceback.print_exc() # More detailed traceback for unexpected errors
    finally:
        # Ensure the lock is always released, even if errors occur
        if process_lock.locked():
             try:
                 process_lock.release()
             except RuntimeError:
                 # This can happen if the lock was already released or never acquired properly
                 # print(" - Info: Lock release attempted but was not held.")
                 pass
             except Exception as release_err:
                 print(f" - Warning: Error releasing process lock: {release_err}")
        end_time = time.time()
        print(f"Processing finished in {end_time - start_time:.2f} seconds.")


def handle_trigger():
    """Called when the trigger key is pressed. Starts the process thread."""
    global running
    if not running:
        return

    if not process_lock.locked():
        # Use acquire with blocking=False to prevent queuing if already processing
        acquired = process_lock.acquire(blocking=False)
        if acquired:
            print(f"\n'{TRIGGER_KEY}' detected. Starting screenshot analysis using AI knowledge...") # Updated message
            # Start as a daemon thread so it doesn't block script exit
            thread = threading.Thread(target=process_screenshot_and_get_answer, daemon=True)
            thread.start()
        # If acquire failed, it means the lock is held (already processing)
        # else:
        #     print(f"'{TRIGGER_KEY}' detected, but already processing. Ignoring.")
    else:
         # This case should ideally be less frequent with non-blocking acquire,
         # but good as a fallback message.
         print(f"'{TRIGGER_KEY}' detected, but already processing. Please wait.")

def signal_handler(sig, frame):
    """Handles Ctrl+C for graceful shutdown."""
    global running
    if running:
        print("\nShutdown signal (Ctrl+C) received. Cleaning up...")
        running = False
        # Don't exit immediately, let the main loop handle cleanup

# === MAIN EXECUTION BLOCK ===

def run_main_application():
    """Contains the main application logic after setup is complete."""
    global running, GOOGLE_API_KEY, genai # Use globals

    print("\n--- Starting Gemini Knowledge MC Solver ---")
    print(f"Press '{TRIGGER_KEY}' to screenshot, have AI analyze using KNOWLEDGE, and signal answer.")
    print(f"Using AI Model: {AI_MODEL_NAME}")
    print(f"Signaling: A={SIGNAL_BASE['A']}..F={SIGNAL_BASE['F']} flashes via '{TOGGLE_KEY}'")
    print(f"Press Ctrl+C in this console window to stop.")
    if SUPPRESS_TRIGGER:
        print(f"Note: The '{TRIGGER_KEY}' key press itself will be suppressed.")

    # --- Configure Google AI ---
    if not GOOGLE_API_KEY:
        print("\nFATAL: API Key not configured during setup. Exiting.")
        return # Exit this function, main block will terminate

    try:
        if genai is None:
             raise ImportError("Google Generative AI library not loaded.")
        genai.configure(api_key=GOOGLE_API_KEY)
        print("Google AI SDK configured successfully.")
    except ImportError as e:
         print(f"ERROR: Failed to import Google AI library for configuration: {e}")
         print("Setup might have failed to install or load 'google-generativeai'.")
         return
    except Exception as e:
        print(f"ERROR: Failed to configure Google AI. Check API Key validity and internet connection: {e}")
        return

    # --- Setup Signal Handler for Ctrl+C ---
    signal.signal(signal.SIGINT, signal_handler)
    print("\nCtrl+C handler set.")

    # --- Setup Keyboard Listener ---
    listener_success = False
    try:
        if keyboard is None:
             raise ImportError("'keyboard' library not loaded.")

        print("Setting up keyboard listener...")
        # Using add_hotkey is generally preferred for specific keys
        keyboard.add_hotkey(
            TRIGGER_KEY,
            handle_trigger,
            trigger_on_release=False, # Trigger immediately on press
            suppress=SUPPRESS_TRIGGER
        )
        print(f"Listener active. Ready for '{TRIGGER_KEY}' key press.")
        listener_success = True

        # --- Main Loop ---
        print("Entering main loop (waiting for trigger or Ctrl+C)...")
        while running:
            # Keep the main thread alive while the listener runs in the background
            # time.sleep is essential to prevent high CPU usage
            time.sleep(0.5) # Check the running flag periodically

    except ImportError as e:
         print(f"\nERROR: The '{e.name}' library is not available.")
         print("Setup might have failed. Please check installation messages.")
         running = False # Ensure cleanup runs
    except Exception as e:
        print(f"\nAn unexpected error occurred setting up listener or in main loop: {type(e).__name__}: {e}")
        if "permissions" in str(e).lower() or "access denied" in str(e).lower() or "administrator" in str(e).lower() or isinstance(e, OSError) and e.winerror == 5 :
             print("\n>>> ERROR LIKELY DUE TO MISSING PERMISSIONS. <<<")
             print(">>> The 'keyboard' library needs high-level access to monitor keys.")
             print(">>> Please re-run this script from a Command Prompt or PowerShell")
             print(">>> window that was opened using 'Run as administrator'.")
        elif "requires root" in str(e).lower(): # Linux specific, but good to include
            print("\n>>> ERROR LIKELY DUE TO MISSING PERMISSIONS (non-Windows). <<<")
            print(">>> Please re-run this script using 'sudo python your_script.py'.")
        else:
             print("\nAn unexpected error occurred.")
             import traceback
             traceback.print_exc()
        running = False # Ensure cleanup runs
    finally:
        # --- Cleanup ---
        print("\n--- Script Stopping ---")
        if running: # If loop exited unexpectedly
             running = False
             print("Exiting loop unexpectedly...")

        # Ensure the running flag is False so threads can see it
        running = False

        # Release lock if held (important if Ctrl+C happens during processing)
        if process_lock.locked():
            print("Releasing process lock...")
            try:
                process_lock.release()
            except Exception as lock_err:
                 print(f"Error releasing lock during shutdown: {lock_err}")

        # Wait slightly for background threads (like screenshot/AI) to notice 'running = False'
        print("Waiting briefly for background tasks to finish...")
        time.sleep(1.0) # Allow a bit more time

        print("Cleaning up keyboard hooks...")
        if listener_success and keyboard: # Only unhook if setup was successful
            try:
                keyboard.unhook_all()
                print("Keyboard hooks removed.")
            except Exception as uh_e:
                print(f"Error during keyboard unhooking: {uh_e}")
        elif not listener_success:
             print("Skipping keyboard unhooking as listener setup failed.")
        else: # keyboard library wasn't loaded
             print("Skipping keyboard unhooking as library wasn't loaded.")

        print("Exiting.")


if __name__ == "__main__":
    print("======================================================")
    print("= Gemini Knowledge MC Solver (Setup & Run)         =")
    print("======================================================")

    # === Phase 1: Setup Checks ===
    if not check_windows():
        sys.exit(1)

    # Check admin privileges (warns but doesn't exit)
    check_admin_privileges()

    if not check_python_version():
        sys.exit(1)

    if not install_libraries():
        print("\nSetup failed: Required libraries could not be installed or loaded.")
        print("Please address the errors above and try again.")
        sys.exit(1)

    if not configure_api_key():
         print("\nSetup failed: API Key could not be configured.")
         print("Please address the errors above (check permissions, manually create .env if needed).")
         sys.exit(1)

    print("\n--- Setup Phase Complete ---")

    # === Phase 2: Run Main Application ===
    # All checks passed, libraries installed/loaded, API key configured.
    run_main_application()
