# UTIL.py (formerly combined_mc_solver.py)
# Modified to use a HARDCODED API key.
# REMEMBER TO REPLACE "YOUR_API_KEY_HERE" IN THE CONFIG SECTION BELOW
# before uploading this file to your GitHub repository.

import sys
import os
import platform
import subprocess
import importlib
import ctypes
import time
import threading
import signal
import io

# --- Attempt to Import Core Libraries ---
try:
    import keyboard
    import mss
    import mss.tools
    from PIL import Image
    # python-dotenv is NO LONGER NEEDED
    import google.generativeai as genai
    import google.api_core.exceptions
except ImportError as e:
    print(f"Info: Initial import failed for '{e.name}'. Setup will attempt installation.")
    # No need for dotenv placeholders

# --- Configuration ---
# !!! IMPORTANT: REPLACE WITH YOUR ACTUAL GOOGLE AI API KEY BELOW !!!
# !!! WARNING: THIS KEY WILL BE VISIBLE IN YOUR PUBLIC GITHUB REPO !!!
GOOGLE_API_KEY = "AIzaSyC4acqyS_WwxhQNMNnuPP-cISu0tV43-Dg"
# !!! Make sure the key above is correct and does not contain quotes within the key itself !!!

# Setup Config
REQUIRED_LIBRARIES = [
    "keyboard",
    "mss",
    "Pillow",
    "google-generativeai",
    # python-dotenv REMOVED from requirements
]
# ENV_FILE_NAME REMOVED
# API_KEY_NAME REMOVED

# Main App Config
TRIGGER_KEY = '='
TOGGLE_KEY = 'caps lock'
SUPPRESS_TRIGGER = True

# AI Config
# GOOGLE_API_KEY is now defined above
AI_MODEL_NAME = "gemini-1.5-flash-latest"

# Caps Lock Signaling Config
SIGNAL_BASE = {'A': 1, 'B': 2, 'C': 3, 'D': 4, 'E': 5, 'F': 6}
SIGNAL_ON_DURATION = 0.15
SIGNAL_OFF_DURATION = 0.15
PAUSE_BETWEEN_SIGNALS = 0.5

# --- State ---
process_lock = threading.Lock()
running = True

# === SETUP FUNCTIONS ===
# check_windows, check_admin_privileges, check_python_version remain the same
def check_windows():
    print("--- Checking Operating System ---")
    if platform.system() != "Windows":
        print(f"ERROR: Windows only. Detected: {platform.system()}. Exiting.")
        return False
    print("Operating System: Windows (OK).")
    return True

def check_admin_privileges():
    print("\n--- Checking Administrator Privileges ---")
    is_admin = False
    try: is_admin = ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception as e: print(f"  Warning: Could not check admin status: {e}")
    if is_admin: print("- Running as Administrator (Required).")
    else: print("! CRITICAL WARNING: NOT running as Administrator. Keyboard hooks will likely FAIL.")
    return True

def check_python_version():
    print("\n--- Checking Python Version ---")
    if sys.version_info < (3, 8):
        print(f"ERROR: Python 3.8+ required. Found: {platform.python_version()}. Exiting.")
        return False
    print(f"Python version {platform.python_version()} OK.")
    return True

