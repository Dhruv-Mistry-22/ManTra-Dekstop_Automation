# modules/input_module.py
# Mantra V2 — Voice Input Module (REWRITE)
# Replaces Google Speech Recognition (internet-required) with OpenAI Whisper (fully offline).
#
# Key changes from V1:
#   - No internet required after model download.
#   - Whisper 'small' model: ~244MB, ~5-10s transcription on CPU, good accuracy.
#   - Wake word detection uses rapidfuzz fuzzy matching — handles noise and partial matches.
#   - Same public function signatures as V1 so main.py needs minimal changes.
#   - get_voice_command() now returns a dict with transcript + confidence info.

import os
import logging
import threading
import tempfile
import time

# CRITICAL WINDOWS FIX: PyTorch MUST be imported on the main thread first.
# If imported inside a background QThread, c10.dll throws WinError 1114.
import torch
import whisper

logger = logging.getLogger(__name__)

# ── Whisper model ─────────────────────────────────────────────────────────────
# Loaded lazily on first call — avoids a 3-5s startup delay every launch.
# "small" = best accuracy/speed tradeoff for CPU-only systems.
_whisper_model = None
_model_lock    = threading.Lock()
WHISPER_MODEL_SIZE = "small"

def _load_whisper():
    global _whisper_model
    if _whisper_model is not None:
        return _whisper_model
    with _model_lock:
        if _whisper_model is not None:   # double-checked locking
            return _whisper_model
        try:
            import whisper
            logger.info("[input] Loading Whisper '%s' model (first run may download ~244MB)...",
                        WHISPER_MODEL_SIZE)
            _whisper_model = whisper.load_model(WHISPER_MODEL_SIZE)
            logger.info("[input] Whisper model loaded.")
        except ImportError:
            raise RuntimeError(
                "[input] openai-whisper not installed.\n"
                "Run: pip install openai-whisper"
            )
    return _whisper_model


# ── Wake word configuration ───────────────────────────────────────────────────
WAKE_WORDS = [
    "hey mantra", "hi mantra", "hello mantra",
    "wake up mantra", "wakeup mantra",
    "mantra", "hey mentor", "hi","hello","a mantra"   # common mishearings
]
WAKE_WORD_FUZZY_THRESHOLD = 75   # rapidfuzz score out of 100

# ── Audio recording settings ──────────────────────────────────────────────────
RECORD_SECONDS   = 7      # max recording window in seconds
SAMPLE_RATE      = 16000  # Whisper requires 16kHz
CHANNELS         = 1      # mono
CHUNK            = 1024   # frames per buffer


# ── Audio recording ───────────────────────────────────────────────────────────
def _record_audio(duration: int = RECORD_SECONDS):
    """
    Record audio from the default microphone for `duration` seconds.
    Returns a 1D numpy array of float32, or None on failure.
    """
    try:
        import sounddevice as sd
        import numpy as np

        print(f"[Mantra] Listening for {duration}s...")
        audio_data = sd.rec(
            int(duration * SAMPLE_RATE),
            samplerate=SAMPLE_RATE,
            channels=CHANNELS,
            dtype="float32"
        )
        sd.wait()  # block until recording is done

        # Flatten to 1D array for Whisper (bypasses ffmpeg entirely)
        return audio_data.flatten()

    except ImportError:
        logger.error("[input] sounddevice not installed. Run: pip install sounddevice numpy")
        return None
    except Exception as e:
        logger.error("[input] Audio recording failed: %s", e)
        return None


# ── Whisper transcription ─────────────────────────────────────────────────────
def _transcribe(audio_data) -> str | None:
    """
    Transcribe a raw NumPy array using the Whisper model.
    Returns the lowercase transcript string, or None on failure.
    """
    try:
        model = _load_whisper()
        result = model.transcribe(
            audio_data,
            language="en",           # force English — faster than auto-detect
            fp16=False,              # CPU-only: fp16 is not supported
            verbose=False,
            temperature=0,           # greedy decoding — most deterministic
            condition_on_previous_text=False, # reduce hallucination
            no_speech_threshold=0.6,          # better silence rejection
        )
        text = result.get("text", "").strip().lower()
        
        # Filter common Whisper hallucinations on empty/noisy audio
        hallucinations = [
            "thank you.", "thank you", "thanks.", "thanks", "thanks for watching.", 
            "thanks for watching", "you.", "you", "subscribe.", "please subscribe.",
            "i'm going to go back to the"
        ]
        
        if text in hallucinations or text.startswith("i'm going to go back to the"):
            text = ""
            
        if text:
            print(f"[Mantra] Heard: {text}")
        return text if text else None
    except Exception as e:
        logger.error("[input] Whisper transcription failed: %s", e)
        return None


