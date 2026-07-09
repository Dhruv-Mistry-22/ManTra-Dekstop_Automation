import sys
sys.path.insert(0, '.')
from modules.intent_module import _keyword_fallback

tests = [
    ('delete last file',             'undo_last_action'),
    ('undo last creation',           'undo_last_action'),
    ('delete what you just created', 'undo_last_action'),
    ('show desktop files',           'list_desktop'),
    ('undo that action',             'undo_action'),   # should NOT be undo_last
    ('type hello',                   'type_text'),
    ('write good morning',           'type_text'),
    ('open chrome',                  'open_app'),
    ('close notepad',                'close_app'),
    ('create file test',             'create_file'),
    ('delete file report',           'delete_file'),
    ('shutdown',                     'shutdown_system'),
    ('volume up',                    'increase_volume'),
    ('mute',                         'mute_volume'),
]

all_ok = True
for cmd, expected in tests:
    got = _keyword_fallback(cmd)
    ok = got == expected
    if not ok:
        all_ok = False
    print(f"  {'OK  ' if ok else 'FAIL'} '{cmd}' -> got={got!r}  expected={expected!r}")

print()
print('ALL FALLBACK TESTS PASSED' if all_ok else 'SOME FALLBACK TESTS FAILED')
