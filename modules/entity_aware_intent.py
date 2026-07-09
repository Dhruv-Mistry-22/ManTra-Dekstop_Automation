"""
entity_aware_intent.py — Mantra V2 Hybrid NLP Fix
==================================================
Problem diagnosed from benchmark:
  - V2 cosine similarity collapses on OOV nouns (vlc, steam, discord)
  - Named entities skew the embedding toward wrong intent clusters
  
Fix: strip named entities BEFORE embedding, re-inject AFTER matching.
This is the "entity-aware" pipeline described in the research paper.

Drop this file into modules/ and update intent_module.py to use it.
"""

import re

# ── Known entity lists (expand these from your registry scanner) ─────────────
KNOWN_APPS = {
    "chrome", "firefox", "edge", "brave", "opera",           # browsers
    "spotify", "vlc", "itunes", "winamp", "musicbee",        # media
    "notepad", "vscode", "code", "sublime", "vim",            # editors
    "discord", "slack", "teams", "zoom", "skype",             # comms
    "excel", "word", "powerpoint", "onenote", "outlook",      # office
    "steam", "epic", "origin", "battlenet", "gog",            # gaming
    "chrome", "explorer", "files", "calculator", "paint",     # system
    "cmd", "powershell", "terminal", "task manager",
}

FILE_EXTENSIONS = {
    ".txt", ".pdf", ".docx", ".xlsx", ".pptx", ".csv",
    ".py", ".js", ".html", ".css", ".json", ".zip",
    ".png", ".jpg", ".mp3", ".mp4", ".exe",
}

FOLDER_NAMES = {
    "downloads", "documents", "desktop", "pictures", "videos",
    "music", "projects", "backup", "archive", "work", "temp",
}

# ── Negation markers — must be detected BEFORE entity stripping ───────────────
NEGATION_MARKERS = {
    "don't", "dont", "do not", "never", "not", "no",
    "stop", "cancel", "abort", "forget", "nevermind",
    "actually don't", "wait don't",
}


def extract_entities(utterance: str) -> dict:
    """
    Extract named entities from utterance before NLP processing.
    Returns dict with entity type and value.
    
    Examples:
      "open chrome"          -> {type: "app",    value: "chrome"}
      "delete report.txt"    -> {type: "file",   value: "report.txt"}
      "create folder backup" -> {type: "folder", value: "backup"}
      "launch vlc"           -> {type: "app",    value: "vlc"}
    """
    u = utterance.lower().strip()
    entities = {"app": None, "file": None, "folder": None}

    # Check for file with extension (most specific — check first)
    for token in u.split():
        for ext in FILE_EXTENSIONS:
            if token.endswith(ext):
                entities["file"] = token
                break

    # Check for known app names
    for app in KNOWN_APPS:
        if app in u:
            entities["app"] = app
            break

    # Check for known folder names
    for folder in FOLDER_NAMES:
        if folder in u:
            entities["folder"] = folder
            break

    # If no known app found, try to extract unknown noun after verb
    # e.g. "open steam" — steam is unknown but follows "open"
    verb_patterns = [
        r"(?:open|launch|start|run|close|quit|kill|switch to|bring up|fire up|pull up)\s+(\w+)",
    ]
    if not entities["app"]:
        for pattern in verb_patterns:
            match = re.search(pattern, u)
            if match:
                candidate = match.group(1)
                # Only treat as app if it is not a common English word
                common_words = {"the","a","an","this","that","it","my","me","all","some","new","old"}
                if candidate not in common_words:
                    entities["app"] = candidate
                    break

    return entities


def normalize_utterance(utterance: str) -> tuple[str, dict]:
    """
    Replace named entities with placeholders before embedding.
    
    "open vlc"          -> "open [APP]",     {app: "vlc"}
    "delete report.txt" -> "delete [FILE]",  {file: "report.txt"}
    "move report to downloads" -> "move [FILE] to [FOLDER]", {...}
    
    This prevents OOV nouns from skewing cosine similarity.
    Returns: (normalized_utterance, entities_dict)
    """
    u = utterance.lower().strip()
    entities = extract_entities(u)

    normalized = u

    # Replace file entity
    if entities["file"]:
        normalized = normalized.replace(entities["file"], "[FILE]")

    # Replace app entity
    if entities["app"]:
        normalized = normalized.replace(entities["app"], "[APP]")

    # Replace folder entity
    if entities["folder"]:
        normalized = normalized.replace(entities["folder"], "[FOLDER]")

    return normalized, entities


