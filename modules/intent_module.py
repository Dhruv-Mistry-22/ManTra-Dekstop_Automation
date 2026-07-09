# modules/intent_module.py
# Mantra V2 — Intent Detection Module (REWRITE)
# Replaces V1 keyword scanning with sentence-transformers cosine similarity.
#
# How it works:
#   1. Check adaptive learning corrections from SQLite (personalised overrides).
#   2. Encode the user's command using 'all-MiniLM-L6-v2' (runs locally, ~90MB).
#   3. Compute cosine similarity against a library of example sentences per intent.
#   4. Return the intent with the highest score above the confidence threshold.
#   5. If negated=True, route to the negation handler instead of executing blindly.
#
# Result: "launch Chrome", "open the browser", "start Chromium" all map to open_app.
#         "don't open Chrome" is detected as negated — execution module handles it.

import logging
from functools import lru_cache
from typing import Optional
from modules.entity_aware_intent import (
    hybrid_predict, build_normalized_embeddings
)

logger = logging.getLogger(__name__)

# ── Adaptive learning (NEW) ───────────────────────────────────────────────────
# Singleton shared for the lifetime of the process.  Must be imported after
# the project root is on sys.path (it always is when running from the repo).
from core.adaptive_learning import CorrectionStore
_correction_store = CorrectionStore()   # reads/writes data/mantra.db
# ── End adaptive learning import ──────────────────────────────────────────────

# ── Confidence threshold ──────────────────────────────────────────────────────
# If the best match scores below this, return "unknown".
# 0.40 is conservative — enough to catch paraphrases without false positives.
CONFIDENCE_THRESHOLD = 0.40

# ── Sentence-transformers model ───────────────────────────────────────────────
_model = None
_intent_embeddings = None   # pre-computed embeddings for all examples
_intent_labels = None       # labels corresponding to the embeddings

def _load_model():
    global _model, _intent_embeddings, _intent_labels
    if _model is not None:
        return _model
    try:
        import os
        os.environ["HF_HUB_OFFLINE"] = "1"
        from sentence_transformers import SentenceTransformer
        logger.info("[intent] Loading sentence-transformers model...")
        _model = SentenceTransformer("all-MiniLM-L6-v2", local_files_only=True)
        _intent_embeddings, _intent_labels = build_normalized_embeddings(_model)
        logger.info("[intent] Model loaded and embeddings pre-computed.")
    except ImportError:
        raise RuntimeError(
            "[intent] sentence-transformers not installed.\n"
            "Run: pip install sentence-transformers"
        )
    return _model

