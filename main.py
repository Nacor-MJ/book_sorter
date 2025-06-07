import os
import shutil
import stat
from pathlib import Path
from collections import Counter

from extract import extract_first_1000_words
from file_utils import visit_files, print_progress, clean_and_create_dir, copy_tree
from llm_utils import standardize_filename, get_existing_authors, categorize_with_llm
from pipeline_utils import extractability_check, print_extension_summary, collect_extractable_files, categorize_validate_and_move_files, validate_author_folders

# ANSI color codes for colorful output
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
CYAN = '\033[96m'
RESET = '\033[0m'

def process_file(file_path: str) -> None:
    """
    Process an individual file to extract its content.
    This is a utility for debugging or testing extraction logic on a single file.
    """
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
    - Optionally clears and copies files to a sandbox directory.
    - Checks extractability of file types.
    - Prints a summary of file extensions.
    - Processes extractable files: categorizes, validates, and moves them.
    - Handles errors and prints a summary.
    - Validates author folders at the end.
    """
    # Clean slate: remove sandbox and processed directories if they exist
    for dir_path in [sandbox_path, processed_dir]:
        if clear_sandbox:
            clean_and_create_dir(dir_path)
    finally_processed_dir.mkdir(exist_ok=True)
    if clear_sandbox:
        copy_tree(root_path, sandbox_path)
        working_root = sandbox_path
    else:
        working_root = Path(root_path)
    failed_extensions = []
    succeeded_extensions = []
    checked_extensions = set()
    extractability_check(working_root, extract_first_1000_words, print_progress, visit_files, CYAN, succeeded_extensions, failed_extensions, checked_extensions)
    print_extension_summary(working_root, visit_files, CYAN, YELLOW, GREEN, RED, succeeded_extensions, failed_extensions, RESET)
    extractable_files = collect_extractable_files(working_root, succeeded_extensions, visit_files)
    from llm_utils import validate_author_name_with_llm
    error_dir = finally_processed_dir / "invalid_classification"
    error_dir.mkdir(exist_ok=True)
    processing_errors = categorize_validate_and_move_files(
        extractable_files, extract_first_1000_words, get_existing_authors, categorize_with_llm, validate_author_name_with_llm, standardize_filename, finally_processed_dir, error_dir, print_progress, CYAN, YELLOW, GREEN, RED
    )
    print_progress("\nAll done!", CYAN)
    if processing_errors:
        print(f"{RED}\nErrors encountered during processing:{RESET}")
        for file, err in processing_errors:
            print(f"{RED}{file}: {err}{RESET}")
    else:
        print(f"{GREEN}\nNo errors encountered during processing!{RESET}")
    print_progress("\nValidating author folder names with LLM...", CYAN)
    validate_author_folders(finally_processed_dir, validate_author_name_with_llm, print_progress, RED, CYAN)

# Main program entrypoint
if __name__ == "__main__":
    """
    Entrypoint for the file processing pipeline.
    Adjust root_path as needed for your environment.
    """
    root_path = "C:/Users/matou/Desktop/ctecka"
    sandbox_path = Path("sandbox")
    processed_dir = Path("processed")
    finally_processed_dir = Path("finally_finally_processed")
    # Set clear_sandbox to True to use the sandbox copy, or False to process files in place
    process_all_files(root_path, sandbox_path, processed_dir, finally_processed_dir, clear_sandbox=True)