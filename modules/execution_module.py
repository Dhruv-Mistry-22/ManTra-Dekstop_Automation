# modules/execution_module.py
from modules.app_controller import open_or_switch_app, close_app, list_running_apps, get_active_window
from modules.file_manager import (
    create_file, create_folder, open_file, open_folder,
    rename_file, rename_folder, delete_file, delete_folder,
    search_files, move_file, list_files,
    list_desktop_files, undo_last_creation
)
from modules.system_control import (
    shutdown_system, restart_system, lock_system, logout_user,
    sleep_system, increase_volume, decrease_volume, mute_volume, get_system_info
)
from modules.text_input_assistant import (
    type_text, insert_predefined_text, copy_text, paste_text,
    select_all, undo_action, redo_action
)
from modules.db_manager import save_macro, get_macro, list_macros as db_list_macros
import subprocess
import threading

# ── MemoryBank (NEW) ──────────────────────────────────────────────────────────
from core.context_memory import MemoryBank
memory = MemoryBank()          # singleton shared across all execute_task() calls

# Pronoun tokens that trigger memory resolution instead of literal matching
_PRONOUN_TOKENS: frozenset[str] = frozenset({
    "it", "that",
    "the file", "that file",
    "the app",  "that app",
    "the folder", "that folder",
    "the command", "that command",
})


def _resolve_keywords(keywords: list[str]) -> tuple[list[str], bool]:
    """Replace any pronoun token in *keywords* with the remembered entity value.

    Joins the keyword list into a single string, checks whether it is a known
    pronoun phrase, resolves it via ``memory.resolve_pronoun``, and returns
    the updated keyword list together with a flag indicating whether an
    *unresolvable* pronoun was encountered.

    Returns:
        (resolved_keywords, unresolvable)
        - resolved_keywords : list[str] ready for routing
        - unresolvable      : True when a pronoun was detected but memory
                              returned None (nothing remembered yet)
    """
    joined = " ".join(keywords).strip().lower()
    if joined in _PRONOUN_TOKENS:
        resolved = memory.resolve_pronoun(joined)
        if resolved is None:
            return keywords, True          # pronoun found but no memory
        return [resolved], False           # pronoun successfully substituted
    # Also check individual tokens for simple "it" / "that"
    new_keywords: list[str] = []
    for kw in keywords:
        if kw.strip().lower() in {"it", "that"}:
            resolved = memory.resolve_pronoun(kw)
            if resolved is None:
                return keywords, True      # unresolvable
            new_keywords.append(resolved)
        else:
            new_keywords.append(kw)
    return new_keywords, False
# ── End MemoryBank additions ──────────────────────────────────────────────────

# ── Macro recorder state ─────────────────────────────────────────────────────
_macro_recording   = False
_macro_events      = []
_macro_listener    = None
_macro_start_time  = None

def remove_action_keyword(keywords, action_words):
    """Remove action keywords from keywords list"""
    return [k for k in keywords if k.lower() not in action_words]


# ── Filename / foldername extraction helpers ──────────────────────────────────

_FILE_FILLER = {
    "create", "make", "new", "file", "called", "named",
    "call", "name", "a", "an", "the", "empty", "blank",
    "text", "document", "generate", "build", "please",
}

_FOLDER_FILLER = {
    "create", "make", "new", "folder", "directory", "dir",
    "called", "named", "call", "name", "a", "an", "the", "mkdir",
}

import re as _re

