# ◈ MANTRA // AI DESKTOP AUTOMATION

**A Fully Offline, High-Performance Desktop Automation Framework with a Premium Holographic GUI.**

Mantra is an advanced, localized AI system designed to give you complete autonomous control over your Windows environment. By combining an offline Natural Language Processing (NLP) semantic engine, real-time adaptive learning, and hardware-accelerated GUI aesthetics, Mantra executes 35+ distinct automation tasks via Voice, Text, or Visual Dashboard—without ever sending a single byte of data to the cloud.

---

## 📑 Table of Contents
1. [Core AI Architecture](#1-core-ai-architecture)
2. [Exhaustive Feature List (35+ Commands)](#2-exhaustive-feature-list)
3. [User Interfaces (GUI, CLI, Voice)](#3-user-interfaces)
4. [Complete File Anatomy (What Every File Does)](#4-complete-file-anatomy)
5. [Installation & Setup](#5-installation--setup)
6. [Security & Privacy](#6-security--privacy)

---

## 🧠 1. Core AI Architecture

Unlike primitive automation scripts that rely on rigid regex or `if/else` keyword matching, Mantra acts as a localized artificial brain. 

### Hybrid Entity-Aware NLP Engine (`sentence-transformers`)
Mantra utilizes PyTorch to run the `all-MiniLM-L6-v2` transformer model entirely offline. Unlike basic cosine-similarity approaches that fail on unknown nouns (OOV), Mantra's V2 engine extracts entities *before* embedding, using normalized semantic placeholders. 
- **Result:** Capable of achieving 92%+ benchmark accuracy on complex, real-world phrasing. *"Launch Chrome"*, *"open the browser"*, or *"start Chromium"* all map perfectly to the same internal intent, regardless of the app name.

### Adaptive Learning (`CorrectionStore`)
If Mantra misunderstands a command and you correct it, it remembers. Backed by `RapidFuzz` and a local SQLite database (`mantra_v2.db`), the system permanently learns your unique phrasing over time without requiring any code updates.

### Short-Term Context Memory
Mantra tracks recent entities. If you say *"Open Notepad"*, and then follow up with *"Close it"*, Mantra recursively evaluates the conversation context and closes Notepad autonomously.

### Negation Detection
The NLP engine intercepts negated commands (e.g., *"don't open Chrome"*, *"cancel that"*) and routes them to a negation handler instead of blindly executing them.

---

## 🛠️ 2. Exhaustive Feature List

Mantra currently supports **35+ distinct automation intents**. Below is the complete catalog of exactly what the system can do.

### 📱 Application Management (`app_controller.py`)
| Capability | Example Phrases |
|:---|:---|
| **Open Application** | *"open Chrome"*, *"launch Spotify"*, *"start calculator"* |
| **Close Application** | *"close Notepad"*, *"kill the process"*, *"exit Spotify"* |
| **List Running Apps** | *"list apps"*, *"show running applications"* |
| **Get Active Window** | *"active window"*, *"what app is in focus right now?"* |
| **Switch Applications** | *"switch to discord"*, *"bring spotify to the front"* |

### 📁 File & Folder Operations (`file_manager.py`)
| Capability | Example Phrases |
|:---|:---|
| **Create File** | *"create file test.txt"*, *"make a new file called report"* |
| **Create Folder** | *"create folder projects"*, *"make a directory for taxes"* |
| **Delete File/Folder** | *"delete test.txt"*, *"trash the backup folder"* |
| **Rename File/Folder** | *"rename old.txt to new.txt"*, *"change the folder name"* |
| **Move File** | *"move report.pdf to downloads"*, *"transfer this file"* |
| **Search Files** | *"search for invoice"*, *"find a file named budget"* |
| **List Directory** | *"list files in this folder"*, *"what files are here?"* |

### ⚙️ System & OS Control (`system_control.py`)
| Capability | Example Phrases |
|:---|:---|
| **Shutdown** | *"shutdown system"*, *"power off the computer"* (5s delay) |
| **Restart** | *"restart the PC"*, *"reboot windows"* |
| **Lock/Sleep/Logout** | *"lock the screen"*, *"go to sleep"*, *"log me out"* |
| **Volume Control** | *"volume up"*, *"decrease volume"*, *"make it louder"* |
| **Mute Audio** | *"mute"*, *"silence the audio"*, *"turn off the sound"* |
| **System Info** | *"system info"*, *"what are my specs?"* (CPU/RAM check) |

### ⌨️ Text & Input Automation (`text_input_assistant.py`)
| Capability | Example Phrases |
|:---|:---|
| **Autonomous Typing** | *"type hello world"*, *"write out this sentence for me"* |
| **Clipboard Ops** | *"copy"*, *"paste"*, *"select all"* |
| **History Ops** | *"undo"*, *"redo"*, *"take that back"* |
| **Preset Snippets** | *"insert email signature"*, *"paste the greeting template"* |

### 🎙️ Voice & Audio Interface (`input_module.py` & `tts_module.py`)
| Capability | Details |
|:---|:---|
| **Wake Word Detection** | Listens silently in the background for *"Hey Mantra"* or *"Wake up Mantra"*. |
| **Dictation** | Transcribes speech to text in real-time via offline `Vosk` models. |
| **Text-To-Speech (TTS)**| Speaks back to you using `pyttsx3` to confirm actions or read errors aloud. |

---

## 🖥️ 3. User Interfaces

You can control Mantra through three distinct modes:

### Mode 1: The GUI Control Center (`gui_app.py`)
A hardware-accelerated PyQt5 dashboard designed to look like a premium, deep-navy "Cockpit".
- **Circuit Board Canvas:** Animated radar sweeps, pulsating connection nodes, and holographic scanning lines running in the background.
- **Live Telemetry (SlimGauges):** Horizontal progress bars tracking real-time CPU, RAM, and Disk I/O.
- **Command Log (LogDelegate):** Every command drops into a scrolling list, color-coded for success/error, featuring glowing pill tags that reveal the exact AI intent detected.
- **Terminal Bar:** Docked at the bottom for instant, silent typing execution.

### Mode 2: Voice Mode (Headless)
Run Mantra silently in the background. It will wait for the wake word, chime to confirm activation, listen to your command, and execute it seamlessly.

### Mode 3: CLI Terminal
For power users who prefer the command prompt, Mantra can be operated as a pure text-based CLI for instantaneous, low-overhead execution.

---

## 📂 4. Complete File Anatomy

Here is exactly what every single file in the Mantra ecosystem does:

### Root Level
- **`mantra.py`**: The primary GUI Launcher. This is the entry point for normal users. It renders the `HexLogo`, applies the dark theme, bypasses PyTorch DLL conflicts, and lets you select your mode.
- **`main.py`**: The headless CLI / Voice-only entry point. Run this if you don't want the visual GUI.
- **`requirements.txt`**: The exhaustive list of Python dependencies required to run the system.

### `gui/` (The Visual Dashboard)
- **`gui_app.py`**: The massive core of the visual interface. It houses the `MantraGUI` class, the background `CircuitBG` animation logic, the `SlimGauge` telemetry renderer, and the `LogDelegate` that draws the colored command history blocks.

### `core/` (The Brain)
- **`adaptive_learning.py`**: Houses the `CorrectionStore` class. This interacts with the database to fuzzy-match failed commands against user corrections, forcing the NLP engine to adapt.
- **`context_memory.py`**: Maintains a sliding window of recent subjects/nouns to resolve pronouns (like "it" or "that") in follow-up commands.

### `modules/` (The Execution Engines)
- **`nlp_module.py`**: Pre-processes raw user input. It strips stop-words, handles tokenization, and runs negation detection before passing data to the intent engine.
- **`entity_aware_intent.py`**: The Hybrid NLP pipeline. Pre-processes utterances to extract nouns, strips negations, and normalizes semantic vectors for 92% benchmark accuracy.
- **`intent_module.py`**: The heaviest AI logic file. It boots up the `sentence-transformers` model, compares your input to the embedded dataset, and spits out a hardcoded intent string (e.g., `"open_app"`).
- **`execution_module.py`**: The master dispatcher. It takes the intent string from `intent_module.py`, checks the context, and routes it to the specific automation script below.
- **`app_controller.py`**: Uses `psutil` and native OS hooks to scan for, launch, switch to, or forcefully terminate `.exe` processes.
- **`file_manager.py`**: Uses Python's `os` and `shutil` libraries to perform hyper-fast disk operations (creating, deleting, moving, or searching files).
- **`system_control.py`**: Taps into Windows-specific APIs (via `ctypes` or `os.system`) to alter volume, lock the screen, trigger sleep states, or reboot the motherboard.
- **`text_input_assistant.py`**: Leverages `pyautogui` to hijack the physical mouse and keyboard, allowing Mantra to type out paragraphs, press `Ctrl+C`, or execute macros anywhere on screen.
- **`input_module.py`**: Hooks into your physical microphone, loads the `Vosk` audio model into RAM, and listens indefinitely for wake words.
- **`tts_module.py`**: Translates system text back into auditory speech using the `win32com.client` (SAPI5) offline voice engine for robust GUI thread-safety.
- **`db_manager.py`**: Connects to the local `mantra_v2.db` SQLite database to log every single command's timestamp, intent, and success/failure status.

### `data/` & `assets/`
- **`data/mantra_v2.db`**: The persistent local database storing your command history and adaptive learning overrides.
- **`assets/*.wav`**: The acoustic chimes played when the system activates, succeeds, or encounters an error.

---

## ⚙️ 5. Installation & Setup

### Requirements
- **OS:** Windows 10 or Windows 11 (Highly Recommended)
- **Python:** Python 3.8+ (64-bit)
- **Hardware:** 4GB+ RAM, working Microphone.

### Installation Steps
```bash
# 1. Clone the repository and enter the directory
cd AI_Desktop_Automation

# 2. Create and activate a virtual environment
python -m venv venv
venv\Scripts\activate

# 3. Install all heavy ML and automation dependencies
pip install -r requirements.txt

# 4. Start the Mantra System!
python mantra.py
```

---

## 🔒 6. Security & Privacy

**Mantra is built for absolute privacy.**
- **Zero Cloud:** No API keys to OpenAI, Google, or AWS are required. Your voice audio and text commands never leave your motherboard. 
- **Protected OS Hooks:** Mantra is strictly restricted from editing the Windows Registry (`regedit`) or deleting core System32 files to prevent accidental OS corruption.
- **No Unprompted Admin Escalation:** Mantra will execute tasks in user-space and will not prompt for UAC Admin rights unless specifically configured to do so. 

---

**Mantra — The ultimate offline AI companion for the modern desktop.**