# ── Intent example library ────────────────────────────────────────────────────
# For each intent: a list of natural language examples.
# The more varied the examples, the better paraphrase coverage.
# When the user types/says something new, it's compared to ALL examples below.
INTENT_EXAMPLES = {
    # ── Application Management ────────────────────────────────────────────────
    "open_app": [
        "open chrome", "launch spotify", "start notepad", "run calculator",
        "bring up firefox", "can you open excel", "pull up discord",
        "start the browser", "open the application", "launch the program",
        "open edge", "fire up vlc", "get discord running", "open word",
        "start visual studio", "run pycharm", "open teams",
    ],
    "close_app": [
        "close chrome", "quit notepad", "exit spotify", "shut down discord",
        "terminate the application", "kill notepad", "close the browser",
        "stop excel", "close this app", "quit the program", "shut it down",
        "end the process", "force close", "close teams",
    ],
    "list_apps": [
        "list all apps", "show running applications", "what apps are open",
        "display all processes", "which programs are running",
        "show me what's open", "list processes", "what is running",
    ],
    "get_active_window": [
        "what is the active window", "which app is in focus",
        "current window", "what am I using right now",
        "which window is active", "tell me the active app",
        "what is currently open", "current active application",
    ],

    # ── File & Folder Management ──────────────────────────────────────────────
    "create_file": [
        "create a file", "make a new file", "create test.txt",
        "new file called report", "make a text file", "create an empty file",
        "generate a new file", "make file notes.txt",
    ],
    "create_folder": [
        "create a folder", "make a new directory", "new folder called documents",
        "create a directory", "make folder backup", "mkdir new_folder",
        "create a new folder named projects",
    ],
    "open_file_folder": [
        "open this file", "open the folder", "show me the folder",
        "open document", "open the directory", "browse to folder",
        "open file report.txt", "open folder downloads",
    ],
    "rename_file": [
        "rename the file", "change file name", "rename old.txt to new.txt",
        "give the file a new name", "rename this document",
    ],
    "rename_folder": [
        "rename the folder", "change folder name", "rename directory",
        "give the folder a new name", "rename this folder",
    ],
    "delete_file": [
        "delete the file", "remove this file", "erase the document",
        "get rid of the file", "delete test.txt", "remove file",
        "permanently delete file", "trash the file",
        "delete the file report.txt", "remove the file notes.txt",
        "delete file called backup.txt", "erase this file permanently",
        "delete the document test.txt", "remove old.txt",
        "delete a file named data.csv", "destroy the file",
    ],
    "delete_folder": [
        "delete the folder", "remove this directory", "erase the folder",
        "delete folder backup", "remove directory", "trash the folder",
    ],
    "search_files": [
        "search for files", "find a file", "look for document",
        "where is my file", "find files named report", "search file",
        "locate a file", "where did I save", "find document",
    ],
    "move_file": [
        "move the file", "transfer file to", "relocate document",
        "move file to downloads", "shift the file to backup",
        "move test.txt to documents",
    ],
    "list_files": [
        "list files in folder", "show files", "what files are here",
        "display folder contents", "show me the files", "list directory",
        "what is inside this folder", "show all files",
    ],

    # ── System Control ────────────────────────────────────────────────────────
    "shutdown_system": [
        "shutdown the computer", "turn off the PC", "power down",
        "shut down now", "turn off my computer", "power off",
        "switch off the computer", "shut the system down",
    ],
    "restart_system": [
        "restart the computer", "reboot the PC", "restart now",
        "reboot my computer", "do a restart", "restart windows",
    ],
    "lock_system": [
        "lock the screen", "lock my computer", "lock workstation",
        "lock the PC", "secure my screen", "lock the system",
    ],
    "logout_user": [
        "log out", "sign out of windows", "switch user",
        "log me out", "sign off", "end my session",
    ],
    "sleep_system": [
        "put computer to sleep", "sleep mode", "go to sleep",
        "hibernate the computer", "suspend", "enter sleep mode",
    ],
    "increase_volume": [
        "increase volume", "turn up the volume", "louder",
        "volume up", "make it louder", "boost the volume",
        "raise the volume", "turn the volume up",
    ],
    "decrease_volume": [
        "decrease volume", "turn down the volume", "quieter",
        "volume down", "make it quieter", "lower the volume",
        "reduce volume", "turn the volume down",
    ],
    "mute_volume": [
        "mute the sound", "silence audio", "mute",
        "turn off sound", "go silent", "mute the volume",
        "no sound", "kill the audio",
    ],
    "get_system_info": [
        "system information", "show system info", "what are my specs",
        "computer info", "hardware info", "tell me about this PC",
        "display system details", "show os info",
    ],

    # ── Text Input Assistance ─────────────────────────────────────────────────
    "type_text": [
        "type this text", "write hello world", "type something for me",
        "input this text", "type the words", "write out", "type hello",
        "type how are you", "type good morning", "type I am fine",
        "write good morning", "say hello there", "enter the text hello",
        "type nice to meet you", "write this for me",
        "type a message", "write a sentence", "type some text",
        "type thank you", "write thank you very much",
        "type my name is john", "type the password",
        "write out the message", "input the text good day",
    ],
    "insert_predefined_text": [
        "insert email template", "insert greeting", "paste the preset",
        "use the email snippet", "insert signature", "add preset text",
    ],
    "copy_text": [
        "copy the text", "copy selected", "copy this",
        "copy to clipboard", "ctrl c", "copy what I selected",
    ],
    "paste_text": [
        "paste the text", "paste here", "ctrl v", "paste what was copied",
        "paste from clipboard", "put the text here",
    ],
    "select_all": [
        "select all text", "select everything", "ctrl a",
        "highlight all", "select all content",
    ],
    "undo_action": [
        "undo last action", "undo that", "ctrl z",
        "take that back", "revert last change", "undo",
    ],
    "redo_action": [
        "redo that action", "redo", "ctrl y",
        "do it again", "redo the last thing",
    ],

    # ── Macro Recorder ────────────────────────────────────────────────────────
    "record_macro": [
        "start recording macro", "record this workflow",
        "begin macro recording", "start macro", "record my actions",
        "capture this workflow", "start recording",
    ],
    "stop_macro": [
        "stop recording", "end macro", "finish recording",
        "stop the macro", "end the recording", "done recording",
    ],
    "play_macro": [
        "run the macro", "play back workflow", "execute macro",
        "replay macro", "run my recorded workflow", "play the macro",
        "execute the workflow",
    ],
    "list_macros": [
        "list macros", "show my macros", "what macros do I have",
        "display saved macros", "show recorded workflows",
    ],

    # ── Screen Vision ─────────────────────────────────────────────────
    "read_screen": [
        "read what is on screen", "what does the screen say",
        "read the error message", "read the dialog box",
        "what is displayed on screen", "read screen text",
        "tell me what is on screen",
    ],

    # ── Undo / Context Delete ───────────────────────────────────────
    "undo_last_action": [
        "delete what you just created", "undo last", "delete the last file you made",
        "remove what you just made", "undo the last thing", "delete that file you created",
        "undo last creation", "remove the file you just created",
        "delete the last created file", "undo that", "remove what I just created",
        "delete last", "undo create", "cancel that creation",
    ],

    # ── Desktop Listing ─────────────────────────────────────────────────
    "list_desktop": [
        "show desktop files", "what is on my desktop", "list desktop",
        "show me my desktop", "what files are on the desktop",
        "list all files on desktop", "desktop files", "show desktop",
    ],
}


