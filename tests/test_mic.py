import sys
import os

# Ensure project root is on sys.path when running from tests/
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    import sounddevice as sd
    import whisper
    import numpy as np
    
    print("Dependencies loaded successfully.")
    
    # Try recording 3 seconds of audio
    print("\n--- Testing Microphone (Recording 3 seconds) ---")
    SAMPLE_RATE = 16000
    DURATION = 3
    
    audio_data = sd.rec(int(DURATION * SAMPLE_RATE), samplerate=SAMPLE_RATE, channels=1, dtype="float32")
    sd.wait()
    print("Recording finished. Microphone access is WORKING!")
    
    # Process audio for Whisper (flatten to 1D array)
    audio_data_1d = audio_data.flatten()
    
    # Try transcribing it
    print("\n--- Testing Whisper Model (small) ---")
    print("Loading model (should be instant now since it downloaded)...")
    model = whisper.load_model("small")
    print("Transcribing directly from memory (bypassing ffmpeg)...")
    
    # Pass the numpy array directly instead of a file path!
    result = model.transcribe(audio_data_1d, fp16=False)
    
    print(f"\n[TRANSCRIPT] -> {result['text']}")
    print("\nAll systems GO! Voice module is fully operational.")

except Exception as e:
    import traceback
    traceback.print_exc()
