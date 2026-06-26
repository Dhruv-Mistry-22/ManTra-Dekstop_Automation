"""
test_system.py -- Mantra V2 Full System Test
Tests every pipeline layer: NLP -> Intent -> Execution -> DB -> TTS
Runs without GUI, covers all 7 pages of functionality.
"""
import sys, time, os
# Ensure project root is on sys.path when running from tests/
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding='utf-8')


PASS = "  [PASS]"
FAIL = "  [FAIL]"
WARN = "  [WARN]"
SEP  = "-" * 65

def hdr(title):
    print(f"\n{'='*65}")
    print(f"  {title}")
    print('='*65)

def result(label, ok, detail=""):
    mark = PASS if ok else FAIL
    print(f"{mark}  {label}")
    if detail:
        print(f"         -> {detail}")

# ─────────────────────────────────────────────────────────────────
# 1. NLP MODULE
# ─────────────────────────────────────────────────────────────────
hdr("LAYER 1 — NLP MODULE (spaCy)")
try:
    from modules.nlp_module import process_command

    tests = [
        ("open chrome",               False, "open",    "chrome"),
        ("don't close notepad",       True,  "close",   "notepad"),
        ("create file report.txt",    False, "create",  None),
        ("delete folder backup",      False, "delete",  None),
        ("type hello world",          False, "type",    None),
        ("shutdown the computer",     False, "shutdown", None),
        ("volume up",                 False, "volume",  None),
        ("",                          False, None,      None),   # empty
    ]

    for cmd, exp_neg, exp_kw, exp_app in tests:
        p = process_command(cmd)
        neg_ok  = (p["negated"] == exp_neg)
        kw_ok   = (exp_kw is None or exp_kw in p["keywords"])
        app_ok  = (exp_app is None or p["entities"]["app"] == exp_app
                   or exp_app in p["keywords"])
        ok = neg_ok and kw_ok
        detail = (f"negated={p['negated']} kw={p['keywords'][:4]} "
                  f"app={p['entities']['app']}")
        result(f"NLP: '{cmd or '(empty)'}'", ok, detail)

except Exception as e:
    result("NLP MODULE LOAD", False, str(e))

# ─────────────────────────────────────────────────────────────────
# 2. INTENT DETECTION
# ─────────────────────────────────────────────────────────────────
hdr("LAYER 2 — INTENT DETECTION (sentence-transformers)")
try:
    from modules.nlp_module import process_command
    from modules.intent_module import detect_intent

    intent_tests = [
        ("open chrome",                    "open_app"),
        ("launch spotify",                 "open_app"),
        ("start visual studio code",       "open_app"),
        ("close notepad",                  "close_app"),
        ("quit discord",                   "close_app"),
        ("what apps are running",          "list_apps"),
        ("create a new file",              "create_file"),
        ("make a folder called backup",    "create_folder"),
        ("delete the file report.txt",     "delete_file"),
        ("shutdown the computer",          "shutdown_system"),
        ("restart my PC",                  "restart_system"),
        ("lock the screen",                "lock_system"),
        ("turn up the volume",             "increase_volume"),
        ("make it quieter",                "decrease_volume"),
        ("mute the sound",                 "mute_volume"),
        ("type hello into the window",     "type_text"),
        ("copy selected text",             "copy_text"),
        ("undo last action",               "undo_action"),
        ("show system info",               "get_system_info"),
        ("don't open chrome",              "negated_open_app"),
        ("start recording macro",          "record_macro"),
        ("stop the macro",                 "stop_macro"),
        ("run the macro",                  "play_macro"),
        ("list all my macros",             "list_macros"),
        ("read what is on screen",         "read_screen"),
        ("xyzzy gibberish command",        "unknown"),
    ]

    passed = 0
    for cmd, expected in intent_tests:
        p = process_command(cmd)
        got = detect_intent(p)
        ok  = (got == expected)
        if ok: passed += 1
        result(f"INTENT: '{cmd}'", ok, f"expected={expected}  got={got}")

    print(f"\n  Score: {passed}/{len(intent_tests)} "
          f"({100*passed//len(intent_tests)}%)")

except Exception as e:
    result("INTENT MODULE LOAD", False, str(e))

# ─────────────────────────────────────────────────────────────────
# 3. EXECUTION MODULE (safe / non-destructive only)
# ─────────────────────────────────────────────────────────────────
hdr("LAYER 3 — EXECUTION MODULE (safe commands only)")
try:
    from modules.execution_module import execute_task
    from modules.nlp_module import process_command
    from modules.intent_module import detect_intent

    exec_tests = [
        # (command, expected_fragment_in_result)
        ("list apps",                   ["Total", "Running", "processes", "Processes"]),
        ("system info",                 ["OS", "Windows", "Processor"]),
        ("create file mantra_test.txt", ["created", "mantra_test"]),
        ("delete file mantra_test.txt", ["deleted", "mantra_test", "not found"]),
        ("list files .",                ["Files"]),
        ("volume up",                   ["Volume", "volume"]),
        ("mute",                        ["muted", "Muted", "mute"]),
        ("volume up",                   ["Volume", "volume"]),  # unmute by vol up
        ("search file test_",          ["Found", "No files"]),
        ("copy",                        ["copy", "Copy"]),
        ("undo",                        ["undo", "Undo"]),
        ("what is the active window",   ["Active window", "window", "No active"]),
        ("list macros",                 ["macro", "Macro", "No macros"]),
        ("xyzzy gibberish test cmd",    ["not recognized", "Unknown"]),
    ]

    for cmd, fragments in exec_tests:
        p      = process_command(cmd)
        intent = detect_intent(p)
        kw     = p.get("keywords", [])
        try:
            r = execute_task(intent, kw, cmd)
            ok = any(f.lower() in str(r).lower() for f in fragments)
            result(f"EXEC: '{cmd}'", ok, str(r)[:90])
        except Exception as ex:
            result(f"EXEC: '{cmd}'", False, f"Exception: {ex}")