# ── Pre-compute embeddings ────────────────────────────────────────────────────
def _precompute_embeddings() -> dict:
    """
    Compute and cache the sentence embedding for every example sentence.
    Returns: { intent_name: tensor_of_stacked_embeddings }
    This is called once at model load time. After that, each inference
    only needs to encode the single user command (~5-15ms on CPU).
    """
    import torch
    embeddings = {}
    all_examples = [(intent, ex) for intent, exs in INTENT_EXAMPLES.items()
                    for ex in exs]
    sentences = [ex for _, ex in all_examples]

    encoded = _model.encode(sentences, convert_to_tensor=True, show_progress_bar=False)

    idx = 0
    for intent, examples in INTENT_EXAMPLES.items():
        n = len(examples)
        embeddings[intent] = encoded[idx: idx + n]
        idx += n

    return embeddings


# ── Public API ────────────────────────────────────────────────────────────────
def detect_intent(parsed: dict) -> str:
    """
    Detect the intent of a parsed command.

    Args:
        parsed: The dict returned by nlp_module.process_command()
                Must have at minimum: 'cleaned', 'keywords', 'negated'.

    Returns:
        Intent string e.g. 'open_app', 'create_file', 'unknown'.
        If parsed['negated'] is True, returns 'negated_<intent>'
        so the execution module can handle it appropriately.

    Example:
        parsed = process_command("don't open chrome")
        intent = detect_intent(parsed)
        # Returns: "negated_open_app"
    """
    # ── Accept both V1-style keyword list and V2 parsed dict ─────────────────
    if isinstance(parsed, list):
        # V1 backward-compatibility: caller passed a keyword list
        parsed = {
            "raw":     " ".join(parsed),
            "cleaned": " ".join(parsed),
            "keywords": parsed,
            "negated": False,
            "entities": {},
            "tokens": [],
        }

    command_text = parsed.get("cleaned") or parsed.get("raw", "")
    if not command_text:
        return "unknown"

    # ── Step 1: Check adaptive learning corrections ───────────────────────────
    corrected = _check_corrections(command_text)
    if corrected:
        logger.info("[intent] Correction override: '%s' → '%s'", command_text, corrected)
        intent = corrected
    else:
        # ── Step 2: Semantic similarity matching ─────────────────────────────
        try:
            model = _load_model()
            intent, entity, confidence = hybrid_predict(
                command_text, model, _intent_embeddings, _intent_labels
            )
            
            if entity and "entities" in parsed:
                if intent in ("open_app", "close_app", "switch_app"):
                    parsed["entities"]["app"] = entity
                elif "file" in intent:
                    parsed["entities"]["file"] = entity
                elif "folder" in intent or intent == "list_directory":
                    parsed["entities"]["folder"] = entity
        except Exception as e:
            logger.error("[intent] Semantic match failed: %s", e)
            intent = _keyword_fallback(command_text)

    # ── Step 3: Negation routing ──────────────────────────────────────────────
    if parsed.get("negated") and intent != "unknown":
        # Prefix with 'negated_' so execution_module can handle it
        return f"negated_{intent}"

    return intent


