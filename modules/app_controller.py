import subprocess
import psutil
import winreg
import os
from rapidfuzz import process, fuzz

BLOCKLIST = ["powershell", "regedit", "taskmgr", "explorer"]

APP_PATHS = {}

def build_app_index():
    """Scans the Windows Registry to find installed applications and their executable paths."""
    global APP_PATHS
    APP_PATHS.clear()
    
    APP_PATHS["notepad"] = "notepad.exe"
    APP_PATHS["calculator"] = "calc.exe"
    APP_PATHS["cmd"] = "cmd.exe"
    APP_PATHS["chrome"] = "chrome.exe"
    APP_PATHS["explorer"] = "explorer.exe"
    APP_PATHS["spotify"] = "spotify:"
    APP_PATHS["whatsapp"] = "whatsapp:"
    APP_PATHS["instagram"] = "instagram:"
    APP_PATHS["settings"] = "ms-settings:"

    registry_keys = [
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths"),
        (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths")
    ]
    
    for hkey, subkey in registry_keys:
        try:
            with winreg.OpenKey(hkey, subkey) as key:
                for i in range(winreg.QueryInfoKey(key)[0]):
                    try:
                        app_key_name = winreg.EnumKey(key, i)
                        with winreg.OpenKey(key, app_key_name) as app_key:
                            app_path = winreg.QueryValue(app_key, None)
                            if app_path and app_path.lower().endswith(".exe"):
                                name = app_key_name.lower().replace(".exe", "")
                                APP_PATHS[name] = app_path
                    except Exception:
                        continue
        except Exception:
            pass

def open_or_switch_app(app_name):
    app_name_lower = app_name.lower()
    
    if app_name_lower in BLOCKLIST:
        return f"\u274c {app_name} cannot be opened for safety."
        
    # Fuzzy match to find the best executable path from Registry
    if not APP_PATHS:
        build_app_index()
        
    best_match = process.extractOne(app_name_lower, list(APP_PATHS.keys()), scorer=fuzz.WRatio)
    
    if best_match and best_match[1] > 75:  # Threshold for a good match
        matched_name = best_match[0]
        exe_path = APP_PATHS[matched_name]
        try:
            if exe_path.endswith(":"):
                os.startfile(exe_path)  # Handle URIs
            else:
                subprocess.Popen([exe_path], shell=False)
            return f"Opened {matched_name}"
        except Exception as e:
            return f"\u274c Failed to open {matched_name}."
    else:
        # Fallback to os.startfile execution (clean error handling, no windows dialogs)
        try:
            os.startfile(app_name)
            return f"Opened {app_name}"
        except Exception:
            return f"\u274c Could not find application: {app_name}"

def close_app(app_name):
    app_name_lower = app_name.lower()
    closed = False
    for proc in psutil.process_iter(['name']):
        try:
            if app_name_lower in str(proc.info['name']).lower():
                proc.terminate()
                closed = True
        except Exception:
            pass
    if closed:
        return f"{app_name} closed successfully."
    return f"{app_name} not running."

def list_running_apps():
    """List all currently running applications"""
    try:
        apps = []
        for proc in psutil.process_iter(['name']):
            try:
                name = proc.info['name']
                if name and name.endswith(".exe"):
                    apps.append(name)
            except Exception:
                pass
        
        unique_apps = sorted(set(apps))
        if unique_apps:
            output = f"Total Running Processes: {len(unique_apps)}\n"
            output += " | ".join(unique_apps[:30]) # Show first 30 to not overflow UI
            if len(unique_apps) > 30:
                output += " ... [truncated]"
            return output
        return "No applications found."
    except Exception as e:
        return f"Failed to list applications: {e}"

def get_active_window():
    """Return the title of the currently focused window using win32gui."""
    try:
        import win32gui
        hwnd = win32gui.GetForegroundWindow()
        title = win32gui.GetWindowText(hwnd)
        if title:
            return f"Active window: {title}"
        return "No active window detected (minimised or no focus)."
    except ImportError:
        return "win32gui not available. Install pywin32."
    except Exception as e:
        return f"Could not get active window: {e}"
