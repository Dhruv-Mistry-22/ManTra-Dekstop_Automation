# modules/text_input_assistant.py
import pyautogui
import time

# CRITICAL: Disable PyAutoGUI fail-safe so commands don't abort
# when the mouse is near a screen corner.
pyautogui.FAILSAFE = False

def type_text(text):
    """Type text into the active application"""
    try:
        time.sleep(0.4)
        # Use keyboard lib for unicode support, fallback to pyautogui
        try:
            import keyboard
            keyboard.write(text, delay=0.04)
        except Exception:
            pyautogui.typewrite(str(text), interval=0.05)
        return f"Typed: {text}"
    except Exception as e:
        return f"Failed to type text: {e}"

def insert_predefined_text(preset_type):
    """Insert predefined text snippets"""
    presets = {
        "email":     "Thank you for your message. I will get back to you soon.",
        "greeting":  "Hello! How are you today?",
        "signature": "Best regards",
        "date":      __get_current_date(),
        "time":      __get_current_time()
    }
    try:
        text = presets.get(preset_type.lower(), None)
        if text:
            time.sleep(0.4)
            try:
                import keyboard
                keyboard.write(text, delay=0.04)
            except Exception:
                pyautogui.typewrite(text, interval=0.02)
            return f"Inserted preset: {preset_type}"
        return f"Unknown preset type: {preset_type}"
    except Exception as e:
        return f"Failed to insert preset text: {e}"

def copy_text():
    """Copy selected text to clipboard"""
    try:
        try:
            import keyboard
            keyboard.send("ctrl+c")
        except Exception:
            pyautogui.hotkey("ctrl", "c")
        time.sleep(0.2)
        return "Text copied."
    except Exception as e:
        return f"Failed to copy text: {e}"

def paste_text():
    """Paste clipboard text into active application"""
    try:
        try:
            import keyboard
            keyboard.send("ctrl+v")
        except Exception:
            pyautogui.hotkey("ctrl", "v")
        time.sleep(0.2)
        return "Text pasted."
    except Exception as e:
        return f"Failed to paste text: {e}"

def select_all():
    """Select all text in active application"""
    try:
        try:
            import keyboard
            keyboard.send("ctrl+a")
        except Exception:
            pyautogui.hotkey("ctrl", "a")
        time.sleep(0.2)
        return "All text selected."
    except Exception as e:
        return f"Failed to select all: {e}"

def undo_action():
    """Undo last action"""
    try:
        try:
            import keyboard
            keyboard.send("ctrl+z")
        except Exception:
            pyautogui.hotkey("ctrl", "z")
        time.sleep(0.2)
        return "Action undone."
    except Exception as e:
        return f"Failed to undo: {e}"

def redo_action():
    """Redo last action"""
    try:
        try:
            import keyboard
            keyboard.send("ctrl+y")
        except Exception:
            pyautogui.hotkey("ctrl", "y")
        time.sleep(0.2)
        return "Action redone."
    except Exception as e:
        return f"Failed to redo: {e}"

def __get_current_date():
    from datetime import datetime
    return datetime.now().strftime("%B %d, %Y")

def __get_current_time():
    from datetime import datetime
    return datetime.now().strftime("%I:%M %p")
