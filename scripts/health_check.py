"""Full health check for ManTra — run before every release."""
import sys, ast, os
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

# ── 1. Syntax check every module ──────────────────────────────────────────────
FILES = [
    'modules/execution_module.py', 'modules/file_manager.py',
    'modules/intent_module.py', 'modules/entity_aware_intent.py',
    'modules/input_module.py', 'modules/nlp_module.py',
    'modules/tts_module.py', 'modules/db_manager.py',
    'modules/app_controller.py', 'modules/system_control.py',
    'modules/text_input_assistant.py', 'modules/response_module.py',
    'core/context_memory.py', 'core/adaptive_learning.py',
    'main.py', 'mantra.py',
]
for f in FILES:
    def _syn(f=f):
        with open(f, encoding='utf-8') as fh: src = fh.read()
        ast.parse(src)
    check(f"syntax:{f.split('/')[-1]}", _syn)

# ── 2. Import checks ──────────────────────────────────────────────────────────
def imp_file_manager():
    from modules.file_manager import (
        build_file_index, search_files, open_file, open_folder,
        create_file, create_folder, delete_file, delete_folder,
        rename_file, rename_folder, move_file, list_files,
        list_desktop_files, undo_last_creation
    )
check("import:file_manager (14 exports)", imp_file_manager)

def imp_execution():
    from modules.execution_module import (
        execute_task, remove_action_keyword,
        _extract_filename, _extract_foldername, _sanitize_name
    )
check("import:execution_module", imp_execution)

def imp_intents():
    from modules.intent_module import INTENT_EXAMPLES, _keyword_fallback
    assert 'undo_last_action' in INTENT_EXAMPLES
    assert 'list_desktop' in INTENT_EXAMPLES
    assert 'type_text' in INTENT_EXAMPLES
    assert len(INTENT_EXAMPLES) >= 37
check("import:intent_module (37+ intents)", imp_intents)

def imp_entity():
    from modules.entity_aware_intent import NORMALIZED_INTENT_EXAMPLES
    assert 'undo_last_action' in NORMALIZED_INTENT_EXAMPLES
    assert 'list_desktop' in NORMALIZED_INTENT_EXAMPLES
    assert len(NORMALIZED_INTENT_EXAMPLES) >= 40
check("import:entity_aware_intent (40+ normalized)", imp_entity)

def imp_db():
    from modules.db_manager import init_db, log_command, get_recent_commands
check("import:db_manager", imp_db)

# ── 3. _extract_filename logic ─────────────────────────────────────────────────
def logic_extract():
    from modules.execution_module import _extract_filename, _extract_foldername
    assert _extract_filename(['create','file','report'], 'create file report') == 'report.txt'
    assert _extract_filename(['create','file','report.pdf'], 'create file report.pdf') == 'report.pdf'
    assert _extract_filename(['create','file'], 'create file called notes') == 'notes.txt'
    assert _extract_filename([], 'create file') == 'newfile.txt'
    assert _extract_foldername(['create','folder'], 'create folder named projects') == 'projects'
    assert _extract_foldername([], 'create folder') == 'newfolder'
check("logic:_extract_filename + _extract_foldername", logic_extract)

# ── 4. type_text regex ─────────────────────────────────────────────────────────
def logic_type():
    import re
    pat = r'\b(?:type|write|input|say|enter|write\s+out)\s+(.+)'
    # Note: production code runs regex on full_command.lower()
    assert re.search(pat, 'type how are you').group(1) == 'how are you'
    assert re.search(pat, 'write good morning').group(1) == 'good morning'
    assert re.search(pat, 'say hello there').group(1) == 'hello there'
    assert re.search(pat, 'type i am fine').group(1) == 'i am fine'   # lowercased
check("logic:type_text regex (stop words preserved)", logic_type)

# ── 5. keyword_fallback all routes ────────────────────────────────────────────
def logic_fallback():
    from modules.intent_module import _keyword_fallback as kf
    assert kf('delete last file')             == 'undo_last_action', kf('delete last file')
    assert kf('undo last creation')           == 'undo_last_action'
    assert kf('delete what you just created') == 'undo_last_action'
    assert kf('show desktop files')           == 'list_desktop'
    assert kf('undo that action')             == 'undo_action'   # NOT undo_last
    assert kf('type hello')                   == 'type_text'
    assert kf('write good morning')           == 'type_text'
    assert kf('open chrome')                  == 'open_app'
    assert kf('close notepad')               == 'close_app'
    assert kf('create file test')             == 'create_file'
    assert kf('delete file report')           == 'delete_file'
    assert kf('shutdown')                     == 'shutdown_system'
    assert kf('volume up')                    == 'increase_volume'
    assert kf('mute')                         == 'mute_volume'
check("logic:keyword_fallback (14 routes)", logic_fallback)

# ── 6. ContextMemory ──────────────────────────────────────────────────────────
def logic_memory():
    from core.context_memory import MemoryBank
    m = MemoryBank(db_path='data/test_health_check.db')
    m.update('created', 'file', 'test.txt')
    m.update('opened', 'app', 'chrome')
    assert m.get_last()['entity_value'] == 'chrome'
    assert m.get_last('file')['entity_value'] == 'test.txt'
    assert m.resolve_pronoun('it') == 'chrome'
    assert m.resolve_pronoun('the file') == 'test.txt'
    # cleanup
    import os
    try: os.remove('data/test_health_check.db')
    except: pass
check("logic:ContextMemory (update/get_last/resolve_pronoun)", logic_memory)

# ── Summary ───────────────────────────────────────────────────────────────────
print()
print(f"{'='*55}")
print(f"  PASSED: {len(PASS)}/{len(PASS)+len(FAIL)}")
if FAIL:
    print(f"  FAILED: {', '.join(FAIL)}")
print(f"{'='*55}")
sys.exit(0 if not FAIL else 1)
