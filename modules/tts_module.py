# modules/tts_module.py
# Mantra V2 — Text-to-Speech Module
# Provides offline spoken feedback using pyttsx3 (Windows SAPI5).
# Uses a background thread + queue so speech never blocks the main thread
# or the voice listener thread.

import threading
import queue
import logging

logger = logging.getLogger(__name__)

# ── Queue that holds text strings waiting to be spoken ───────────────────────
_speech_queue: queue.Queue = queue.Queue()

# ── Sentinel value to cleanly shut down the worker thread ────────────────────
_STOP_SIGNAL = object()

# ── Module-level config (can be changed via set_rate / set_voice) ────────────
_config = {
    "rate": 175,        # words per minute (default SAPI5 rate is ~200)
    "volume": 0.95,     # 0.0 – 1.0
    "voice_index": 0,   # 0 = first available voice (usually Microsoft Zira/David)
    "enabled": True,    # set to False to silence TTS globally without changing code
}

# ── Internal worker ───────────────────────────────────────────────────────────
def _tts_worker():
    """
    Runs in a daemon thread. Pulls text from _speech_queue and speaks it.
    Uses native SAPI5 to avoid pyttsx3 PyQt5 event loop conflicts.
    """
    import win32com.client
    import pythoncom
    
    pythoncom.CoInitialize()
    try:
        speaker = win32com.client.Dispatch("SAPI.SpVoice")
        speaker.Rate = (_config["rate"] - 150) // 10  # approximate scaling
        speaker.Volume = int(_config["volume"] * 100)
    except Exception as e:
        logger.error("[tts] Failed to initialise SAPI5: %s", e)
        # Drain the queue silently so callers don't block
        while True:
            item = _speech_queue.get()
            _speech_queue.task_done()
            if item is _STOP_SIGNAL:
                return
        return

    while True:
        try:
            text = _speech_queue.get(timeout=0.5)
        except queue.Empty:
            continue

        if text is _STOP_SIGNAL:
            _speech_queue.task_done()
            break

        if not _config["enabled"]:
            _speech_queue.task_done()
            continue

        try:
            speaker.Rate = (_config["rate"] - 150) // 10
            speaker.Volume = int(_config["volume"] * 100)
            speaker.Speak(str(text))
        except Exception as e:
            logger.warning("[tts] Speech error: %s", e)
        finally:
            _speech_queue.task_done()
            
    pythoncom.CoUninitialize()


# ── Start the worker thread immediately on import ────────────────────────────
_worker_thread = threading.Thread(target=_tts_worker, daemon=True, name="TTS-Worker")
_worker_thread.start()


# ── Public API ────────────────────────────────────────────────────────────────
def speak(text: str) -> None:
    """
    Queue text for speech — returns immediately (non-blocking).
    Any module can call this and the voice plays in the background.

    Example:
        speak("Opening Chrome for you.")
    """
    if not text or not isinstance(text, str):
        return
    # Strip markdown/emoji before speaking so the voice doesn't say
    # things like "tick mark" or "star star".
    clean = _strip_symbols(text)
    _speech_queue.put(clean)


def speak_blocking(text: str) -> None:
    """
    Queue text and WAIT until it has been fully spoken before returning.
    Use this only when the next action must not happen until speech is done
    (e.g., asking the user a yes/no question).
    """
    if not text or not isinstance(text, str):
        return
    clean = _strip_symbols(text)
    _speech_queue.put(clean)
    _speech_queue.join()   # blocks until the queue is empty (speech finished)


def silence() -> None:
    """
    Drain the queue — cancels any pending speech immediately.
    Does NOT stop a word currently being spoken (pyttsx3 limitation on Windows).
    """
    while not _speech_queue.empty():
        try:
            _speech_queue.get_nowait()
            _speech_queue.task_done()
        except queue.Empty:
            break


def set_rate(wpm: int) -> None:
    """Change speech rate. Typical range: 120 (slow) – 250 (fast)."""
    _config["rate"] = max(80, min(300, int(wpm)))


def set_volume(level: float) -> None:
    """Change speech volume. Range: 0.0 – 1.0."""
    _config["volume"] = max(0.0, min(1.0, float(level)))


def set_voice(index: int) -> None:
    """
    Change voice by index. On most Windows machines:
        0 = Microsoft David (male)
        1 = Microsoft Zira  (female)
    """
    _config["voice_index"] = max(0, int(index))


def enable() -> None:
    """Re-enable TTS after it was disabled."""
    _config["enabled"] = True


def disable() -> None:
    """
    Disable TTS globally without changing code elsewhere.
    speak() calls will still be accepted (queue them) but nothing is spoken.
    Useful for running automated tests silently.
    """
    _config["enabled"] = False


def list_voices() -> list:
    """
    Return a list of available voice names on this machine.
    Useful for the GUI settings tab.
    """
    try:
        import win32com.client
        import pythoncom
        pythoncom.CoInitialize()
        speaker = win32com.client.Dispatch("SAPI.SpVoice")
        voices = speaker.GetVoices()
        names = [voice.GetDescription() for voice in voices]
        pythoncom.CoUninitialize()
        return names
    except Exception as e:
        logger.warning("[tts] Could not list voices: %s", e)
        return []


def shutdown() -> None:
    """
    Gracefully stop the TTS worker thread.
    Call this when the application is closing.
    """
    _speech_queue.put(_STOP_SIGNAL)
    _worker_thread.join(timeout=3)


# ── Internal helpers ──────────────────────────────────────────────────────────
def _strip_symbols(text: str) -> str:
    """
    Remove common symbols that sound bad when spoken:
    emojis, markdown asterisks/underscores, URLs.
    """
    import re
    # Remove URLs
    text = re.sub(r'https?://\S+', '', text)
    # Remove markdown bold/italic
    text = re.sub(r'[*_`#]', '', text)
    # Remove emoji (broad unicode range)
    emoji_pattern = re.compile(
        "["
        u"\U0001F600-\U0001F64F"
        u"\U0001F300-\U0001F5FF"
        u"\U0001F680-\U0001F6FF"
        u"\U0001F1E0-\U0001F1FF"
        u"\U00002702-\U000027B0"
        u"\U000024C2-\U0001F251"
        "]+", flags=re.UNICODE
    )
    text = emoji_pattern.sub('', text)
    return text.strip()