def _extract_filename(keywords: list, full_command: str) -> str:
    """
    Extract a clean filename from the user command.

    Priority order:
      1. A token that already contains a file extension (e.g. 'report.txt')
      2. Quoted name in full_command  (e.g. 'create file "my notes"')
      3. The word(s) after 'called'/'named' in full_command
      4. Keywords after stripping all filler words
      5. Fallback: 'newfile.txt'

    Always ensures the result has a .txt extension if none was given,
    and replaces spaces with underscores.
    """
    # 1. Token with extension already present
    for kw in keywords:
        if _re.match(r'.+\.\w{2,5}$', kw):
            return kw

    # 2. Quoted string in the raw command
    quoted = _re.search(r'["\'](.+?)["\']', full_command)
    if quoted:
        name = quoted.group(1).strip()
        if name:
            return _sanitize_name(name, is_file=True)

    # 3. Word(s) after 'called' or 'named'
    after = _re.search(r'\b(?:called|named)\s+(\S+)', full_command.lower())
    if after:
        name = after.group(1).strip().strip(".,!?")
        if name:
            return _sanitize_name(name, is_file=True)

    # 4. Strip filler and join remaining keywords
    parts = [k for k in keywords if k.lower() not in _FILE_FILLER]
    name = "_".join(parts).strip("_")
    if name:
        return _sanitize_name(name, is_file=True)

    return "newfile.txt"


def _extract_foldername(keywords: list, full_command: str) -> str:
    """
    Extract a clean folder name from the user command.
    Same logic as _extract_filename but for folders (no extension added).
    """
    # Quoted string
    quoted = _re.search(r'["\'](.+?)["\']', full_command)
    if quoted:
        name = quoted.group(1).strip()
        if name:
            return name.replace(" ", "_")

    # Word(s) after 'called' or 'named'
    after = _re.search(r'\b(?:called|named)\s+(\S+)', full_command.lower())
    if after:
        return after.group(1).strip().strip(".,!?")

    # Strip filler
    parts = [k for k in keywords if k.lower() not in _FOLDER_FILLER]
    name = "_".join(parts).strip("_")
    return name if name else "newfolder"


def _sanitize_name(name: str, is_file: bool = True) -> str:
    """Replace spaces with underscores and auto-add .txt for files without extension."""
    name = name.replace(" ", "_")
    if is_file and "." not in name:
        name = name + ".txt"
    return name

