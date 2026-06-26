# main.py — Mantra V2 Entry Point (CLI + Voice)
# Wires together the full V2 pipeline:
#   input_module (Whisper) → nlp_module (spaCy) → intent_module (sentence-transformers)
#   → execution_module → tts_module (pyttsx3) + db_manager (SQLite)
#
# V1 behaviours preserved:
#   - Wake word detection still works the same way
#   - Text (CLI) commands still work the same way
#   - Ctrl+C to exit

import threading
import time

# ── V2 modules ────────────────────────────────────────────────────────────────
from modules.db_manager    import log_command               # SQLite persistence
from modules.tts_module    import speak, disable as tts_disable  # offline TTS
from modules.nlp_module    import process_command           # spaCy NLP
from modules.intent_module import detect_intent             # sentence-transformers
from modules.execution_module import execute_task           # command executor
from modules.response_module  import give_feedback          # console feedback
from modules.input_module  import (
    get_voice_command,
    get_text_command,
    is_wake_word,
    extract_command_from_wake,
    preload_model,
)

# ── Pause flag — prevents voice listener interrupting while user types ────────
_pause_voice = threading.Event()
_pause_voice.set()   # start in listening mode


# ── Core command handler ───────────────────────────────────────────────────────
def handle_command(raw_command: str) -> None:
    """
    Full V2 pipeline for one command:
        raw text → spaCy parse → intent → execute → TTS + log
    """
    if not raw_command or not raw_command.strip():
        return

    start_ms = int(time.time() * 1000)

    print(f"\n  Processing: {raw_command}")

    # 1. spaCy NLP — returns rich dict (negation, entities, keywords)
    parsed = process_command(raw_command)

    # 2. sentence-transformers intent detection
    intent = detect_intent(parsed)

    # 3. Handle negation gracefully
    if intent.startswith("negated_"):
        real_intent = intent.replace("negated_", "")
        result = f"Understood — NOT doing: {real_intent.replace('_', ' ')}"
        give_feedback(result)
        speak(result)
        _log("cancelled", None, None, intent, 0, int(time.time() * 1000) - start_ms)

        return

    # 4. Execute
    keywords = parsed.get("keywords", [])
    try:
        result = execute_task(intent, keywords, raw_command)
    except Exception as e:
        result = f"Error executing command: {e}"

    # 5. Feedback — console print + spoken
    give_feedback(result)
    
    # Speak a simplified response instead of reading long results
    if result and result.startswith(("Error", "Failed", "❌")):
        speak("Sorry, there was an error.")
    else:
        speak("Done.")

    # 6. Log to SQLite — new V2 schema
    entities = parsed.get("entities", {})
    entity_type  = "app"  if entities.get("app")  else \
                   "file" if entities.get("file") else \
                   "text" if entities.get("path") else None
    entity_value = entities.get("app") or entities.get("file") or entities.get("path")
    success = 0 if result and result.startswith(("Error", "Failed", "\u274c")) else 1
    action  = intent.replace("_", " ") if intent else "unknown"
    elapsed_ms = int(time.time() * 1000) - start_ms
    _log(action, entity_type, entity_value, intent, success, elapsed_ms)

    print()


def _log(action: str, entity_type: str, entity_value: str,
         intent: str, success: int, elapsed_ms: int = None) -> None:
    """Write one command execution record to SQLite. Never raises."""
    try:
        log_command(
            action=action,
            entity_type=entity_type,
            entity_value=entity_value,
            intent=intent,
            success=success,
            latency_ms=elapsed_ms,
        )
    except Exception:
        pass   # never crash the main loop due to a logging failure


# ── Voice listener thread ─────────────────────────────────────────────────────
def voice_listener():
    """
    Runs in a background daemon thread.
    Continuously records audio, checks for wake word, then processes command.
    Uses Whisper (offline) — no internet needed.
    """
    print("\n  Voice listener ACTIVE - Say 'Hey Mantra' anytime...\n")

    while True:
        try:
            if not _pause_voice.is_set():
                time.sleep(0.2)
                continue

            transcript = get_voice_command()

            if not transcript:
                continue

            if is_wake_word(transcript):
                print("\n" + "=" * 60)
                print("  MANTRA ACTIVATED!")
                print("=" * 60)
                speak("Mantra is activated, give command.")

                # Extract command that followed the wake word
                command = extract_command_from_wake(transcript)

                if not command:
                    # Wake word only — listen for follow-up command
                    print("\n  What would you like me to do?")
                    command = get_voice_command()

                if command:
                    print(f"\n  You said: {command}")
                    _pause_voice.clear()      # pause listener while executing
                    handle_command(command)
                    _pause_voice.set()        # resume after execution

                print("=" * 60)
                print("  Listening for next command...\n")

        except KeyboardInterrupt:
            print("\n  Voice listener stopped.")
            break
        except Exception:
            time.sleep(0.5)
            continue


# ── Main entry point ───────────────────────────────────────────────────────────
def main():
    print("\n" + "=" * 70)
    print("  MANTRA AI Desktop Automation - V2")
    print("=" * 70)
    print("\n  FEATURES: 35+ Commands | Offline Voice | Semantic NLP | Memory")
    print("\n  VOICE MODE:  Say 'Hey Mantra' then your command (fully offline)")
    print("  TEXT MODE:   Type commands directly below")
    print("\n  COMMANDS:    open [app] | close [app] | create file [name]")
    print("               delete file [name] | list apps | system info")
    print("               shutdown | restart | lock | volume up/down | mute")
    print("               type [text] | copy | paste | undo | redo")
    print("\n  Press Ctrl+C to exit")
    print("=" * 70 + "\n")

    # Preload Whisper in background so first voice command is instant
    preload_model()

    # Start voice listener in background
    voice_thread = threading.Thread(target=voice_listener, daemon=True, name="Voice-Listener")
    voice_thread.start()

    # Main text input loop
    while True:
        try:
            _pause_voice.clear()   # pause voice while waiting for text input
            text = input("  You: ").strip()
            _pause_voice.set()     # resume voice after text received

            if not text:
                continue

            if text.lower() in ("exit", "quit", "bye"):
                speak("Goodbye!")
                print("\n  Goodbye!\n")
                break

            # If the user typed a wake word phrase, extract the real command
            if is_wake_word(text):
                command = extract_command_from_wake(text)
                if command:
                    handle_command(command)
                else:
                    print("  What would you like me to do?")
                    text = input("  Command: ").strip()
                    if text:
                        handle_command(text)
            else:
                handle_command(text)

        except KeyboardInterrupt:
            print("\n" + "=" * 60)
            speak("System shutting down. Goodbye!")
            give_feedback("Shutting down. Goodbye!")
            print("=" * 60)
            break
        except Exception as e:
            print(f"  Error: {e}")
            continue


if __name__ == "__main__":
    main()