def install_libraries():
    # Modified to remove python-dotenv
    print("\n--- Checking and Installing Libraries ---")
    missing_libs = []
    for lib in REQUIRED_LIBRARIES: # Uses the updated list
        try:
            import_name = lib
            if lib == 'Pillow': import_name = 'PIL'
            elif lib == 'google-generativeai': import_name = 'google.generativeai'
            spec = importlib.util.find_spec(import_name)
            if spec is None: missing_libs.append(lib); print(f"- '{lib}' not found.")
            else: print(f"- '{lib}' found.")
        except Exception as e: print(f"  Warn: Error check lib '{lib}': {e}"); missing_libs.append(lib)

    if not missing_libs:
        print("All required libraries appear installed.")
        try: # Re-import check
            global keyboard, mss, mss_tools, Image, genai, google_api_core_exceptions
            import keyboard, mss, mss.tools as mss_tools
            from PIL import Image
            import google.generativeai as genai
            import google.api_core.exceptions as google_api_core_exceptions
            print("Successfully re-imported core libraries.")
            return True
        except ImportError as e: print(f"ERROR: Lib '{e.name}' installed but failed import."); return False

    print(f"Attempting install: {', '.join(missing_libs)}")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", *missing_libs],
                              stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        print(f"Installed missing libraries.")
        print("Reloading libraries...")
        global keyboard, mss, mss_tools, Image, genai, google_api_core_exceptions
        importlib.invalidate_caches()
        import keyboard, mss, mss.tools as mss_tools
        from PIL import Image
        import google.generativeai as genai
        import google.api_core.exceptions as google_api_core_exceptions
        print("Loaded libraries after install.")
        return True
    except subprocess.CalledProcessError as e:
        stderr_output = e.stderr.decode('utf-8', errors='replace').strip() if e.stderr else "No stderr."
        print(f"ERROR: pip install failed. Stderr: {stderr_output}"); return False
    except ImportError as e: print(f"ERROR: Import failed for '{e.name}' after install."); return False
    except Exception as e: print(f"Unexpected install/reload error: {e}"); return False

# --- configure_api_key FUNCTION ENTIRELY REMOVED ---

# === MAIN APPLICATION FUNCTIONS ===
# signal_answer_with_capslock, get_answer_from_ai_knowledge,
# process_screenshot_and_get_answer, handle_trigger, signal_handler
# remain exactly the same as before.
# Copy them here...

def signal_answer_with_capslock(answer_letter):
    """Signals the answer letter using Caps Lock flashes."""
    global running
    answer_upper = answer_letter.upper() # Convert once
    if answer_upper not in SIGNAL_BASE:
        print(f"Cannot signal answer '{answer_letter}'. Not defined in SIGNAL_BASE.")
        return
    num_flashes = SIGNAL_BASE[answer_upper]
    print(f"Signaling answer: {answer_upper} ({num_flashes} flashes) based on AI knowledge.")
    try:
        for i in range(num_flashes):
            if not running: print(" - Signaling interrupted."); break
            keyboard.press_and_release(TOGGLE_KEY)
            time.sleep(SIGNAL_ON_DURATION)
            if not running: break
            keyboard.press_and_release(TOGGLE_KEY)
            time.sleep(SIGNAL_OFF_DURATION)
            if i < num_flashes - 1: time.sleep(PAUSE_BETWEEN_SIGNALS)
        print(f"Finished signaling '{answer_upper}'.")
    except Exception as e:
        print(f"Error during Caps Lock signaling: {e}")
        print("Ensure script has keyboard control (run launcher as Admin).")

