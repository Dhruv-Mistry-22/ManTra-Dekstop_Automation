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
    """
    Open a file smartly.
    Search order:
      1. Exact absolute path
      2. Desktop — exact name match (with or without extension)
      3. Desktop — fuzzy name match
      4. Full file index — fuzzy match
    """
    try:
        name = file_path_or_name.strip()

        # 1. Already a valid absolute path
        if os.path.isabs(name) and os.path.exists(name):
            os.startfile(name)
            return f"✅ Opened: {os.path.basename(name)}"

        desktop = os.path.join(os.path.expanduser("~"), "Desktop")

        # 2. Desktop — exact match (try with and without common extensions)
        for candidate in os.listdir(desktop):
            candidate_path = os.path.join(desktop, candidate)
            if not os.path.isfile(candidate_path):
                continue
            # Match full name or stem (without extension)
            stem = os.path.splitext(candidate)[0]
            if candidate.lower() == name.lower() or stem.lower() == name.lower():
                os.startfile(candidate_path)
                return f"✅ Opened '{candidate}' from Desktop."

        # 3. Desktop — fuzzy match
        from rapidfuzz import process as fuzz_proc, fuzz
        desktop_files = {}
        for f in os.listdir(desktop):
            fp = os.path.join(desktop, f)
            if os.path.isfile(fp):
                stem = os.path.splitext(f)[0].lower()
                desktop_files[stem] = fp
                desktop_files[f.lower()] = fp   # also index full name

        if desktop_files:
            best = fuzz_proc.extractOne(name.lower(), list(desktop_files.keys()), scorer=fuzz.WRatio)
            if best and best[1] > 65:
                actual = desktop_files[best[0]]
                os.startfile(actual)
                return f"✅ Opened '{os.path.basename(actual)}' from Desktop."

        # 4. Fall back to full file index
        if not _index_ready:
            return "❌ File not found on Desktop and file index is still loading. Try again in a few seconds."

        best_match = fuzz_proc.extractOne(name.lower(), list(FILE_INDEX.keys()), scorer=fuzz.WRatio)
        if best_match and best_match[1] > 70:
            actual_path = FILE_INDEX[best_match[0]]
            os.startfile(actual_path)
            return f"✅ Opened '{os.path.basename(actual_path)}' (found in {os.path.dirname(actual_path)})."

        return (
            f"❌ Could not find '{name}' on your Desktop or common folders.\n"
            f"   Tip: Say 'create file {name}' to create it first."
        )
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
    """Create a new empty file on the Desktop and open Explorer to show it."""
    try:
        if not os.path.isabs(file_path):
            desktop = os.path.join(os.path.expanduser("~"), "Desktop")
            file_path = os.path.join(desktop, file_path)

        # Create any missing parent directories then touch the file
        Path(file_path).parent.mkdir(parents=True, exist_ok=True)
        Path(file_path).touch()

        # Refresh file index in background
        build_file_index()

        # Open File Explorer with the new file selected so user can see it instantly
        try:
            import subprocess
            subprocess.Popen(["explorer", "/select,", file_path])
        except Exception:
            pass  # Non-critical — file is still created even if Explorer doesn't open

        basename = os.path.basename(file_path)
        return f"✅ File '{basename}' created on Desktop — File Explorer opened to show it."
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


def list_desktop_files() -> str:
    """Return a formatted list of all files currently on the Desktop."""
    try:
        desktop = os.path.join(os.path.expanduser("~"), "Desktop")
        items = os.listdir(desktop)
        files = [f for f in items if os.path.isfile(os.path.join(desktop, f))]
        folders = [f for f in items if os.path.isdir(os.path.join(desktop, f))]
        lines = []
        if files:
            lines.append(f"📄 Files ({len(files)}):")
            lines.extend(f"   • {f}" for f in sorted(files))
        if folders:
            lines.append(f"📁 Folders ({len(folders)}):")
            lines.extend(f"   • {f}" for f in sorted(folders))
        return "\n".join(lines) if lines else "Desktop is empty."
    except Exception as e:
        return f"Failed to list Desktop: {e}"


def undo_last_creation(memory) -> str:
    """
    Reverse the most recent 'created' action stored in MemoryBank.

    - If the last created item was a FILE  → delete that file
    - If the last created item was a FOLDER → delete that folder (and contents)

    Looks back through up to 10 recent memory entries to find a 'created' action.
    Returns a human-readable result string.
    """
    try:
        recent = memory.get_recent(10)
        # Find the most recent "created" entry
        last_created = None
        for entry in reversed(recent):
            if entry.get("action") == "created":
                last_created = entry
                break

        if not last_created:
            return (
                "❌ Nothing to undo — I haven't created any files or folders in this session.\n"
                "   Use 'delete file <name>' to delete a specific file."
            )

        entity_type  = last_created["entity_type"]   # "file" or "folder"
        entity_value = last_created["entity_value"]  # e.g. "report.txt"

        # Resolve to an absolute path (Desktop is the default creation location)
        if not os.path.isabs(entity_value):
            desktop_path = os.path.join(os.path.expanduser("~"), "Desktop", entity_value)
        else:
            desktop_path = entity_value

        if entity_type == "file":
            if os.path.exists(desktop_path):
                os.remove(desktop_path)
                build_file_index()
                return f"✅ Deleted file '{os.path.basename(desktop_path)}' from Desktop (undo last creation)."
            # Try current dir as fallback
            if os.path.exists(entity_value):
                os.remove(entity_value)
                build_file_index()
                return f"✅ Deleted file '{entity_value}' (undo last creation)."
            return f"❌ Could not find '{entity_value}' to delete — it may have already been removed."

        elif entity_type == "folder":
            if os.path.exists(desktop_path):
                shutil.rmtree(desktop_path)
                return f"✅ Deleted folder '{os.path.basename(desktop_path)}' from Desktop (undo last creation)."
            if os.path.exists(entity_value):
                shutil.rmtree(entity_value)
                return f"✅ Deleted folder '{entity_value}' (undo last creation)."
            return f"❌ Could not find folder '{entity_value}' to delete."

        return f"❌ Cannot undo '{entity_type}' action automatically."

    except Exception as e:
        return f"Failed to undo last creation: {e}"

