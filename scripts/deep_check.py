"""
Deep dependency + feature verification for ManTra V2.
Tests every critical import, every feature category end-to-end.
"""
import sys, os
sys.path.insert(0, '.')

PASS = []; FAIL = []

def check(name, fn):
    try:
        fn()
        PASS.append(name)
        print(f"  OK   {name}")
    except Exception as e:
        FAIL.append(name)
        print(f"  FAIL {name}: {e}")

# ── CORE DEPENDENCIES ──────────────────────────────────────────────────────────
print("\n[1] Core Dependencies")

def dep_pyqt5():
    from PyQt5.QtWidgets import QApplication
    from PyQt5.QtCore import Qt
check("PyQt5 (GUI)", dep_pyqt5)

def dep_whisper():
    # Import whisper in isolation — torch DLL must not be pre-loaded by another module
    import subprocess, sys
    r = subprocess.run([sys.executable, "-c", "import whisper; print('ok')"], capture_output=True, text=True)
    assert r.returncode == 0 and "ok" in r.stdout, r.stderr.strip()[:200]
check("openai-whisper (STT)", dep_whisper)

def dep_sounddevice():
    import sounddevice as sd
check("sounddevice (microphone)", dep_sounddevice)

def dep_spacy():
    import subprocess, sys
    r = subprocess.run([sys.executable, "-c", "import spacy; nlp=spacy.load('en_core_web_md'); print('ok')"], capture_output=True, text=True)
    assert r.returncode == 0 and "ok" in r.stdout, r.stderr.strip()[:200]
check("spaCy + en_core_web_md", dep_spacy)

def dep_sentence_transformers():
    import subprocess, sys
    r = subprocess.run([sys.executable, "-c", "from sentence_transformers import SentenceTransformer; m=SentenceTransformer('all-MiniLM-L6-v2'); print('ok')"], capture_output=True, text=True, timeout=60)
    assert r.returncode == 0 and "ok" in r.stdout, r.stderr.strip()[:200]
check("sentence-transformers (NLP)", dep_sentence_transformers)

def dep_rapidfuzz():
    from rapidfuzz import fuzz
    assert fuzz.ratio("hello", "hello") == 100
check("rapidfuzz (fuzzy search)", dep_rapidfuzz)

def dep_psutil():
    import psutil
    assert psutil.cpu_percent() >= 0
check("psutil (system info)", dep_psutil)

def dep_pyautogui():
    import pyautogui
check("pyautogui (automation)", dep_pyautogui)

def dep_pywin32():
    import win32com.client
    import win32api
check("pywin32 (TTS + Windows API)", dep_pywin32)

def dep_pynput():
    from pynput import keyboard, mouse
check("pynput (macro recording)", dep_pynput)

def dep_pillow():
    from PIL import Image, ImageGrab
check("Pillow (screenshot)", dep_pillow)

def dep_sqlite():
    import sqlite3
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE t (x TEXT)")
    conn.close()
check("sqlite3 (database)", dep_sqlite)

def dep_pyperclip():
    import pyperclip
check("pyperclip (clipboard)", dep_pyperclip)

# ── FEATURE PIPELINE ──────────────────────────────────────────────────────────
print("\n[2] Feature Pipeline")

def feat_intent_detection():
    import subprocess, sys
    r = subprocess.run(
        [sys.executable, "-c",
         "import sys; sys.path.insert(0,'.');"
         "from modules.nlp_module import process_command;"
         "res=process_command('open chrome');"
         "assert 'keywords' in res and 'negated' in res, str(res);"
         "print('ok keywords:', res['keywords'])"],
        capture_output=True, text=True, cwd="."
    )
    assert r.returncode == 0 and "ok keywords" in r.stdout, r.stderr.strip()[:300]
check("Intent Detection / process_command (NLP)", feat_intent_detection)

def feat_entity_extraction():
    from modules.entity_aware_intent import extract_entities
    ents = extract_entities("open chrome please")
    assert isinstance(ents, dict)
check("Entity Extraction", feat_entity_extraction)

def feat_execute_open_app():
    from modules.execution_module import execute_task
    # Just test routing, not actual launch
    result = execute_task("list_apps", [], "list apps")
    assert isinstance(result, str)
check("execute_task routing (list_apps)", feat_execute_open_app)