def execute_task(intent, keywords, full_command=""):
    # ── Pronoun resolution (NEW) ──────────────────────────────────────────────
    # Before routing, substitute any pronoun/reference token with the last
    # remembered entity value.  If the pronoun cannot be resolved (memory is
    # empty), return a clarification prompt immediately.
    keywords, _unresolvable = _resolve_keywords(keywords)
    if _unresolvable:
        return (
            "I\u2019m not sure what you\u2019re referring to \u2014 "
            "what would you like to open/close/rename?"
        )
    # ── End pronoun resolution ────────────────────────────────────────────────

    # Application Management
    if intent == "open_app":
        # Remove "open" and "switch" from keywords
        app_name = " ".join(remove_action_keyword(keywords, ["open", "switch"])).strip()
        if not app_name:
            app_name = " ".join(keywords)
        result = open_or_switch_app(app_name)
        memory.update("opened", "app", app_name)  # NEW: persist to memory
        return result
    
    elif intent == "close_app":
        # Remove "close" from keywords
        app_name = " ".join(remove_action_keyword(keywords, ["close"])).strip()
        if not app_name:
            app_name = " ".join(keywords)
        result = close_app(app_name)
        memory.update("closed", "app", app_name)  # NEW
        return result
    
    elif intent == "list_apps":
        return list_running_apps()
    
    elif intent == "get_active_window":
        return get_active_window()
    
    # File and Folder Management
    elif intent == "create_file":
        file_path = _extract_filename(keywords, full_command)
        result = create_file(file_path)
        memory.update("created", "file", file_path)  # NEW
        return result
    
    elif intent == "create_folder":
        folder_path = _extract_foldername(keywords, full_command)
        result = create_folder(folder_path)
        memory.update("created", "folder", folder_path)  # NEW
        return result
    
    elif intent == "open_file_folder":
        import re as _re3
        # Extract target name from raw command (preserves stop words like "my", "the")
        # e.g. "open report.txt"  → "report.txt"
        #      "open my notes"    → "my notes" → cleaned to "notes"
        #      "open downloads folder" → "downloads"
        target_match = _re3.search(
            r'\b(?:open|show|launch|browse)\s+(?:the\s+|my\s+|a\s+)?(.+?)(?:\s+(?:file|folder|directory))?$',
            full_command.strip().lower()
        )
        path = target_match.group(1).strip() if target_match else ""
        # Strip trailing filler words that may have been captured
        path = _re3.sub(r'\b(?:please|now|for me)\b', '', path).strip()

        # Pronoun fallback ("open it", "open that file")
        if not path or path in {"it", "that", "the file", "that file", "the folder"}:
            last = memory.get_last()
            if last:
                path = last["entity_value"]

        if not path:
            path = " ".join(remove_action_keyword(keywords, ["open", "file", "folder"])).strip()

        # Route: if command mentions "folder" or path has no extension → open folder
        if "folder" in full_command.lower() or "directory" in full_command.lower():
            result = open_folder(path)
            memory.update("opened", "folder", path)
        else:
            result = open_file(path)
            memory.update("opened", "file", path)
        return result

    
    elif intent == "rename_file":
        if len(keywords) >= 2:
            old_name = keywords[0]
            new_name = " ".join(keywords[1:])
            result = rename_file(old_name, new_name)
            memory.update("renamed", "file", new_name)  # NEW: track new name
            return result
        return "Please specify old and new filename."
    
    elif intent == "rename_folder":
        if len(keywords) >= 2:
            old_name = keywords[0]
            new_name = " ".join(keywords[1:])
            result = rename_folder(old_name, new_name)
            memory.update("renamed", "folder", new_name)  # NEW
            return result
        return "Please specify old and new folder name."
    
    elif intent == "delete_file":
        file_path = " ".join(remove_action_keyword(keywords, ["delete", "file"])).strip()
        if not file_path:
            file_path = " ".join(keywords)
        result = delete_file(file_path)
        memory.update("deleted", "file", file_path)  # NEW
        return result
    
    elif intent == "delete_folder":
        folder_path = " ".join(remove_action_keyword(keywords, ["delete", "folder", "directory"])).strip()
        if not folder_path:
            folder_path = " ".join(keywords)
        result = delete_folder(folder_path)
        memory.update("deleted", "folder", folder_path)  # NEW
        return result
    
    elif intent == "search_files":
        search_term = " ".join(remove_action_keyword(keywords, ["search", "file", "find"])).strip()
        if not search_term:
            search_term = " ".join(keywords)
        result = search_files(search_term)
        memory.update("searched", "file", search_term)  # NEW
        return result
    
    elif intent == "move_file":
        if len(keywords) >= 2:
            source = keywords[0]
            destination = " ".join(keywords[1:])
            result = move_file(source, destination)
            memory.update("moved", "file", destination)  # NEW: track destination
            return result
        return "Please specify source and destination."
    
    elif intent == "list_files":
        folder_path = " ".join(remove_action_keyword(keywords, ["list", "files", "folder"])).strip()
        if not folder_path:
            folder_path = "."
        return list_files(folder_path)
    
    # System Control Operations
    elif intent == "shutdown_system":
        return shutdown_system()
    elif intent == "restart_system":
        return restart_system()
    elif intent == "lock_system":
        return lock_system()
    elif intent == "logout_user":
        return logout_user()
    elif intent == "sleep_system":
        return sleep_system()
    elif intent == "increase_volume":
        return increase_volume()
    elif intent == "decrease_volume":
        return decrease_volume()
    elif intent == "mute_volume":
        return mute_volume()
    elif intent == "get_system_info":
        return get_system_info()
    
    # Text Input Assistance
    elif intent == "type_text":
        # ── Extract text from the RAW command, not NLP keywords ──────────────
        # Reason: NLP strips stop words ("how", "are", "you", "I", etc.) so
        # "type how are you" → keywords=["type"] → nothing left to type.
        # Using a regex on full_command preserves the complete phrase.
        import re as _re2
        text = ""

        # Match everything after the trigger verb
        trigger_match = _re2.search(
            r'\b(?:type|write|input|say|enter|write\s+out)\s+(.+)',
            full_command.strip().lower()
        )
        if trigger_match:
            text = trigger_match.group(1).strip()

        # Fallback: if regex didn't capture anything, join keywords without "type"
        if not text:
            text = " ".join(remove_action_keyword(keywords, ["type", "write", "input", "say", "enter"])).strip()

        # Last resort: use the full command minus common filler
        if not text:
            text = full_command.strip()

        result = type_text(text)
        memory.update("typed", "text", text)  # NEW
        return result

    
    elif intent == "insert_predefined_text":
        preset_type = keywords[0] if keywords else "greeting"
        return insert_predefined_text(preset_type)
    
    elif intent == "copy_text":
        return copy_text()
    elif intent == "paste_text":
        return paste_text()
    elif intent == "select_all":
        return select_all()
    elif intent == "undo_action":
        return undo_action()
    elif intent == "redo_action":
        return redo_action()
    
    elif intent == "record_macro":
        return _start_macro_recording(keywords)

    elif intent == "stop_macro":
        return _stop_macro_recording(keywords)

    elif intent == "play_macro":
        macro_name = " ".join(remove_action_keyword(keywords, ["play", "run", "execute", "replay", "macro"])).strip()
        if not macro_name:
            macro_name = "default"
        return _play_macro(macro_name)

    elif intent == "list_macros":
        return _list_macros()

    elif intent == "read_screen":
        return _read_screen()

    elif intent == "undo_last_action":
        # Delete / reverse the last thing Mantra created in this session
        return undo_last_creation(memory)

    elif intent == "list_desktop":
        return list_desktop_files()

    elif intent == "unknown":
        # Only attempt app launch if a known app-like keyword is present
        # and the user didn't just type something generic.
        _KNOWN_APP_HINTS = {
            "chrome", "firefox", "edge", "opera", "brave",
            "notepad", "wordpad", "word", "excel", "powerpoint", "outlook",
            "vlc", "discord", "telegram", "whatsapp", "slack", "teams",
            "spotify", "steam", "blender", "gimp", "pycharm", "intellij",
            "calculator", "paint", "zoom", "skype", "obs", "audacity",
            "7zip", "winrar", "putty", "filezilla", "thunderbird",
            "vs", "code", "atom", "sublime",
        }
        matched = [kw for kw in keywords if kw.lower() in _KNOWN_APP_HINTS]
        if matched:
            return open_or_switch_app(" ".join(matched))
        return (
            "❌ Command not recognized. Try: 'open chrome', 'create file test.txt', "
            "'close notepad', 'list apps', 'volume up', 'shutdown'"
        )

    else:
        return "❌ Unknown command. Try: 'open [app]', 'create file', 'delete file', 'type text', etc."


