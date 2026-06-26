# modules/system_control.py
import subprocess
import os
import ctypes
import pyautogui

# Disable fail-safe so volume/media keys always work
pyautogui.FAILSAFE = False

def shutdown_system():
    """Shutdown the system"""
    try:
        subprocess.run("shutdown /s /t 5", shell=True)
        return "System will shutdown in 5 seconds."
    except Exception as e:
        return f"Failed to shutdown: {e}"

def restart_system():
    """Restart the system"""
    try:
        subprocess.run("shutdown /r /t 5", shell=True)
        return "System will restart in 5 seconds."
    except Exception as e:
        return f"Failed to restart: {e}"

def lock_system():
    """Lock the system"""
    try:
        # Using Windows API to lock the system
        ctypes.windll.user32.LockWorkStation()
        return "System locked successfully."
    except Exception as e:
        return f"Failed to lock system: {e}"

def logout_user():
    """Log out the current user"""
    try:
        os.system("shutdown /l")
        return "Logging out user..."
    except Exception as e:
        return f"Failed to logout: {e}"

def sleep_system():
    """Put system into sleep mode"""
    try:
        os.system("rundll32.exe powrprof.dll,SetSuspendState 0,1,0")
        return "System entering sleep mode..."
    except Exception as e:
        return f"Failed to enter sleep mode: {e}"

def increase_volume():
    """Increase system volume by a noticeable chunk (~10%)"""
    try:
        import pyautogui
        # Press 5 times to make a 10% jump (Windows default step is 2%)
        for _ in range(5):
            pyautogui.press('volumeup')
        return "Volume increased by 10%."
    except Exception as e:
        return f"Failed to increase volume: {e}"

def decrease_volume():
    """Decrease system volume by a noticeable chunk (~10%)"""
    try:
        import pyautogui
        for _ in range(5):
            pyautogui.press('volumedown')
        return "Volume decreased by 10%."
    except Exception as e:
        return f"Failed to decrease volume: {e}"

def mute_volume():
    """Mute system volume"""
    try:
        import pyautogui
        pyautogui.press('volumemute')
        return "Volume muted."
    except Exception as e:
        return f"Failed to mute volume: {e}"

def get_system_info():
    """Get basic system information"""
    try:
        import platform
        info = f"OS: {platform.system()} {platform.release()}\n"
        info += f"Processor: {platform.processor()}\n"
        info += f"Python: {platform.python_version()}"
        return info
    except Exception as e:
        return f"Failed to get system info: {e}"