def get_answer_from_ai_knowledge(pil_image):
    """Sends image to Gemini, asks it to READ the question and use KNOWLEDGE."""
    global running, genai, google_api_core_exceptions, GOOGLE_API_KEY # Need API key global
    print(f"Asking AI ({AI_MODEL_NAME}) to read image and apply knowledge...")
    if not running: return None
    if GOOGLE_API_KEY == "YOUR_API_KEY_HERE" or not GOOGLE_API_KEY:
         print("!!! FATAL ERROR: GOOGLE_API_KEY is not set correctly in the UTIL.py source code !!!")
         return None
    if genai is None or google_api_core_exceptions is None:
        print("ERROR: Google AI library not loaded correctly.")
        return None
    try:
        model = genai.GenerativeModel(AI_MODEL_NAME)
    except Exception as model_err:
        print(f"ERROR: Failed to initialize Gemini model '{AI_MODEL_NAME}': {model_err}")
        return None
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
            [prompt, pil_image],
            generation_config=genai.types.GenerationConfig(temperature=0.0),
            request_options={'timeout': 90}
        )
        ai_response_text = ""
        if not response.candidates:
             block_reason="Unknown"; safety_ratings="N/A"
             try:
                 if hasattr(response, 'prompt_feedback') and response.prompt_feedback:
                     block_reason=response.prompt_feedback.block_reason; safety_ratings=response.prompt_feedback.safety_ratings
             except Exception: pass
             print(f"ERROR: Gemini response empty/blocked. Reason: {block_reason}, Safety: {safety_ratings}")
             return None
        try: ai_response_text = response.text
        except Exception as resp_err: print(f"ERROR: Could not extract text: {resp_err}"); return None

        ai_response_text_processed = ai_response_text.strip().upper()
        print(f"AI raw response: '{ai_response_text.strip()}' -> Processed: '{ai_response_text_processed}'")

        if ai_response_text_processed in SIGNAL_BASE: return ai_response_text_processed
        elif ai_response_text_processed == "ERROR": print(" - AI responded with ERROR."); return None
        else:
             potential_letters = [char for char in ai_response_text_processed if char in SIGNAL_BASE]
             if len(potential_letters) == 1: print(f" - Warn: AI extra text. Extracted: {potential_letters[0]}"); return potential_letters[0]
             else: print(f" - AI unexpected response: '{ai_response_text.strip()}'"); return None
    except google_api_core_exceptions.PermissionDenied as e: print(f"ERROR Gemini API: Permission Denied (Check hardcoded GOOGLE_API_KEY / API enabled?). {e}"); return None
    except Exception as e: print(f"Error during Gemini API call: {type(e).__name__}: {e}"); return None # Other errors remain

def process_screenshot_and_get_answer():
    """Takes screenshot, asks AI KNOWLEDGE, signals answer."""
    global running, mss, Image
    screenshot_pil_img=None; start_time = time.time()
    if mss is None or Image is None: print("ERROR: Screenshot libs not loaded."); return
    try:
        print("Taking screenshot...")
        with mss.mss() as sct:
            monitor = sct.monitors[1] if len(sct.monitors) > 1 else sct.monitors[0] if sct.monitors else None
            if not monitor: print("FATAL: No monitors."); return
            print(f" - Using monitor: {monitor}")
            sct_img = sct.grab(monitor)
            print(f" - Screenshot captured ({sct_img.width}x{sct_img.height}).")
            screenshot_pil_img = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")
            print(" - Image converted for AI.")
        if not running or screenshot_pil_img is None: print(" - Interrupted/screenshot fail."); return
        answer = get_answer_from_ai_knowledge(screenshot_pil_img) # API key check happens inside here now
        if not running: print(" - Interrupted after AI call."); return
        if answer: signal_answer_with_capslock(answer)
        else: print("No valid answer from AI / interrupted.")
    except Exception as e: print(f"Error in screenshot processing: {type(e).__name__}: {e}"); traceback.print_exc()
    finally:
        if process_lock.locked():
             try: process_lock.release()
             except Exception: pass
        print(f"Processing finished in {time.time() - start_time:.2f} seconds.")

def handle_trigger():
    """Called when trigger key is pressed."""
    global running
    if not running: return
    if not process_lock.locked():
        if process_lock.acquire(blocking=False):
            print(f"\n'{TRIGGER_KEY}' detected. Starting analysis...")
            thread = threading.Thread(target=process_screenshot_and_get_answer, daemon=True); thread.start()
    else: print(f"'{TRIGGER_KEY}' detected, already processing.")

def signal_handler(sig, frame):
    """Handles Ctrl+C."""
    global running
    if running: print("\nShutdown signal received..."); running = False


# === MAIN EXECUTION BLOCK ===