# ── Macro helpers ─────────────────────────────────────────────────────────────

def _start_macro_recording(keywords):
    """Begin recording keyboard + mouse events via pynput."""
    global _macro_recording, _macro_events, _macro_listener, _macro_start_time
    import time

    if _macro_recording:
        return "⚠️ Already recording a macro. Say 'stop recording' first."

    try:
        from pynput import keyboard as kb, mouse as ms
    except ImportError:
        return "❌ pynput not installed. Run: pip install pynput"

    _macro_recording  = True
    _macro_events     = []
    _macro_start_time = time.time()

    def on_key_press(key):
        if not _macro_recording:
            return False   # stops the listener
        try:
            _macro_events.append({"type": "key_press",
                                   "key": str(key),
                                   "timestamp": round(time.time() - _macro_start_time, 3)})
        except Exception:
            pass

    def on_key_release(key):
        if not _macro_recording:
            return False
        try:
            _macro_events.append({"type": "key_release",
                                   "key": str(key),
                                   "timestamp": round(time.time() - _macro_start_time, 3)})
        except Exception:
            pass

    def on_click(x, y, button, pressed):
        if not _macro_recording:
            return False
        _macro_events.append({"type": "mouse_click",
                               "x": x, "y": y,
                               "button": str(button),
                               "pressed": pressed,
                               "timestamp": round(time.time() - _macro_start_time, 3)})

    _macro_listener = kb.Listener(on_press=on_key_press, on_release=on_key_release)
    _macro_listener.start()
    return "⏺ Recording macro... Say 'stop recording' or 'stop macro' when done."


