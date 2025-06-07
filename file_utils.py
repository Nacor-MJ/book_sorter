from pathlib import Path
import shutil
import os
import stat

# Visit all files recursively and apply a callback
def visit_files(path: str, callback) -> None:
    for entry in os.scandir(path):
        if entry.is_dir():
            visit_files(entry.path, callback)
        elif entry.is_file():
            callback(entry.path)

def copy_file_preserve_structure(src_file: str, src_root: Path, dst_root: Path) -> Path:
    rel_path = Path(src_file).relative_to(src_root)
    target_path = dst_root / rel_path
    target_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src_file, target_path)
    return target_path

# Remove read-only attribute and retry the operation (for Windows file deletion)
def remove_readonly(func, path, excinfo):
    os.chmod(path, stat.S_IWRITE)
    func(path)

# Utility: Print a progress message with color
def print_progress(message: str, color: str = '\033[96m'):
    RESET = '\033[0m'
    print(f"{color}{message}{RESET}")

# Utility: Clean and recreate a directory
def clean_and_create_dir(dir_path: Path):
    YELLOW = '\033[93m'
    GREEN = '\033[92m'
    if dir_path.exists():
        print_progress(f"Cleaning directory: {dir_path}", YELLOW)
        shutil.rmtree(dir_path, onerror=remove_readonly)
    dir_path.mkdir()
    print_progress(f"Created directory: {dir_path}", GREEN)

# Utility: Copy all files from src_root to dst_root, preserving structure
def copy_tree(src_root: str, dst_root: Path):
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    print_progress(f"Copying files from {src_root} to {dst_root} ...", CYAN)
    for dirpath, dirnames, filenames in os.walk(src_root):
        rel_dir = os.path.relpath(dirpath, src_root)
        target_dir = dst_root / rel_dir if rel_dir != '.' else dst_root
        target_dir.mkdir(parents=True, exist_ok=True)
        for filename in filenames:
            src_file = os.path.join(dirpath, filename)
            dst_file = target_dir / filename
            shutil.copy2(src_file, dst_file)
    print_progress(f"Copy complete!", GREEN)