# ── Wake word detection ───────────────────────────────────────────────────────
def is_wake_word(text: str) -> bool:
    """
    Check if the transcribed text contains a wake word.
    Uses rapidfuzz fuzzy matching — handles noise, accents, and Whisper mishearings.

    Examples that return True:
        "hey mantra open chrome"
        "a mantra"   (Whisper mishearing of "hey mantra")
        "wake up mantra"
        "hi mantra"
    """
    if not text:
        return False
    text_lower = text.lower().strip()
    try:
        from rapidfuzz import fuzz, process as fuzz_process
        # Check each wake word for a fuzzy match
        for wake_word in WAKE_WORDS:
            # Partial ratio: wake word must appear as a subsequence in the text
            score = fuzz.partial_ratio(wake_word, text_lower)
            if score >= WAKE_WORD_FUZZY_THRESHOLD:
                return True
        return False
    except ImportError:
        # Fallback to exact substring matching if rapidfuzz is missing
        return any(ww in text_lower for ww in WAKE_WORDS)


def extract_command_from_wake(text: str) -> str:
    """
    Remove the wake word from the beginning of the transcript.
    Returns whatever the user said after the wake word.

    Example:
        extract_command_from_wake("hey mantra open chrome") → "open chrome"
    """
    text_lower = text.lower().strip()
    try:
        from rapidfuzz import fuzz, process as fuzz_process
        for wake_word in sorted(WAKE_WORDS, key=len, reverse=True):
            # Find and remove the wake word from the start
            if text_lower.startswith(wake_word):
                return text_lower[len(wake_word):].strip()
            # Fuzzy: find the wake word as a substring near the beginning
            score = fuzz.partial_ratio(wake_word, text_lower[:len(wake_word) + 10])
            if score >= WAKE_WORD_FUZZY_THRESHOLD:
                # Remove approx the same number of chars as the wake word
                cutoff = min(len(wake_word) + 5, len(text_lower))
                return text_lower[cutoff:].strip()
    except ImportError:
        for wake_word in sorted(WAKE_WORDS, key=len, reverse=True):
            if wake_word in text_lower:
                return text_lower.replace(wake_word, "").strip()
    return text_lower


# ── Public API ────────────────────────────────────────────────────────────────
def get_voice_command(duration: int = RECORD_SECONDS) -> str | None:
    """
    Record audio and return the transcribed text (offline via Whisper).
    Returns a lowercase string or None if nothing was heard.

    This is a DROP-IN REPLACEMENT for the V1 get_voice_command().
    The return type is the same: a string or None.

    Example:
        command = get_voice_command()  # blocks for ~7s of listening + ~5s transcription
        if command:
            print(f"User said: {command}")
    """
    audio_data = _record_audio(duration)
    if audio_data is None:
        return None
    return _transcribe(audio_data)


def get_text_command() -> str:
    """
    Read a command from stdin (unchanged from V1).
    """
    try:
        command = input("You: ")
        return command.lower().strip()
    except (KeyboardInterrupt, EOFError):
        return ""


def get_user_command(mode: str = "text") -> str | None:
    """
    Unified entry point — returns a text command regardless of input mode.
    mode = 'text'  → reads from keyboard
    mode = 'voice' → records from microphone via Whisper
    """
    if mode == "voice":
        return get_voice_command()
    return get_text_command()


def preload_model() -> None:
    """
    Preload the Whisper model in a background thread at startup.
    This avoids the first-command delay of 3-5 seconds.
    Call this from main.py during the startup banner display.
    """
    def _load():
        try:
            _load_whisper()
            print("[Mantra] Voice engine ready.")
        except Exception as e:
            logger.warning("[input] Whisper preload failed: %s", e)

    t = threading.Thread(target=_load, daemon=True, name="Whisper-Preloader")
    t.start()