def run_main_application():
    """Contains the main application logic after setup is complete."""
    global running, genai, GOOGLE_API_KEY # Make GOOGLE_API_KEY global

    print("\n--- Starting Gemini Knowledge MC Solver (UTIL.py) ---")
    # --- Check if API Key is still the placeholder ---
    if GOOGLE_API_KEY == "YOUR_API_KEY_HERE" or not GOOGLE_API_KEY:
         print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
         print("!!! FATAL ERROR: GOOGLE_API_KEY is not set in this script's source code! !!!")
         print("!!! You must edit the code.py on GitHub to include your real API key.  !!!")
         print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
         return # Cannot proceed without the key

    print(f"Press '{TRIGGER_KEY}' to trigger analysis.")
    print(f"Using AI Model: {AI_MODEL_NAME}")
    print(f"Signaling via '{TOGGLE_KEY}'")
    print(f"Press Ctrl+C in console to stop.")

    # --- Load API Key Step REMOVED (no .env reading) ---

    # --- Configure Google AI (using the hardcoded key) ---
    try:
        if genai is None: raise ImportError("Google GenAI lib not loaded.")
        print(f"Configuring Google AI SDK with hardcoded key...") # Don't print the key!
        # Use the GOOGLE_API_KEY constant directly
        genai.configure(api_key=GOOGLE_API_KEY)
        print("Google AI SDK configured successfully.")
    except ImportError as e:
         print(f"ERROR: Failed to import Google AI library for config: {e}")
         return
    except Exception as e:
        print(f"ERROR: Failed to configure Google AI SDK.")
        print(f"   Error details: {e}")
        if "API key not valid" in str(e):
            print("   >>> Check the hardcoded GOOGLE_API_KEY value in the script source. <<<")
        return

    # --- Setup Signal Handler ---
    signal.signal(signal.SIGINT, signal_handler)
    print("\nCtrl+C handler set.")

    # --- Setup Keyboard Listener ---
    listener_success = False
    try:
        if keyboard is None: raise ImportError("'keyboard' lib not loaded.")
        print("Setting up keyboard listener...")
        keyboard.add_hotkey(
            TRIGGER_KEY, handle_trigger, trigger_on_release=False, suppress=SUPPRESS_TRIGGER
        )
        print(f"Listener active. Ready for '{TRIGGER_KEY}'.")
        listener_success = True

        print("Entering main loop...")
        while running:
            time.sleep(0.5)

    except ImportError as e: print(f"\nERROR: Required lib '{e.name}' unavailable."); running = False
    except Exception as e:
        print(f"\nERROR during listener setup/main loop: {type(e).__name__}: {e}")
        if "permissions" in str(e).lower() or "administrator" in str(e).lower() or isinstance(e, OSError) and e.winerror == 5:
             print("\n>>> ERROR LIKELY MISSING ADMIN PERMISSIONS. Ensure LAUNCHER ran as admin. <<<")
        else: print("\nUnexpected error."); traceback.print_exc()
        running = False
    finally:
        # --- Cleanup ---
        print("\n--- Script Stopping ---")
        running = False
        if process_lock.locked(): print("Releasing lock..."); process_lock.release()
        time.sleep(0.1) # Brief pause
        print("Cleaning up keyboard hooks...")
        if listener_success and keyboard:
            try: keyboard.unhook_all()
            except Exception: pass # Ignore errors here
        print("Exiting UTIL.py.")


if __name__ == "__main__":
    print("======================================================")
    print("= Gemini Knowledge MC Solver (UTIL.py - Launched)  =")
    print("======================================================")

    # === Phase 1: Setup Checks ===
    if not check_windows(): sys.exit(1)
    if not check_admin_privileges(): pass
    if not check_python_version(): sys.exit(1)
    if not install_libraries(): sys.exit(1) # Libraries are still needed

    # --- API Key Config Step REMOVED ---

    print("\n--- Setup Phase Complete (UTIL.py) ---")

    # === Phase 2: Run Main Application ===
    run_main_application() # This now uses the hardcoded key