def _stop_macro_recording(keywords):
    """Stop the active recording and save the macro to SQLite."""
    global _macro_recording, _macro_listener

    if not _macro_recording:
        return "⚠️ No macro is currently being recorded."

    _macro_recording = False
    if _macro_listener:
        _macro_listener.stop()
        _macro_listener = None

    macro_name = " ".join(remove_action_keyword(
        keywords, ["stop", "end", "finish", "done", "recording", "macro"]
    )).strip() or "default"

    try:
        save_macro(macro_name, _macro_events)
        count = len(_macro_events)
        return f"✅ Macro '{macro_name}' saved with {count} events."
    except Exception as e:
        return f"❌ Failed to save macro: {e}"


def _play_macro(macro_name: str):
    """Replay a saved macro from SQLite."""
    try:
        import time
        from pynput import keyboard as kb, mouse as ms
    except ImportError:
        return "❌ pynput not installed. Run: pip install pynput"

    steps = get_macro(macro_name)
    if steps is None:
        # Try to list available macros for helpful feedback
        available = [m["macro_name"] for m in db_list_macros()]
        hint = f" Available: {', '.join(available)}" if available else " No macros saved yet."
        return f"❌ Macro '{macro_name}' not found.{hint}"

    kb_ctrl  = kb.Controller()
    ms_ctrl  = ms.Controller()

    prev_ts = 0.0
    for event in steps:
        # Honour original timing (capped at 2s per gap to avoid hanging)
        gap = min(event.get("timestamp", 0) - prev_ts, 2.0)
        if gap > 0:
            time.sleep(gap)
        prev_ts = event.get("timestamp", 0)

        try:
            etype = event.get("type")
            if etype == "key_press":
                kb_ctrl.press(_parse_key(event["key"]))
            elif etype == "key_release":
                kb_ctrl.release(_parse_key(event["key"]))
            elif etype == "mouse_click":
                ms_ctrl.position = (event["x"], event["y"])
                btn = ms.Button.left if "left" in event.get("button", "") else ms.Button.right
                if event.get("pressed"):
                    ms_ctrl.press(btn)
                else:
                    ms_ctrl.release(btn)
        except Exception:
            pass   # skip unplayable events silently

    return f"▶️ Macro '{macro_name}' played back ({len(steps)} events)."


def _parse_key(key_str: str):
    """Convert a pynput key string back to a pynput Key or character."""
    from pynput import keyboard as kb
    key_str = key_str.strip("'")
    try:
        return kb.Key[key_str.replace("Key.", "")]
    except KeyError:
        return key_str[0] if key_str else ''


def _list_macros():
    """Return a formatted list of all saved macros."""
    try:
        macros = db_list_macros()
        if not macros:
            return "❌ No macros saved yet. Say 'start recording macro' to create one."
        lines = [f"• {m['macro_name']} (saved {m['created_at']}" for m in macros]
        return "📝 Saved macros:\n" + "\n".join(lines)
    except Exception as e:
        return f"❌ Failed to list macros: {e}"


def _read_screen():
    """Capture a screenshot and extract visible text using pytesseract (OCR)."""
    try:
        import pytesseract
        from PIL import ImageGrab
        screenshot = ImageGrab.grab()
        text = pytesseract.image_to_string(screenshot).strip()
        if not text:
            return "❌ No readable text found on screen."
        # Truncate to first 500 chars to keep TTS reasonable
        preview = text[:500]
        if len(text) > 500:
            preview += " ... [truncated]"
        return f"📺 Screen text:\n{preview}"
    except ImportError:
        # Fallback: just use pyautogui screenshot + basic summary
        try:
            import pyautogui
            screenshot = pyautogui.screenshot()
            return (
                f"📺 Screenshot captured ({screenshot.width}x{screenshot.height}px). "
                "Install pytesseract + Tesseract OCR for full text reading."
            )
        except Exception as e2:
            return f"❌ Screen read failed: {e2}"
    except Exception as e:
        return f"❌ Screen read failed: {e}"
