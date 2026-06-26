# 🎯 MANTRA - GUI USER GUIDE

## Quick Start for Non-Technical Users

### Installation & Setup

1. **Install Dependencies:**
```bash
venv\Scripts\activate
pip install -r requirements.txt
```

2. **Start Mantra:**
```bash
python mantra.py
```

Or headless CLI/Voice mode:
```bash
python main.py
```

---

## 🖥️ GUI Dashboard Overview

### Layout
The GUI is organized in **7 main tabs** for easy navigation:

```
┌─────────────────────────────────────────────────────┐
│ 🏠 Dashboard | 🖥️ Apps | 📁 Files | ⚙️ System | ⌨️ Text | 📋 History | ⚙️ Settings │
└─────────────────────────────────────────────────────┘
```

---

## 📑 Tab Guide

### 1. 🏠 Dashboard (Home)
**What it shows:**
- 📊 Real-time system status (CPU, RAM, running apps)
- ⚡ Quick access buttons for common tasks
- 📜 Recently executed commands

**Quick Actions Available:**
- Open Chrome
- Open Notepad
- List Running Apps
- Lock PC
- Sleep Mode
- Mute Audio

**Perfect for:** Getting quick information and performing frequent tasks

---

### 2. 🖥️ Applications Tab
**Manage all desktop applications**

**Features:**
- ✅ **Open App** - Type app name and open it
  - Examples: `chrome`, `notepad`, `spotify`, `discord`
- 🔴 **Close App** - Close any running application
  - Type exact app name and close it
- 📋 **List Apps** - See all running applications
  - Click "Refresh" button to update list
  - Shows complete list of running processes

**Instructions:**
1. Type app name in the text box
2. Click the button (Open/Close)
3. See result in status area

---

### 3. 📁 Files & Folders Tab
**Complete file management system**

**Features:**

| Feature | How to Use |
|---------|-----------|
| 📄 Create File | Enter full path (e.g., `C:\Users\Document\test.txt`) → Click Create |
| 📂 Create Folder | Enter folder path (e.g., `C:\Users\MyFolder`) → Click Create |
| 🗑️ Delete | Enter file/folder path → Click Delete |
| 🔍 Search | Enter search term (e.g., `document`) → See results |

**Examples:**
```
Create File:     C:\Users\MyFile.txt
Create Folder:   C:\Users\MyDocuments
Delete:          C:\Users\OldFile.txt
Search:          invoice
```

---

### 4. ⚙️ System Control Tab
**Control your computer system**

**Power Controls:**
- 🔴 **Shutdown** - Turn off PC (5 second countdown)
- 🔄 **Restart** - Restart PC (5 second countdown)
- 🔒 **Lock PC** - Lock Windows session (immediate)
- 💤 **Sleep** - Enter sleep mode (immediate)
- 👤 **Logout** - Logout current user (immediate)

**Volume Controls:**
- 🔊 Increase Volume
- 🔉 Decrease Volume
- 🔇 Mute Audio

**System Info:**
- Shows detailed system information

⚠️ **WARNING:** Shutdown and Restart require confirmation before executing!

---

### 5. ⌨️ Text Input Tab
**Control keyboard and clipboard**

**Features:**

| Feature | Purpose |
|---------|---------|
| ⌨️ Type Text | Auto-type text into active window |
| 📋 Copy | Copy selected text |
| 📌 Paste | Paste from clipboard |
| ✓ Select All | Select all text in active window |
| ↶ Undo | Undo last action |
| ↷ Redo | Redo last action |

**How to Use Type Text:**
1. Click in the active application where you want text
2. Enter text in the GUI input field
3. Click "Type" button
4. Text appears automatically in active window

---

### 6. 📋 History Tab
**View all executed commands**

**Features:**
- Shows timestamp, command, and result
- Lists last 20 commands
- Sortable list showing time and action
- Clear all history option

**Example History:**
```
2026-05-07 14:23:45 - open_or_switch_app: Opened new chrome window
2026-05-07 14:22:10 - create_file: File created: C:\test.txt
2026-05-07 14:21:32 - lock_system: System locked successfully
```

---

### 7. ⚙️ Settings Tab
**Configuration and information**

