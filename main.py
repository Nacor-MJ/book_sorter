import os
import shutil
import stat
from pathlib import Path
from collections import Counter

from extract import extract_first_1000_words
from file_utils import visit_files, copy_file_preserve_structure, remove_readonly, print_progress, clean_and_create_dir, copy_tree
from llm_utils import standardize_filename, get_existing_authors, categorize_with_llm

# ANSI color codes for colorful output
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
CYAN = '\033[96m'
RESET = '\033[0m'

# Function to process each file (customize as needed)
def process_file(file_path: str) -> None:
    """Process an individual file to extract its content."""
    print(f"Processing file: {file_path}")
    try:
        _buffer = extract_first_1000_words(file_path)
        # You can do something with the buffer here, e.g., print or store it
        # print(buffer)
    except Exception as e:
        print(f"Error processing {file_path}: {e}")

def process_all_files(root_path: str, sandbox_path: Path, processed_dir: Path, finally_processed_dir: Path, clear_sandbox: bool = True):
    """
    Main workflow for processing, checking, and categorizing files.
    If use_sandbox is True, copies all files from root_path to sandbox. Otherwise, processes files in root_path directly.
    After each file is classified, the reasoning LLM validates the classification (up to 5 times). If valid, the file is saved to finally_finally_processed and deleted from the source. Otherwise, it is moved to an error folder.
    """
    # Clean slate: remove sandbox and processed directories if they exist
    for dir_path in [sandbox_path, processed_dir]:
        if clear_sandbox:
            clean_and_create_dir(dir_path)
    finally_processed_dir.mkdir(exist_ok=True)

    # Copy all files from root_path to sandbox, preserving structure (if enabled)
    if clear_sandbox:
        copy_tree(root_path, sandbox_path)
        working_root = sandbox_path
    else:
        working_root = Path(root_path)

    # --- Extractability Check ---
    failed_extensions = []
    succeeded_extensions = []
    extractable_files = []
    checked_extensions = set()
    processing_errors = []  # Collect errors for final reporting

    def check_extractable_once_per_ext(file_path: str) -> None:
        ext = os.path.splitext(file_path)[1].lower()
        if ext in checked_extensions:
            return
        checked_extensions.add(ext)
        try:
            extract_first_1000_words(file_path)
            succeeded_extensions.append(ext)
        except Exception:
            failed_extensions.append(ext)

    print_progress("Checking which file extensions are extractable (one file per extension)...", CYAN)
    visit_files(str(working_root), check_extractable_once_per_ext)
    print_progress("Sandbox checking complete.", CYAN)

    # --- Print summary of file types ---
    all_extensions = []
    def collect_all_extensions(file_path: str) -> None:
        ext = os.path.splitext(file_path)[1].lower()
        all_extensions.append(ext)
    visit_files(str(working_root), collect_all_extensions)
    ext_counts = Counter(all_extensions)

    print(f"{CYAN}\nFile extension summary in sandbox:{RESET}")
    for ext, count in ext_counts.items():
        print(f"{CYAN}{ext}: {count} file(s){RESET}")

    if failed_extensions:
        print(f"{YELLOW}\nFile extensions that could NOT be extracted:{RESET}")
        for ext in set(failed_extensions):
            print(f"{YELLOW}{ext}{RESET}")
    else:
        print(f"{GREEN}\nAll file types were extractable!{RESET}")

    if succeeded_extensions:
        print(f"{GREEN}\nFile types that were successfully extracted:{RESET}")
        for ext in set(succeeded_extensions):
            print(f"{GREEN}{ext}{RESET}")
    else:
        print(f"{RED}\nNo file types were successfully extracted!{RESET}")

    # --- Collect all files with succeeded extensions for further processing ---
    def collect_extractable_files(file_path: str) -> None:
        ext = os.path.splitext(file_path)[1].lower()
        if ext in succeeded_extensions:
            extractable_files.append(str(file_path))
    visit_files(str(working_root), collect_extractable_files)

    # --- Categorize, validate, and move extractable files ---
    print_progress("\nStarting categorization, validation, and final copy...", CYAN)
    from llm_utils import validate_author_name_with_llm
    error_dir = finally_processed_dir / "invalid_classification"
    error_dir.mkdir(exist_ok=True)
    for idx, processed_file in enumerate(extractable_files, 1):
        ext = os.path.splitext(processed_file)[1]
        print_progress(f"[{idx}/{len(extractable_files)}] Processing: {processed_file}", CYAN)
        try:
            buffer = extract_first_1000_words(processed_file)
            existing_authors = get_existing_authors(finally_processed_dir)
            max_attempts = 5
            for attempt in range(max_attempts):
                author, title, language = categorize_with_llm(buffer, processed_file, existing_authors)
                print_progress(f"LLM output: author='{author}', title='{title}', language='{language}'", YELLOW)
                # Validate classification with reasoning LLM (up to 5 times)
                valid, reason = False, ""
                for v_attempt in range(5):
                    valid, reason = validate_author_name_with_llm(author, title=title, language=language)
                    if valid:
                        break
                if valid:
                    author_dir = finally_processed_dir / author
                    author_dir.mkdir(parents=True, exist_ok=True)
                    new_filename = standardize_filename(author, title, language, ext)
                    target_path = author_dir / new_filename
                    shutil.copy2(processed_file, target_path)
                    print_progress(f"Validated and copied: {processed_file} -> {target_path}", GREEN)
                    break  # Success, stop retrying
                else:
                    print_progress(f"Invalid classification for '{author}': {reason}", RED)
                    if attempt == max_attempts - 1:
                        shutil.copy2(processed_file, error_dir / os.path.basename(processed_file))
                        print_progress(f"Max attempts reached. File moved to error folder.", RED)
                    else:
                        print_progress(f"Retrying LLM classification for {processed_file} (attempt {attempt+2}/{max_attempts})...", YELLOW)
            # Remove the file from the working directory
            os.remove(processed_file)
        except Exception as e:
            processing_errors.append((processed_file, str(e)))
    print_progress("\nAll done!", CYAN)

    # --- Print all errors at the end ---
    if processing_errors:
        print(f"{RED}\nErrors encountered during processing:{RESET}")
        for file, err in processing_errors:
            print(f"{RED}{file}: {err}{RESET}")
    else:
        print(f"{GREEN}\nNo errors encountered during processing!{RESET}")

    # --- Validate author folder names with LLM and move invalids ---
    print_progress("\nValidating author folder names with LLM...", CYAN)
    error_dir = finally_processed_dir / "invalid_author_folders"
    error_dir.mkdir(exist_ok=True)
    from llm_utils import validate_author_name_with_llm
    for author_folder in [d for d in finally_processed_dir.iterdir() if d.is_dir() and d.name != "invalid_author_folders"]:
        is_valid, reason = validate_author_name_with_llm(author_folder.name)
        if not is_valid:
            print_progress(f"Invalid author folder: {author_folder.name} ({reason})", RED)
            # Move all files in this folder to error_dir, preserving filenames
            for file in author_folder.iterdir():
                shutil.move(str(file), error_dir / file.name)
            # Remove the now-empty folder
            author_folder.rmdir()
    print_progress("Author folder validation complete!", CYAN)

# Main program
if __name__ == "__main__":
    """
    Entrypoint for the file processing pipeline.
    Adjust root_path as needed for your environment.
    """
    root_path = "C:/Users/matou/Desktop/ctecka"
    sandbox_path = Path("sandbox")
    processed_dir = Path("processed")
    finally_processed_dir = Path("finally_finally_processed")
    # Set use_sandbox to True to use the sandbox copy, or False to process files in place
    process_all_files(root_path, sandbox_path, processed_dir, finally_processed_dir, clear_sandbox=True)