def detect_negation(utterance: str) -> bool:
    """
    Detect negation BEFORE any stop-word stripping.
    This is the V1 bug fix — V1 stripped 'don't' as a stop word.
    
    Returns True if command should be intercepted as negation.
    """
    u = utterance.lower().strip()
    for marker in NEGATION_MARKERS:
        if u.startswith(marker) or f" {marker} " in u or u == marker:
            return True
    return False


def hybrid_predict(utterance: str, model, intent_embeddings, intent_labels) -> tuple[str, str, float]:
    """
    Full hybrid pipeline:
    1. Detect negation first (before any stripping)
    2. Extract named entities
    3. Normalize utterance (replace entities with placeholders)
    4. Run cosine similarity on normalized utterance
    5. Return intent + extracted entity
    
    Returns: (intent, entity_value, confidence)
    """
    import torch
    import torch.nn.functional as F

    # Step 1 — negation check (catches V1's biggest failure)
    if detect_negation(utterance):
        return "negation", "", 1.0

    # Step 2 + 3 — extract and normalize
    normalized, entities = normalize_utterance(utterance)

    # Step 4 — embed normalized utterance
    emb = model.encode([normalized], convert_to_tensor=True)
    sims = F.cosine_similarity(emb, intent_embeddings)
    best_idx = int(sims.argmax())
    confidence = float(sims[best_idx])

    # Low confidence threshold — ask for clarification
    if confidence < 0.38:
        return "ambiguous", "", confidence

    intent = intent_labels[best_idx]

    # Step 5 — determine entity to return
    entity = ""
    if entities["app"]:
        entity = entities["app"]
    elif entities["file"]:
        entity = entities["file"]
    elif entities["folder"]:
        entity = entities["folder"]

    return intent, entity, confidence


# ── Updated intent embeddings using PLACEHOLDERS ─────────────────────────────
# These are the normalized versions — [APP] replaces actual app names
# so the model never sees OOV nouns during matching

NORMALIZED_INTENT_EXAMPLES = {
    "open_app":        ["open [APP]", "launch [APP]", "start [APP]",
                        "bring up [APP]", "fire up [APP]", "run [APP]",
                        "pull up [APP]", "i want to use [APP]"],
    "close_app":       ["close [APP]", "quit [APP]", "exit [APP]",
                        "kill [APP]", "shut down [APP]", "terminate [APP]"],
    "list_apps":       ["list running apps", "show all open apps",
                        "what apps are running", "show processes"],
    "switch_app":      ["switch to [APP]", "bring [APP] to front",
                        "focus on [APP]", "go to [APP]"],
    "create_file":     ["create [FILE]", "make a new [FILE]",
                        "create a file [FILE]", "make file [FILE]"],
    "create_folder":   ["create [FOLDER]", "make a directory [FOLDER]",
                        "new folder [FOLDER]", "mkdir [FOLDER]"],
    "delete_file":     ["delete [FILE]", "remove [FILE]", "trash [FILE]",
                        "get rid of [FILE]", "erase [FILE]"],
    "rename_file":     ["rename [FILE]", "change the file name",
                        "rename [FILE] to [FILE]"],
    "move_file":       ["move [FILE] to [FOLDER]", "transfer [FILE]",
                        "relocate [FILE] to [FOLDER]"],
    "search_files":    ["search for [FILE]", "find [FILE]",
                        "look for [FILE]", "where is [FILE]"],
    "open_file":       ["open [FILE]", "show me [FILE]", "view [FILE]"],
    "list_directory":  ["list files in [FOLDER]", "show contents of [FOLDER]",
                        "what files are in [FOLDER]"],
    "shutdown_system": ["shutdown the computer", "power off", "turn off the pc"],
    "restart_system":  ["restart the computer", "reboot windows", "restart now"],
    "lock_system":     ["lock the screen", "lock my computer", "lock it"],
    "sleep_system":    ["sleep mode", "go to sleep", "put it to sleep"],
    "logout_user":     ["log me out", "sign out", "log out of windows"],
    "increase_volume": ["volume up", "make it louder", "turn up the volume",
                        "increase the sound"],
    "decrease_volume": ["volume down", "make it quieter", "lower the sound",
                        "turn down the volume"],
    "mute_volume":     ["mute", "silence the audio", "mute the sound", "unmute"],
    "get_system_info": ["system info", "what are my specs", "show cpu usage",
                        "how much ram am i using"],
    "type_text":       ["type how are you", "write good morning", "type this message",
                        "input text here", "type some words", "write a sentence",
                        "say hello there", "enter the text", "type thank you"],

    "copy_text":       ["copy", "copy the text", "ctrl c", "copy that"],
    "paste_text":      ["paste", "paste here", "ctrl v", "paste the text"],
    "select_all":      ["select all", "highlight all text", "ctrl a",
                        "select everything"],
    "undo_action":     ["undo", "undo that", "take that back", "undo last action"],
    "redo_action":     ["redo", "redo that", "redo the last thing"],
    "negation":        ["don't open", "do not launch", "cancel that",
                        "forget it", "nevermind", "abort", "stop that"],
    "ambiguous":       ["open it", "do the thing", "start", "run it",
                        "make a file", "open the app"],
    "multi_step":      ["open [APP] then close [APP]", "search then open it",
                        "create [FOLDER] then move [FILE] into it"],
    "context_close":   ["close it", "shut it down", "close the last one"],
    "context_open":    ["open it again", "bring it back up", "open that again"],
    "context_delete":  ["delete that", "delete the last file"],
    "context_rename":  ["rename that file", "rename it"],
    "context_move":    ["move that to [FOLDER]"],
    "context_repeat":  ["do that again"],
    "context_undo":    ["undo what you just did"],
    "context_switch":  ["switch back to it"],
    "context_search":  ["search for it", "where did you put it"],
    "context_copy":    ["copy that file"],
    "undo_last_action": [
        "delete what you just created", "undo last creation",
        "remove the file you just made", "delete the last file you created",
        "undo that file creation", "delete last", "cancel the last creation",
        "remove what you just created",
    ],
    "list_desktop": [
        "show desktop files", "what is on my desktop",
        "list desktop contents", "show me my desktop",
        "what files are on the desktop", "list files on desktop",
    ],
}



