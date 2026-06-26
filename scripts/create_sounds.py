import numpy as np
import soundfile as sf
import os, pathlib

# Always write assets relative to the project root (works from any CWD)
_PROJECT_ROOT = pathlib.Path(__file__).parent.parent
os.makedirs(_PROJECT_ROOT / "assets", exist_ok=True)

SAMPLE_RATE = 44100

def generate_tone(freq, duration_ms, wave_type='sine'):
    t = np.linspace(0, duration_ms / 1000, int(SAMPLE_RATE * duration_ms / 1000), False)
    if wave_type == 'sine':
        wave = np.sin(freq * t * 2 * np.pi)
    elif wave_type == 'square':
        wave = np.sign(np.sin(freq * t * 2 * np.pi))
    else:
        wave = np.sin(freq * t * 2 * np.pi)
        
    # Apply envelope to avoid clicking (fade in/out)
    fade = int(SAMPLE_RATE * 0.02) # 20ms fade
    if fade > 0 and fade < len(wave)/2:
        envelope = np.ones_like(wave)
        envelope[:fade] = np.linspace(0, 1, fade)
        envelope[-fade:] = np.linspace(1, 0, fade)
        wave = wave * envelope
        
    return wave

# 1. Activate Sound (Short, high-pitched ascending double beep)
part1 = generate_tone(1200, 80)
part2 = generate_tone(1600, 100)
silence = np.zeros(int(SAMPLE_RATE * 0.02))
activate_wave = np.concatenate([part1, silence, part2]) * 0.3 # Volume 30%
sf.write(str(_PROJECT_ROOT / "assets" / "activate.wav"), activate_wave, SAMPLE_RATE)

# 2. Success Sound (Smooth, melodic ascending chord or sweep)
part1 = generate_tone(800, 100)
part2 = generate_tone(1000, 100)
part3 = generate_tone(1200, 150)
success_wave = np.concatenate([part1, part2, part3]) * 0.3
sf.write(str(_PROJECT_ROOT / "assets" / "success.wav"), success_wave, SAMPLE_RATE)

# 3. Error Sound (Low, dissonant buzz or double descending tone)
part1 = generate_tone(300, 150, 'square')
part2 = generate_tone(250, 250, 'square')
error_wave = np.concatenate([part1, silence, part2]) * 0.15 # Lower volume for square wave
sf.write(str(_PROJECT_ROOT / "assets" / "error.wav"), error_wave, SAMPLE_RATE)

print("Created 3 sound effect files in assets/ folder.")
