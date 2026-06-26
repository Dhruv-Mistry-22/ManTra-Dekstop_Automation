# modules/nlp_module.py
# Mantra V2 — NLP Processing Module (REWRITE)
# Replaces V1 NLTK keyword extractor with a spaCy pipeline.
#
# Key V1 bugs fixed:
#   - Negation words ('don't', 'stop', 'never') are NO LONGER stripped.
#     spaCy detects them via dependency arc dep_='neg' and sets negated=True.
#   - Intent now understands paraphrasing via sentence-transformers (intent_module).
#   - Named entities (app names, file paths, numbers) are extracted automatically.
#
# Output of process_command() is a structured dict — not just a keyword list.
# Every downstream module (intent, execution, memory) works from this dict.

import re
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# ── spaCy model ───────────────────────────────────────────────────────────────
# en_core_web_md is the medium model: includes word vectors (needed for
# similarity), POS tags, dependency parse, and named entity recognition.
# Install: python -m spacy download en_core_web_md
_nlp = None

def _load_nlp():
    global _nlp
    if _nlp is not None:
        return _nlp
    try:
        import spacy
        _nlp = spacy.load("en_core_web_md")
        logger.info("[nlp] spaCy model loaded: en_core_web_md")
    except OSError:
        # Model not downloaded yet — give a clear actionable error
        raise RuntimeError(
            "[nlp] spaCy model 'en_core_web_md' not found.\n"
            "Run this command to fix it:\n"
            "    python -m spacy download en_core_web_md"
        )
    return _nlp


# ── Stop words we DO NOT remove ───────────────────────────────────────────────
# These are critical for negation and command meaning.
# spaCy has its own stop word set; we use it but protect these words.
_NEGATION_WORDS = {"not", "no", "never", "don't", "dont", "cannot", "can't",
                   "won't", "wont", "without"}

# Words that are structurally important for command parsing — never remove.
_PROTECTED_WORDS = _NEGATION_WORDS | {
    "up", "down", "all", "file", "folder", "app", "system", "text",
    "open", "close", "create", "delete", "rename", "move", "list",
    "search", "find", "type", "copy", "paste", "undo", "redo",
    "lock", "sleep", "mute", "shutdown", "restart", "logout",
    "volume", "window", "active", "switch", "run", "start",
    "record", "macro", "screen", "read", "info"
}


# ── Public API ────────────────────────────────────────────────────────────────
def process_command(command: str) -> dict:
    """
    Parse a raw text command and return a structured dict.

    Returns:
    {
        "raw":      "don't open chrome",          # original input
        "cleaned":  "don't open chrome",          # whitespace-normalised
        "keywords": ["open", "chrome"],           # content words (no stop words, but negation preserved separately)
        "negated":  True,                         # True if command contains negation
        "negation_target": "open",                # the verb being negated (if found)
        "entities": {
            "app":    "chrome",                   # detected app name
            "file":   None,
            "path":   None,
            "number": None,
        },
        "tokens": [                               # full token info for intent_module
            {"text": "do", "pos": "AUX",  "dep": "aux",    "is_negation": False},
            {"text": "n't","pos": "PART", "dep": "neg",    "is_negation": True},
            {"text": "open","pos": "VERB","dep": "ROOT",   "is_negation": False},
            {"text": "chrome","pos":"PROPN","dep":"dobj",  "is_negation": False},
        ]
    }

    Example usage:
        parsed = process_command("don't open chrome")
        parsed["negated"]          # True
        parsed["keywords"]         # ["open", "chrome"]
        parsed["entities"]["app"]  # "chrome"
    """
    if not command or not isinstance(command, str):
        return _empty_result("")

    nlp = _load_nlp()

    # Normalise: lowercase, collapse whitespace, strip leading/trailing spaces
    cleaned = re.sub(r'\s+', ' ', command.strip().lower())

    doc = nlp(cleaned)

    # ── 1. Negation detection ─────────────────────────────────────────────────
    # A token has dep_='neg' when it is a negation modifier of another word.
    # Example: "don't open" → "n't" has dep_='neg', head is "open" (the verb).
    negated = False
    negation_target = None

    for token in doc:
        if token.dep_ == "neg" or token.text in _NEGATION_WORDS:
            negated = True
            # The head of the negation token is what's being negated
            if token.dep_ == "neg" and token.head.pos_ in ("VERB", "AUX"):
                negation_target = token.head.lemma_
            break

    # ── 2. Keyword extraction ─────────────────────────────────────────────────
    # Keep: NOUN, PROPN, VERB, ADJ, ADV that are not pure stop words
    # Always keep PROTECTED_WORDS even if spaCy marks them as stop words.
    keywords = []
    for token in doc:
        t = token.text.lower()
        # Skip punctuation and whitespace
        if token.is_punct or token.is_space:
            continue
        # Skip spaCy stop words UNLESS they are in our protected set
        if token.is_stop and t not in _PROTECTED_WORDS:
            continue
        # Skip pure negation tokens themselves (already captured above)
        if token.dep_ == "neg":
            continue
        # Only keep meaningful POS tags
        if token.pos_ in ("NOUN", "PROPN", "VERB", "ADJ", "ADV", "NUM", "X"):
            keywords.append(t)
        # Also keep any token in the protected list regardless of POS
        elif t in _PROTECTED_WORDS:
            keywords.append(t)

    # Deduplicate while preserving order
    seen = set()
    keywords = [k for k in keywords if not (k in seen or seen.add(k))]

    # ── 3. Entity extraction ─────────────────────────────────────────────────
    entities = _extract_entities(doc, cleaned, keywords)

    # ── 4. Token debug info ───────────────────────────────────────────────────
    tokens = [
        {
            "text":         t.text,
            "lemma":        t.lemma_,
            "pos":          t.pos_,
            "dep":          t.dep_,
            "is_negation":  (t.dep_ == "neg" or t.text in _NEGATION_WORDS),
        }
        for t in doc if not t.is_space
    ]

    return {
        "raw":              command,
        "cleaned":          cleaned,
        "keywords":         keywords,
        "negated":          negated,
        "negation_target":  negation_target,
        "entities":         entities,
        "tokens":           tokens,
    }


