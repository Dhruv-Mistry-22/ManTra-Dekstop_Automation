# ManTra — AI Desktop Automation

ManTra is a fully offline, voice-controlled desktop automation system for Windows. You speak or type a command, and ManTra executes it — opening apps, managing files, controlling system settings, typing text, recording macros, and more.

It runs entirely on your machine. No cloud. No API keys. No internet required.

**What it can do:**
- Open, close, and switch between applications
- Create, delete, rename, move, and search files and folders
- Control system volume, lock screen, sleep, restart, and shutdown
- Type any sentence into any active window by voice
- Copy, paste, undo, and redo keyboard actions
- Record and replay multi-step keyboard/mouse macros
- Read text on screen using OCR
- Remember the last thing it did — say *"undo last"* to reverse it

---

## Installation

**Requirements:** Windows 10/11 · Python 3.12 (64-bit) · 4 GB RAM · Microphone

```bash
# 1. Clone the repo
git clone https://github.com/Dhruv-Mistry-22/ManTra-Dekstop_Automation.git
cd ManTra-Dekstop_Automation

# 2. Install PyTorch (CPU build) first
pip install torch --index-url https://download.pytorch.org/whl/cpu

# 3. Install all other dependencies
pip install -r requirements.txt

# 4. Download the spaCy language model
python -m spacy download en_core_web_md
```

> **Note:** For the Screen Vision feature (`read screen`), install [Tesseract OCR](https://github.com/tesseract-ocr/tesseract) separately and add it to your system PATH.

---

## How to Run

**GUI Mode** (recommended — visual dashboard with voice and text input):
```bash
python mantra.py
```

**Headless / CLI Mode** (no GUI, voice only):
```bash
python main.py
```

### Example Commands
| Say this | What happens |
|---|---|
| `open chrome` | Launches or switches to Chrome |
| `create file report` | Creates `report.txt` on the Desktop and opens Explorer |
| `type how are you` | Types "how are you" into the active window |
| `undo last` | Deletes the last file or folder ManTra created |
| `volume up` | Raises system volume |
| `read screen` | Reads all visible text on screen aloud |
| `record macro` | Starts recording your keyboard/mouse inputs |
| `shutdown` | Shuts down Windows after a 5-second delay |

---

## Benchmark Results

The full benchmark suite is in [`evaluation/benchmark.py`](evaluation/benchmark.py).  
Test utterances are in [`evaluation/test_utterances.csv`](evaluation/test_utterances.csv).

Run it yourself:
```bash
python evaluation/benchmark.py
```

The ManTra V2 hybrid NLP pipeline (entity-aware sentence embeddings + keyword fallback) achieves **92%+ intent accuracy** across 35+ command categories on real-world phrasing variations.

| Category | ManTra V2 | ISHA (baseline) |
|---|---|---|
| App Management | ✅ | ✅ |
| File Management | ✅ | ✅ |
| System Control | ✅ | ❌ |
| Text Input | ✅ | ❌ |
| Negation Handling | ✅ | ❌ |
| Context / Memory | ✅ | ❌ |
| Ambiguous Detection | ✅ | ❌ |
| Multi-Step Macros | ✅ | ❌ |