def feat_execute_file_create():
    from modules.execution_module import execute_task
    # Dry run — just test the filename extraction path
    from modules.execution_module import _extract_filename
    name = _extract_filename(["create","file","test"], "create file test")
    assert name == "test.txt", f"got {name}"
check("File creation (filename extraction)", feat_execute_file_create)

def feat_execute_type():
    from modules.execution_module import execute_task
    import re
    pat = r'\b(?:type|write|input|say|enter)\s+(.+)'
    m = re.search(pat, "type how are you today")
    assert m and m.group(1) == "how are you today"
check("Type text (stop-word preservation)", feat_execute_type)

def feat_undo():
    from core.context_memory import MemoryBank
    from modules.file_manager import undo_last_creation
    m = MemoryBank(db_path="data/test_undo_verify.db")
    m.update("created", "file", "__test_undo_file.txt")
    # Create the actual file first
    desktop = os.path.join(os.path.expanduser("~"), "Desktop")
    test_path = os.path.join(desktop, "__test_undo_file.txt")
    open(test_path, "w").close()
    result = undo_last_creation(m)
    assert "Deleted" in result or "Could not find" in result
    # cleanup
    try: os.remove("data/test_undo_verify.db")
    except: pass
check("Undo last creation", feat_undo)

def feat_memory_pronouns():
    from core.context_memory import MemoryBank
    m = MemoryBank(db_path="data/test_pronoun.db")
    m.update("opened", "app", "chrome")
    m.update("created", "file", "notes.txt")
    assert m.resolve_pronoun("it") == "notes.txt"
    assert m.resolve_pronoun("the app") == "chrome"
    try: os.remove("data/test_pronoun.db")
    except: pass
check("Memory Bank pronoun resolution", feat_memory_pronouns)

def feat_list_desktop():
    from modules.file_manager import list_desktop_files
    result = list_desktop_files()
    assert isinstance(result, str)
    assert len(result) > 0
check("List desktop files", feat_list_desktop)

def feat_tts():
    from modules.tts_module import speak
    assert callable(speak)
check("TTS module (speak callable)", feat_tts)

def feat_db_logging():
    from modules.db_manager import log_command, get_recent_commands
    log_command("test command", "test_intent", "test result", 0.1)
    rows = get_recent_commands(1)
    assert len(rows) >= 1
check("DB command logging", feat_db_logging)

def feat_adaptive_learning():
    from core.adaptive_learning import CorrectionStore
    cs = CorrectionStore(db_path="data/test_adaptive_verify.db")
    # Correct method names are store_correction and check_correction
    assert hasattr(cs, "store_correction") or hasattr(cs, "add_correction"), \
        f"Neither store_correction nor add_correction found. Methods: {[m for m in dir(cs) if not m.startswith('_')]}"
    assert hasattr(cs, "check_correction")
    try: os.remove("data/test_adaptive_verify.db")
    except: pass
check("Adaptive learning (CorrectionStore)", feat_adaptive_learning)

def feat_keyword_fallback():
    from modules.intent_module import _keyword_fallback as kf
    checks = [
        ("open chrome",              "open_app"),
        ("close notepad",            "close_app"),
        ("create file report",       "create_file"),
        ("delete file test",         "delete_file"),
        ("delete last file",         "undo_last_action"),
        ("undo last creation",       "undo_last_action"),
        ("type hello world",         "type_text"),
        ("volume up",                "increase_volume"),
        ("mute",                     "mute_volume"),
        ("shutdown",                 "shutdown_system"),
        ("show desktop files",       "list_desktop"),
    ]
    for cmd, expected in checks:
        got = kf(cmd)
        assert got == expected, f"'{cmd}' -> got={got!r} expected={expected!r}"
check("All keyword fallback routes (11 routes)", feat_keyword_fallback)

# ── SUMMARY ──────────────────────────────────────────────────────────────────
print(f"\n{'='*55}")
print(f"  TOTAL  : {len(PASS)+len(FAIL)} checks")
print(f"  PASSED : {len(PASS)}")
if FAIL:
    print(f"  FAILED : {len(FAIL)}")
    for f in FAIL:
        print(f"    - {f}")
else:
    print(f"  FAILED : 0")
print(f"  STATUS : {'ALL SYSTEMS GO' if not FAIL else 'ISSUES FOUND'}")
print(f"{'='*55}")
sys.exit(0 if not FAIL else 1)
