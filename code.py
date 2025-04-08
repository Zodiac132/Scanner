# UTIL.py (Source code for GitHub - WITHOUT Google API Key definition)
# The checker script will inject the GOOGLE_API_KEY variable before running.

import sys
import os
import platform
import subprocess
import importlib
# import ctypes # No longer checking admin privileges within this script
import time
import threading
import signal
import io
import traceback # Keep traceback for debugging errors

# --- Attempt to Import Core Libraries ---
try:
    import keyboard
    import mss
    import mss.tools
    from PIL import Image
    import google.generativeai as genai
    import google.api_core.exceptions
except ImportError as e:
    # This message will appear if the .bat install failed or wasn't run
    print(f"Info: Initial import failed for '{e.name}'. Setup will attempt installation/verification.")
    # Define placeholders only if essential for setup phase (less likely now)
    # We rely on the install_libraries function to handle missing libs.

# --- Configuration ---
# GOOGLE_API_KEY will be injected here by the checker script if authentication succeeds
# Example line that gets injected:
# GOOGLE_API_KEY = "AIzaSy..." # Injected by checker

# Setup Config
# List of libraries needed by THIS script (UTIL.py)
REQUIRED_LIBRARIES = [
    "keyboard",
    "mss",
    "Pillow",         # Note: Imported as PIL
    "google-generativeai",
    # python-dotenv REMOVED
]

# Main App Config
TRIGGER_KEY = '='
TOGGLE_KEY = 'caps lock'
SUPPRESS_TRIGGER = True # Prevent '=' from being typed
AI_MODEL_NAME = "gemini-1.5-flash-latest" # Use the latest flash model

# Caps Lock Signaling Config
SIGNAL_BASE = {'A': 1, 'B': 2, 'C': 3, 'D': 4, 'E': 5, 'F': 6}
SIGNAL_ON_DURATION = 0.15
SIGNAL_OFF_DURATION = 0.15
PAUSE_BETWEEN_SIGNALS = 0.5

# --- State ---
process_lock = threading.Lock()
running = True # Flag for graceful shutdown

# === SETUP FUNCTIONS ===

def check_windows():
    """Checks if running on Windows."""
    print("--- Checking Operating System ---")
    if platform.system() != "Windows":
        print(f"ERROR: This script is designed ONLY for Windows. Detected OS: {platform.system()}. Exiting.")
        return False
    print("Operating System: Windows (OK).")
    return True

# --- check_admin_privileges function REMOVED ---
# This script no longer performs its own admin check. It relies on the launcher's status.

def check_python_version():
    """Checks if Python 3.8+ is being used."""
    print("\n--- Checking Python Version ---")
    if sys.version_info < (3, 8):
        print(f"ERROR: Python 3.8+ recommended. You are using {platform.python_version()}. Exiting.")
        return False
    print(f"Python version {platform.python_version()} is sufficient.")
    return True

def install_libraries():
    """Verifies required libraries are installed (should have been done by launcher)."""
    # This function now mostly serves as a verification step.
    print("\n--- Verifying Required Libraries ---")
    missing_libs = []
    for lib in REQUIRED_LIBRARIES: # Uses list without dotenv
        try:
            import_name = lib
            if lib == 'Pillow': import_name = 'PIL'
            elif lib == 'google-generativeai': import_name = 'google.generativeai'
            spec = importlib.util.find_spec(import_name)
            if spec is None:
                 missing_libs.append(lib)
                 print(f"- '{lib}' NOT FOUND.")
            else:
                 print(f"- '{lib}' found.")
        except Exception as e:
             print(f"  Warning: Error checking for library '{lib}': {e}")
             # Assume missing if error occurs during check
             if lib not in missing_libs: missing_libs.append(lib)

    if not missing_libs:
        print("All required libraries appear to be installed.")
        # Final import check to be sure
        try:
            global keyboard, mss, mss_tools, Image, genai, google_api_core_exceptions
            import keyboard
            import mss
            import mss.tools as mss_tools
            from PIL import Image
            import google.generativeai as genai
            import google.api_core.exceptions as google_api_core_exceptions
            print("Core libraries imported successfully.")
            return True
        except ImportError as e:
             print(f"ERROR: Library '{e.name}' found but failed to import. Installation might be corrupted.", file=sys.stderr)
             return False
    else:
        # If libraries are missing here, the launcher's .bat likely failed.
        print(f"\nERROR: Required libraries are missing: {', '.join(missing_libs)}", file=sys.stderr)
        print("The initial installation process via the launcher might have failed.", file=sys.stderr)
        print("Please ensure the launcher ran correctly and check its console output.", file=sys.stderr)
        return False