**Current Features:**
- ✅ View enabled features
- ℹ️ Version information
- 📋 About Mantra
- 🎯 System status

**Future Features (Coming Soon):**
- [ ] Custom keyboard shortcuts
- [ ] Theme selection
- [ ] Notification settings
- [ ] Command scheduling

---

## 💡 Usage Tips for Non-Technical Users

### Getting Started
1. **Open Mantra GUI** - Run `python launcher.py`
2. **Choose mode** - Click "GUI Control Center"
3. **Explore tabs** - Each tab has specific features
4. **Read labels** - Every button explains what it does

### Common Tasks

**Opening an Application:**
```
1. Go to "Applications" tab
2. Type: chrome (or notepad, spotify, etc.)
3. Click "Open"
```

**Creating a File:**
```
1. Go to "Files & Folders" tab
2. Enter path: C:\Users\MyFile.txt
3. Click "Create"
```

**Shutting Down PC:**
```
1. Go to "System Control" tab
2. Click "Shutdown"
3. Confirm in popup
4. PC will shutdown in 5 seconds
```

**Checking System Resources:**
```
1. Go to "Dashboard" tab
2. See CPU, RAM, and App count at top
3. Auto-refreshes every 5 seconds
```

---

## ⚠️ Important Safety Notes

### Critical Operations Require Confirmation
- ✅ Shutdown - Ask for confirmation
- ✅ Restart - Ask for confirmation
- ✅ Logout - Requires action
- ✅ Lock - Locks immediately

### Safe to Use Freely
- ✅ Opening/Closing apps - Won't damage system
- ✅ File creation/deletion - You choose what to delete
- ✅ Text input - Only types in active window
- ✅ Volume control - No system damage

### Best Practices
1. **Save work before shutdown/restart**
2. **Double-check file paths before deleting**
3. **Close important apps before locking/sleeping**
4. **Use History tab to see what commands were executed**

---

## 🎤 Integration with Voice Commands

**Can I use GUI and Voice Together?**
- Yes! Switch between them anytime
- Voice and GUI work independently
- One doesn't affect the other

**Starting Voice Commands:**
```bash
python main.py
```
Then still use GUI in another window!

---

## 🆘 Troubleshooting

### Issue: App won't open
**Solution:** Make sure app is installed on system
- Check app name spelling
- Use common names (chrome, notepad, spotify)

### Issue: File path error
**Solution:** Use correct Windows path format
- Correct: `C:\Users\Documents\file.txt`
- Wrong: `C:/Users/Documents/file.txt`

### Issue: System commands not working
**Solution:** Run as Administrator if needed
- Right-click launcher.py → Run as administrator

### Issue: GUI is slow
**Solution:** Close other heavy applications
- GUI works best with 2-3 GB RAM free
- Refresh system status manually if slow

---

## 📊 Feature Checklist

```
✅ Applications
   ✓ Open app
   ✓ Close app
   ✓ List running apps

✅ Files & Folders
   ✓ Create file
   ✓ Create folder
   ✓ Delete file
   ✓ Delete folder
   ✓ Search files

✅ System Control
   ✓ Shutdown
   ✓ Restart
   ✓ Lock PC
   ✓ Sleep
   ✓ Logout
   ✓ Volume control
   ✓ System info

✅ Text Input
   ✓ Type text
   ✓ Copy/Paste
   ✓ Select all
   ✓ Undo/Redo

✅ History & Logs
   ✓ Track all commands
   ✓ View recent actions
   ✓ Clear history
```

---

## 🎯 Next Steps

1. **Try Dashboard** - Get a quick overview
2. **Test Applications** - Open/close apps
3. **Explore Commands** - Try different features
4. **Check History** - See what was executed
5. **Combine with Voice** - Use both modes together

---

## 📞 Support Features

**Built-in Help:**
- Every button has description
- Hover over elements for info
- Check History tab for logs
- Status messages show operation results

**Error Messages:**
- GUI shows what went wrong
- Check typos in paths
- Use correct app names
- Ensure app is installed

---

**Version:** 1.0  
**Last Updated:** May 7, 2026  
**Status:** Production Ready ✅