def build_normalized_embeddings(model):
    """Build embedding matrix using placeholder-normalized examples."""
    all_phrases, all_labels = [], []
    for intent, phrases in NORMALIZED_INTENT_EXAMPLES.items():
        for phrase in phrases:
            all_phrases.append(phrase)
            all_labels.append(intent)
    embeddings = model.encode(
        all_phrases, convert_to_tensor=True, show_progress_bar=False
    )
    return embeddings, all_labels


# ── Quick self-test ───────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("Testing entity extraction and negation detection...\n")

    test_cases = [
        ("open chrome",           False, {"app": "chrome"}),
        ("launch vlc",            False, {"app": "vlc"}),
        ("open steam",            False, {"app": "steam"}),
        ("delete report.txt",     False, {"file": "report.txt"}),
        ("create folder backup",  False, {"folder": "backup"}),
        ("don't open chrome",     True,  {}),
        ("do not launch spotify", True,  {}),
        ("never close notepad",   True,  {}),
        ("don't shutdown",        True,  {}),
        ("cancel that",           True,  {}),
        ("move report.txt to downloads", False, {"file": "report.txt", "folder": "downloads"}),
    ]

    all_pass = True
    for utterance, expect_neg, expect_entities in test_cases:
        neg = detect_negation(utterance)
        _, entities = normalize_utterance(utterance)
        
        neg_ok = (neg == expect_neg)
        ent_ok = all(entities.get(k) == v for k, v in expect_entities.items())
        status = "PASS" if (neg_ok and ent_ok) else "FAIL"
        if status == "FAIL":
            all_pass = False

        print(f"  [{status}] '{utterance}'")
        if not neg_ok:
            print(f"         negation: expected={expect_neg} got={neg}")
        if not ent_ok:
            print(f"         entities: expected={expect_entities} got={dict(entities)}")
        else:
            norm, ents = normalize_utterance(utterance)
            print(f"         normalized='{norm}'  entities={dict((k,v) for k,v in ents.items() if v)}")

    print(f"\n{'All tests passed!' if all_pass else 'Some tests failed — review above.'}")
    print("\nTo integrate into Mantra:")
    print("  1. Copy this file to modules/entity_aware_intent.py")
    print("  2. In intent_module.py, import hybrid_predict and")
    print("     build_normalized_embeddings from this module")
    print("  3. Replace the direct cosine similarity call with hybrid_predict()")
    print("  4. Re-run benchmark.py to measure the accuracy improvement")
