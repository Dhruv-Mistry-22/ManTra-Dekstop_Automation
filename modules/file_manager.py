# modules/file_manager.py
import os
import shutil
from pathlib import Path
import time
import threading

FILE_INDEX = {}
_indexing_lock = threading.Lock()
_index_ready = False

def build_file_index():
    """Asynchronously scan common user directories and index file paths."""
    global FILE_INDEX, _index_ready
    
    def _scan():
        with _indexing_lock:
            user_dir = os.path.expanduser("~")
            # Only scan these common folders to avoid 10-minute deep scans of AppData
            target_folders = ["Desktop", "Documents", "Downloads", "Music", "Pictures", "Videos"]
            
            temp_index = {}
            for folder in target_folders:
                folder_path = os.path.join(user_dir, folder)
                if not os.path.exists(folder_path):
                    continue
                    
                for root, _, files in os.walk(folder_path):
                    for file in files:
                        try:
                            # Use lowercase filename without extension as the key for fuzzy matching
                            name_no_ext = os.path.splitext(file)[0].lower()
                            temp_index[name_no_ext] = os.path.join(root, file)
                        except Exception:
                            continue
                            
            global FILE_INDEX, _index_ready
            FILE_INDEX = temp_index
            _index_ready = True
            print(f"[file_manager] Indexed {len(FILE_INDEX)} files.")

    t = threading.Thread(target=_scan, daemon=True, name="FileIndexer")
    t.start()

# Start indexing immediately when module loads
build_file_index()


def search_files(search_term, _=None):
    """Smart fuzzy search using RapidFuzz against the indexed files."""
    if not _index_ready:
        return "Still indexing files. Please wait a few seconds and try again."
        
    try:
        from rapidfuzz import process, fuzz
        
        search_lower = search_term.lower()
        
        # If perfect substring match exists, prioritize those
        exact_matches = [path for name, path in FILE_INDEX.items() if search_lower in name]
        if exact_matches:
            # Return up to 5 matches
            return f"Found {len(exact_matches)} file(s):\n" + "\n".join(exact_matches[:5])
            
        # Fallback to fuzzy matching
        best_matches = process.extract(search_lower, list(FILE_INDEX.keys()), scorer=fuzz.WRatio, limit=5)
        
        results = []
        for match in best_matches:
            if match[1] > 60: # Threshold
                results.append(FILE_INDEX[match[0]])
                
        if results:
            return f"Found matching files:\n" + "\n".join(results)
            
        return f"Could not find any files matching '{search_term}'."
    except ImportError:
        return "rapidfuzz not installed. Run: pip install rapidfuzz"
    except Exception as e:
        return f"Search failed: {e}"


def open_file(file_path_or_name):
    """Open a file smartly. Try direct path first, then fuzzy search."""
    try:
        # If it's a valid absolute path, open it
        if os.path.exists(file_path_or_name):
            os.startfile(file_path_or_name)
            return f"Opened file: {file_path_or_name}"
            
        # If not an absolute path, fuzzy search it
        if not _index_ready:
            return "File system is still indexing. Try again in 5 seconds."
            
        from rapidfuzz import process, fuzz
        best_match = process.extractOne(file_path_or_name.lower(), list(FILE_INDEX.keys()), scorer=fuzz.WRatio)
        
        if best_match and best_match[1] > 70:
            actual_path = FILE_INDEX[best_match[0]]
            os.startfile(actual_path)
            return f"Opened {os.path.basename(actual_path)}"
            
        return f"Could not find a file matching '{file_path_or_name}' to open."
    except Exception as e:
        return f"Failed to open file: {e}"


def open_folder(folder_path):
    """Open a folder in file explorer using native Windows API"""
    try:
        if os.path.exists(folder_path):
            os.startfile(folder_path)
            return f"Opened folder: {folder_path}"
        
        # Fallback to general explorer launch
        os.system("explorer")
        return "Opened File Explorer"
    except Exception as e:
        return f"Failed to open folder: {e}"


def create_file(file_path):
    """Create a new empty file. If no absolute path provided, create on Desktop."""
    try:
        if not os.path.isabs(file_path):
            file_path = os.path.join(os.path.expanduser("~"), "Desktop", file_path)
            
        Path(file_path).touch()
        # Refresh index asynchronously
        build_file_index()
        return f"File created on Desktop: {os.path.basename(file_path)}"
    except Exception as e:
        return f"Failed to create file: {e}"


def create_folder(folder_path):
    """Create a new folder. Defaults to Desktop if not absolute."""
    try:
        if not os.path.isabs(folder_path):
            folder_path = os.path.join(os.path.expanduser("~"), "Desktop", folder_path)
            
        os.makedirs(folder_path, exist_ok=True)
        return f"Folder created on Desktop: {os.path.basename(folder_path)}"
    except Exception as e:
        return f"Failed to create folder: {e}"


def delete_file(file_path):
    """Delete a file with fuzzy search fallback."""
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
            build_file_index()
            return f"File deleted: {file_path}"
            
        # Try fuzzy match
        if _index_ready:
            from rapidfuzz import process, fuzz
            best = process.extractOne(file_path.lower(), list(FILE_INDEX.keys()), scorer=fuzz.WRatio)
            if best and best[1] > 80:
                actual_path = FILE_INDEX[best[0]]
                os.remove(actual_path)
                build_file_index()
                return f"Deleted {os.path.basename(actual_path)}"
                
        return f"File not found: {file_path}"
    except Exception as e:
        return f"Failed to delete file: {e}"


def delete_folder(folder_path):
    """Delete a folder and its contents"""
    try:
        if os.path.exists(folder_path):
            shutil.rmtree(folder_path)
            return f"Folder deleted: {folder_path}"
        return f"Folder not found: {folder_path}"
    except Exception as e:
        return f"Failed to delete folder: {e}"


def rename_file(old_path, new_path):
    try:
        os.rename(old_path, new_path)
        build_file_index()
        return f"File renamed from {old_path} to {new_path}"
    except Exception as e:
        return f"Failed to rename file: {e}"


def rename_folder(old_path, new_path):
    try:
        os.rename(old_path, new_path)
        return f"Folder renamed from {old_path} to {new_path}"
    except Exception as e:
        return f"Failed to rename folder: {e}"


def move_file(source, destination):
    try:
        shutil.move(source, destination)
        build_file_index()
        return f"File moved from {source} to {destination}"
    except Exception as e:
        return f"Failed to move file: {e}"


def list_files(folder_path):
    try:
        if folder_path == ".":
            folder_path = os.path.join(os.path.expanduser("~"), "Desktop")
            
        if not os.path.exists(folder_path):
            return f"Folder not found: {folder_path}"
        
        files = os.listdir(folder_path)
        return f"Files in {os.path.basename(folder_path)}:\n" + "\n".join(files[:20])
    except Exception as e:
        return f"Failed to list files: {e}"