def _extract_entities(doc, cleaned: str, keywords: list) -> dict:
    """
    Extract structured entities from the parsed doc.
    Returns a dict with keys: app, file, path, number.
    Values are strings or None.
    """
    entities = {
        "app":    None,
        "file":   None,
        "path":   None,
        "number": None,
    }

    # ── File path detection (Windows paths like C:\Users\...) ─────────────────
    path_match = re.search(r'[a-zA-Z]:\\[\w\\\s\-\.]+', cleaned)
    if path_match:
        entities["path"] = path_match.group(0).strip()

    # ── File name detection (.ext pattern) ───────────────────────────────────
    file_match = re.search(r'\b([\w\-]+\.\w{2,5})\b', cleaned)
    if file_match:
        entities["file"] = file_match.group(1)

    # ── Number detection ──────────────────────────────────────────────────────
    for token in doc:
        if token.like_num or token.pos_ == "NUM":
            entities["number"] = token.text
            break

    # ── App name heuristic ────────────────────────────────────────────────────
    # PROPN (proper noun) tokens that are not file names or path components
    # are likely app names. Also check against the known app keyword list.
    _KNOWN_APP_KEYWORDS = {
        "chrome", "firefox", "edge", "opera", "brave", "safari",
        "notepad", "wordpad", "word", "excel", "powerpoint", "outlook",
        "vlc", "discord", "telegram", "whatsapp", "slack", "teams",
        "spotify", "steam", "blender", "gimp", "pycharm", "intellij",
        "calculator", "paint", "zoom", "skype", "obs", "audacity",
        "7zip", "winrar", "putty", "filezilla", "thunderbird",
        "vs", "code", "visual", "studio", "atom", "sublime",
    }
    for token in doc:
        t = token.text.lower()
        if token.pos_ in ("PROPN", "NOUN") and t in _KNOWN_APP_KEYWORDS:
            entities["app"] = t
            break
    # Fallback: last keyword that looks like an app name
    if not entities["app"]:
        for kw in reversed(keywords):
            if kw in _KNOWN_APP_KEYWORDS:
                entities["app"] = kw
                break

    return entities


def _empty_result(command: str) -> dict:
    """Return a safe empty result for blank or invalid input."""
    return {
        "raw":             command,
        "cleaned":         "",
        "keywords":        [],
        "negated":         False,
        "negation_target": None,
        "entities":        {"app": None, "file": None, "path": None, "number": None},
        "tokens":          [],
    }