# --- configure_api_key function REMOVED ---

# === MAIN APPLICATION FUNCTIONS ===
# (signal_answer_with_capslock, get_answer_from_ai_knowledge,
#  process_screenshot_and_get_answer, handle_trigger, signal_handler)

def signal_answer_with_capslock(answer_letter):
    """Signals the answer letter using Caps Lock flashes."""
    global running, keyboard # Ensure keyboard is accessible
    answer_upper = answer_letter.upper()
    if answer_upper not in SIGNAL_BASE:
        print(f"Cannot signal answer '{answer_letter}'. Not defined.")
        return

    num_flashes = SIGNAL_BASE[answer_upper]
    print(f"Signaling answer: {answer_upper} ({num_flashes} flashes)...")

    # Check if keyboard module is loaded before trying to use it
    if keyboard is None:
        print("ERROR: Keyboard library not loaded. Cannot signal.", file=sys.stderr)
        return

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
        print(f"Error during Caps Lock signaling: {e}", file=sys.stderr)
        print("Ensure the LAUNCHER script was run with sufficient permissions (Administrator often needed).", file=sys.stderr)

def get_answer_from_ai_knowledge(pil_image):
    """Sends image to Gemini, asks it to READ the question and use KNOWLEDGE."""
    global running, genai, google_api_core_exceptions, GOOGLE_API_KEY # Use injected global key

    print(f"Asking AI ({AI_MODEL_NAME})...")
    if not running: return None

    # --- Check if GOOGLE_API_KEY was injected ---
    try:
         # Check if GOOGLE_API_KEY exists as a global and is not empty/placeholder
         if 'GOOGLE_API_KEY' not in globals() or not GOOGLE_API_KEY or GOOGLE_API_KEY == "YOUR_GOOGLE_API_KEY_HERE":
             raise NameError("GOOGLE_API_KEY not defined or invalid")
    except NameError:
         print("\n!!! FATAL ERROR (UTIL.py): GOOGLE_API_KEY variable not found or invalid !!!", file=sys.stderr)
         print("   This means the checker script failed to inject the key correctly.", file=sys.stderr)
         return None

    if genai is None or google_api_core_exceptions is None:
        print("ERROR: Google AI library not loaded correctly.", file=sys.stderr)
        return None

    try:
        model = genai.GenerativeModel(AI_MODEL_NAME)
    except Exception as e:
        print(f"ERROR: Failed to initialize Gemini model '{AI_MODEL_NAME}': {e}", file=sys.stderr)
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
        print(f" - Sending image prompt to Gemini...")
        response = model.generate_content(
            [prompt, pil_image],
            generation_config=genai.types.GenerationConfig(temperature=0.0),
            request_options={'timeout': 90} # Increased timeout
        )

        if not response.candidates:
             # Simplified blocking check - more detail could be added if needed
             print(f"ERROR: Gemini response was empty or blocked.", file=sys.stderr)
             try: print(f"   Prompt Feedback: {response.prompt_feedback}", file=sys.stderr)
             except Exception: pass
             return None

        ai_response_text = response.text.strip().upper()
        print(f"AI raw: '{response.text.strip()}' -> Processed: '{ai_response_text}'")

        if ai_response_text in SIGNAL_BASE: return ai_response_text
        elif ai_response_text == "ERROR": print(" - AI responded with ERROR."); return None
        else:
             # Check if it's just a single valid letter not in SIGNAL_BASE
             if len(ai_response_text) == 1 and 'A' <= ai_response_text <= 'Z':
                  print(f" - AI gave single letter '{ai_response_text}' not in defined signals {list(SIGNAL_BASE.keys())}.")
             else:
                  print(f" - AI gave unexpected response: '{response.text.strip()}'")
             return None # Don't signal unexpected responses

    except google_api_core_exceptions.PermissionDenied as e:
         print(f"ERROR querying Google Gemini API: Permission Denied.", file=sys.stderr)
         print(f"   Check the injected GOOGLE_API_KEY and ensure the Gemini API is enabled.", file=sys.stderr)
         print(f"   Error details: {e}", file=sys.stderr)
         return None
    # Keep other specific Google API errors if desired
    except google_api_core_exceptions.ResourceExhausted as e: print(f"ERROR Gemini API: Quota Exceeded. {e}", file=sys.stderr); return None
    except google_api_core_exceptions.DeadlineExceeded as e: print(f"ERROR Gemini API: Timeout. {e}", file=sys.stderr); return None
    except google_api_core_exceptions.InvalidArgument as e: print(f"ERROR Gemini API: Invalid Argument (Bad image/prompt?). {e}", file=sys.stderr); return None
    except Exception as e:
        print(f"Error during Gemini API call: {type(e).__name__}: {e}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr) # Print traceback for unexpected errors
        return None

def process_screenshot_and_get_answer():
    """Takes screenshot, asks AI KNOWLEDGE, signals answer."""
    global running, mss, Image, keyboard # Ensure keyboard is accessible
    screenshot_pil_img=None; start_time = time.time()

    # Check for libs
    if mss is None or Image is None: print("ERROR: mss or Pillow library not loaded.", file=sys.stderr); return
    if keyboard is None: print("ERROR: keyboard library not loaded.", file=sys.stderr); return

    try:
        print("Taking screenshot...")
        with mss.mss() as sct:
            # Simple monitor selection (primary usually index 1, fallback 0)
            monitor = sct.monitors[1] if len(sct.monitors) > 1 else sct.monitors[0] if sct.monitors else None
            if not monitor: print("FATAL: No monitors detected by mss.", file=sys.stderr); return
            print(f" - Using monitor: {monitor}")
            sct_img = sct.grab(monitor)
            print(f" - Captured ({sct_img.width}x{sct_img.height}).")
            screenshot_pil_img = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")
            print(" - Image converted.")
    except mss.ScreenShotError as e:
         print(f"Error taking screenshot with mss: {e}", file=sys.stderr)
         return
    except Exception as e:
         print(f"Error preparing screenshot: {e}", file=sys.stderr)
         traceback.print_exc(file=sys.stderr)
         return

    if not running: print(" - Interrupted during screenshot."); return
    if screenshot_pil_img is None: print(" - Screenshot failed."); return

    # Get answer from AI
    answer = get_answer_from_ai_knowledge(screenshot_pil_img) # Key check happens inside here

    if not running: print(" - Interrupted after AI call."); return

    # Signal if answer received
    if answer:
        signal_answer_with_capslock(answer)
    else:
        print("No valid answer received from AI to signal.")

    print(f"Processing finished in {time.time() - start_time:.2f} seconds.")


def handle_trigger():
    """Called when trigger key is pressed (if listener works)."""
    global running, process_lock
    if not running: return
    # Attempt to acquire lock without blocking
    if process_lock.acquire(blocking=False):
        print(f"\n'{TRIGGER_KEY}' detected. Starting screenshot analysis...")
        # Run processing in a separate thread
        thread = threading.Thread(target=process_screenshot_and_get_answer, daemon=True)
        thread.start()
    else:
        # Already processing, ignore this trigger
        print(f"'{TRIGGER_KEY}' detected, but already processing. Please wait.")

def signal_handler(sig, frame):
    """Handles Ctrl+C for graceful shutdown."""
    global running
    if running:
        print("\nShutdown signal (Ctrl+C) received. Cleaning up...")
        running = False
        # Allow main loop to exit naturally

# === MAIN EXECUTION BLOCK ===
def run_main_application():
    """Contains the main application logic after setup is complete."""
    global running, genai, GOOGLE_API_KEY, keyboard # Use injected global key & keyboard

    print("\n--- Starting Gemini Knowledge MC Solver (UTIL.py) ---")

    # --- Configure Google AI (using the *injected* key) ---
    try:
        # Check if key exists (was injected)
        if 'GOOGLE_API_KEY' not in globals() or not GOOGLE_API_KEY:
            raise NameError("GOOGLE_API_KEY was not injected by the checker script.")
        if genai is None: raise ImportError("Google GenAI lib not loaded.")
        print(f"Configuring Google AI SDK...") # Don't print key
        genai.configure(api_key=GOOGLE_API_KEY) # Use the injected key
        print("Google AI SDK configured.")
    except NameError as e:
         print(f"!!! FATAL ERROR: {e} !!!", file=sys.stderr)
         return # Exit if key wasn't injected
    except ImportError as e:
        print(f"ERROR: Failed to import Google AI library for config: {e}", file=sys.stderr)
        return
    except Exception as e:
        print(f"ERROR: Failed to configure Google AI SDK: {e}", file=sys.stderr)
        if "API key not valid" in str(e):
            print("   >>> The injected API key seems invalid. Check the key in the LAUNCHER script. <<<", file=sys.stderr)
        return

    # --- Setup Signal Handler ---
    signal.signal(signal.SIGINT, signal_handler)
    print("\nCtrl+C handler set.")

    # --- Setup Keyboard Listener ---
    listener_success = False
    try:
        if keyboard is None:
            raise ImportError("'keyboard' library not loaded/available.")

        # --- ADDED WARNING ---
        print("\n" + "*"*60)
        print("WARNING: Attempting to set up global keyboard listener.")
        print("         If the launcher was NOT run as Administrator, this step")
        print(f"         will likely FAIL silently. The trigger key ('{TRIGGER_KEY}') may")
        print("         not be detected even if the script continues running.")
        print("*"*60)
        # --- END ADDED WARNING ---

        print("Setting up keyboard listener...")
        # Use add_hotkey for specific trigger
        keyboard.add_hotkey(
            TRIGGER_KEY,
            handle_trigger,
            trigger_on_release=False, # Trigger on press
            suppress=SUPPRESS_TRIGGER
        )
        print(f"Listener active (or attempted). Ready for '{TRIGGER_KEY}' key press.") # Worded carefully
        listener_success = True

        # --- Main Loop ---
        print("Entering main loop (waiting for trigger or Ctrl+C)...")
        while running:
            time.sleep(0.5) # Keep main thread alive, periodically check 'running' flag

    except ImportError as e:
        print(f"\nERROR: Required library '{e.name}' is not available.", file=sys.stderr)
        print("   Installation by the launcher might have failed.", file=sys.stderr)
        running = False # Ensure cleanup runs if possible
    except Exception as e:
        print(f"\nERROR during keyboard listener setup or main loop: {type(e).__name__}: {e}", file=sys.stderr)
        # Check specifically for the kind of error keyboard might raise without permissions
        if isinstance(e, OSError) or "permissions" in str(e).lower() or "Administrator" in str(e):
             print("\n>>> FAILURE LIKELY DUE TO MISSING ADMIN PERMISSIONS FOR KEYBOARD HOOKS. <<<", file=sys.stderr)
             print(">>> Please run the main LAUNCHER script as Administrator for the trigger key to work. <<<", file=sys.stderr)
        else:
             # Print full traceback for other unexpected errors
             print("Traceback:", file=sys.stderr)
             traceback.print_exc(file=sys.stderr)
        running = False # Stop loop on error
    finally:
        # --- Cleanup ---
        print("\n--- Script Stopping (UTIL.py) ---")
        if running: # If loop exited unexpectedly (should be false now)
             running = False
             print("Exiting loop unexpectedly...")

        # Ensure the running flag is False so threads can see it
        running = False

        # Release processing lock if held
        if process_lock.locked():
            print("Releasing process lock...")
            try: process_lock.release()
            except Exception as lock_err: print(f" - Warn: Error releasing lock: {lock_err}") # Don't crash on cleanup error

        # Wait briefly for background threads (like screenshot/AI) to notice 'running = False'
        print("Waiting briefly for background tasks...")
        time.sleep(0.5) # Short wait

        print("Cleaning up keyboard hooks (if setup succeeded)...")
        # Only unhook if setup succeeded AND keyboard module is loaded
        if listener_success and keyboard:
            try:
                keyboard.unhook_all()
                print("Keyboard hooks removed.")
            except Exception as uh_e:
                # Log error but don't crash the exit process
                print(f" - Warn: Error during keyboard unhooking: {uh_e}", file=sys.stderr)
        elif not listener_success:
             print(" - Skipping keyboard unhooking as listener setup failed or was interrupted.")
        else: # keyboard library wasn't loaded
             print(" - Skipping keyboard unhooking as library wasn't loaded.")

        print("Exiting UTIL.py.")


# --- Script Entry Point (`if __name__ == "__main__":`) ---
if __name__ == "__main__":
    print("="*54)
    print("= Gemini Knowledge MC Solver (UTIL.py - Launched by Checker) =")
    print("="*54)

    # === Phase 1: Setup Checks ===
    if not check_windows(): sys.exit(1)
    # --- Admin check REMOVED from here ---
    if not check_python_version(): sys.exit(1)
    if not install_libraries(): # This now mostly verifies installation
        print("\nSetup failed: Required libraries check failed.", file=sys.stderr)
        sys.exit(1)

    # --- API Key Configuration Step REMOVED ---

    print("\n--- Setup Phase Complete (UTIL.py) ---")

    # === Phase 2: Run Main Application ===
    # It will check for the injected GOOGLE_API_KEY inside run_main_application
    run_main_application()