def _semantic_match(command_text: str) -> str:
    """
    Encode the command and find the closest intent via cosine similarity.
    Returns the intent name or 'unknown' if no match exceeds the threshold.
    """
    try:
        import torch
        from sentence_transformers import util as st_util

        model = _load_model()
        cmd_embedding = model.encode(command_text, convert_to_tensor=True,
                                     show_progress_bar=False)

        best_intent = "unknown"
        best_score  = 0.0

        for intent, example_embeddings in _intent_embeddings.items():
            # Cosine similarity between command and ALL examples for this intent
            scores = st_util.cos_sim(cmd_embedding, example_embeddings)
            # Take the max score (best matching example for this intent)
            max_score = float(scores.max())

            if max_score > best_score:
                best_score  = max_score
                best_intent = intent

        if best_score >= CONFIDENCE_THRESHOLD:
            logger.debug("[intent] '%s' → '%s' (score=%.3f)", command_text, best_intent, best_score)
            return best_intent
        else:
            logger.debug("[intent] No confident match for '%s' (best=%.3f)", command_text, best_score)
            return "unknown"

    except Exception as e:
        logger.error("[intent] Semantic match failed: %s", e)
        # Fallback to V1 keyword method so the system doesn't crash
        return _keyword_fallback(command_text)


def _check_corrections(command_text: str) -> Optional[str]:
    """
    Check the adaptive learning corrections table via CorrectionStore.

    Delegates to ``_correction_store.check_correction()`` which uses
    ``rapidfuzz.fuzz.partial_ratio`` with a threshold of 85 and requires
    ``frequency >= 2`` before a correction is applied.

    Returns the correct intent string if a high-confidence correction is
    found, or None if no correction applies.
    """
    # BEFORE: inline rapidfuzz + db_manager lookup (replaced)
    # AFTER : single call to CorrectionStore – handles fuzzy match,
    #         frequency gate, logging, and graceful ImportError internally.
    corrected = _correction_store.check_correction(command_text, threshold=85)
    if corrected:
        logger.info("[intent] Adaptive correction applied: '%s' -> '%s'",
                    command_text, corrected)
    return corrected


def _keyword_fallback(command_text: str) -> str:
    """
    Emergency fallback to simple keyword matching if sentence-transformers fails.
    Mirrors the V1 logic so the system is never completely broken.
    """
    words = set(command_text.lower().split())
    if "open" in words or "launch" in words or "start" in words:
        return "open_app"
    if "close" in words or "quit" in words or "exit" in words:
        return "close_app"
    if "create" in words and "file" in words:
        return "create_file"
    if "create" in words and ("folder" in words or "directory" in words):
        return "create_folder"
    # ── undo_last MUST come before delete_file ─────────────────────────────────
    # "delete last file" has both "delete" and "file" — without this guard it
    # would incorrectly match delete_file instead of undo_last_action.
    if ("undo" in words or "delete" in words) and \
       ("last" in words or "created" in words or "just" in words):
        return "undo_last_action"
    if "delete" in words and "file" in words:
        return "delete_file"
    if "delete" in words and "folder" in words:
        return "delete_folder"
    if "shutdown" in words:
        return "shutdown_system"
    if "restart" in words:
        return "restart_system"
    if "lock" in words:
        return "lock_system"
    if "volume" in words and "up" in words:
        return "increase_volume"
    if "volume" in words and "down" in words:
        return "decrease_volume"
    if "mute" in words:
        return "mute_volume"
    if "type" in words or "write" in words or "say" in words:
        return "type_text"

    if "copy" in words:
        return "copy_text"
    if "paste" in words:
        return "paste_text"
    if "undo" in words:
        return "undo_action"
    if "redo" in words:
        return "redo_action"
    if "desktop" in words and ("list" in words or "show" in words or "what" in words):
        return "list_desktop"
    return "unknown"