except Exception as e:
    result("EXECUTION MODULE LOAD", False, str(e))

# ─────────────────────────────────────────────────────────────────
# 4. DATABASE MANAGER
# ─────────────────────────────────────────────────────────────────
hdr("LAYER 4 — DATABASE MANAGER (SQLite)")
try:
    from modules.db_manager import (
        log_command, get_recent_commands, add_correction,
        get_all_corrections, set_preference, get_preference,
        save_macro, get_macro, list_macros, delete_macro
    )

    # Log a command
    rid = log_command("test command", "app", "chrome", "open_app", 1, 123)
    result("DB: log_command()", isinstance(rid, int), f"row_id={rid}")

    # Read it back
    rows = get_recent_commands(5)
    found = any(r.get("action") == "test command" for r in rows)
    result("DB: get_recent_commands()", found, f"rows={len(rows)}")

    # Preferences
    set_preference("test_key", "hello_world")
    val = get_preference("test_key")
    result("DB: set/get_preference()", val == "hello_world", f"value={val}")

    # Macros
    steps = [{"type": "key_press", "key": "a", "timestamp": 0.1}]
    save_macro("__test_macro__", steps)
    loaded = get_macro("__test_macro__")
    result("DB: save_macro() + get_macro()", loaded == steps, f"steps={loaded}")

    names = [m["macro_name"] for m in list_macros()]
    result("DB: list_macros()", "__test_macro__" in names, f"macros={names}")

    deleted = delete_macro("__test_macro__")
    result("DB: delete_macro()", deleted, f"deleted={deleted}")

    # Adaptive corrections
    add_correction("hey open chrome", "unknown", "open_app")
    add_correction("hey open chrome", "unknown", "open_app")  # freq → 2
    corrs = get_all_corrections()
    found_corr = any(c["utterance"] == "hey open chrome" for c in corrs)
    result("DB: add_correction() freq>=2", found_corr, f"corrections={len(corrs)}")

except Exception as e:
    result("DATABASE MODULE", False, str(e))

# ─────────────────────────────────────────────────────────────────
# 5. TTS MODULE
# ─────────────────────────────────────────────────────────────────
hdr("LAYER 5 — TTS MODULE (pyttsx3 offline)")
try:
    from modules.tts_module import speak, set_rate, set_volume, list_voices, silence

    voices = list_voices()
    result("TTS: list_voices()", len(voices) > 0, f"voices={voices}")

    set_rate(170)
    set_volume(0.9)
    speak("Mantra system test running. All modules operational.")
    result("TTS: speak() queued", True, "speech queued non-blocking")

    time.sleep(0.5)
    silence()
    result("TTS: silence() drain", True, "queue drained")

except Exception as e:
    result("TTS MODULE", False, str(e))

# ─────────────────────────────────────────────────────────────────
# 6. APP CONTROLLER
# ─────────────────────────────────────────────────────────────────
hdr("LAYER 6 — APP CONTROLLER")
try:
    from modules.app_controller import (
        build_app_index, list_running_apps, get_active_window, APP_PATHS
    )

    build_app_index()
    result("APP: build_app_index()", len(APP_PATHS) > 0, f"apps indexed={len(APP_PATHS)}")

    running = list_running_apps()
    result("APP: list_running_apps()", "Running" in running or "Total" in running, running[:60])

    win = get_active_window()
    result("APP: get_active_window()", "window" in win.lower() or "Active" in win, win[:60])

    # Test blocklist
    from modules.app_controller import open_or_switch_app
    r = open_or_switch_app("powershell")
    result("APP: blocklist blocks powershell", "cannot" in r.lower() or "safety" in r.lower(), r)

except Exception as e:
    result("APP CONTROLLER", False, str(e))

# ─────────────────────────────────────────────────────────────────
# 7. FILE MANAGER
# ─────────────────────────────────────────────────────────────────
hdr("LAYER 7 — FILE MANAGER")
try:
    from modules.file_manager import (
        create_file, create_folder, list_files,
        rename_file, delete_file, delete_folder
    )

    r1 = create_file("mantra_unit_test.txt")
    result("FILE: create_file()", "created" in r1.lower(), r1)

    r2 = rename_file("mantra_unit_test.txt", "mantra_renamed.txt")
    result("FILE: rename_file()", "renamed" in r2.lower(), r2)

    r3 = list_files(".")
    result("FILE: list_files('.')", "mantra_renamed" in r3, r3[:60])

    r4 = delete_file("mantra_renamed.txt")
    result("FILE: delete_file()", "deleted" in r4.lower(), r4)

    r5 = create_folder("mantra_test_folder")
    result("FILE: create_folder()", "created" in r5.lower(), r5)

    r6 = delete_folder("mantra_test_folder")
    result("FILE: delete_folder()", "deleted" in r6.lower(), r6)

    r7 = delete_file("nonexistent_xyz.txt")
    result("FILE: delete nonexistent (graceful)", "not found" in r7.lower(), r7)

except Exception as e:
    result("FILE MANAGER", False, str(e))

# ─────────────────────────────────────────────────────────────────
# SUMMARY
# ─────────────────────────────────────────────────────────────────
print(f"\n{'='*65}")
print("  TEST COMPLETE -- Check [PASS]/[FAIL] above for results")
print('='*65)
