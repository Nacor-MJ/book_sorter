import os
import shutil
from pathlib import Path
from collections import Counter

def extractability_check(working_root, extract_first_1000_words, print_progress, visit_files, CYAN, succeeded_extensions, failed_extensions, checked_extensions):
    """
    Checks which file extensions in the working directory are extractable by attempting to extract from one file per extension.
    Populates succeeded_extensions and failed_extensions lists.
    """
    print_progress("Checking which file extensions are extractable (one file per extension)...", CYAN)
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
    visit_files(str(working_root), check_extractable_once_per_ext)
    print_progress("Sandbox checking complete.", CYAN)

def print_extension_summary(working_root, visit_files, CYAN, YELLOW, GREEN, RED, succeeded_extensions, failed_extensions, RESET):
    """
    Prints a summary of all file extensions found in the working directory, including which were extractable and which were not.
    """
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

def collect_extractable_files(working_root, succeeded_extensions, visit_files):
    """
    Collects all files in the working directory that have an extension listed in succeeded_extensions.
    Returns a list of file paths.
    """
    extractable_files = []
    def collect(file_path: str) -> None:
        ext = os.path.splitext(file_path)[1].lower()
        if ext in succeeded_extensions:
            extractable_files.append(str(file_path))
    visit_files(str(working_root), collect)
    return extractable_files

def categorize_validate_and_move_files(
    extractable_files, extract_first_1000_words, get_existing_authors, categorize_with_llm, validate_author_name_with_llm, standardize_filename,
    finally_processed_dir, error_dir, print_progress, CYAN, YELLOW, GREEN, RED
):
    """
    For each extractable file:
    - Extracts the first 1000 words.
    - Uses the LLM to categorize (author, title, language).
    - Validates the result with a reasoning LLM (up to 5 times).
    - If valid, moves the file to the final directory; otherwise, moves it to the error folder.
    Returns a list of processing errors.
    """
    processing_errors = []
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
                    break
                else:
                    print_progress(f"Invalid classification for '{author}': {reason}", RED)
                    if attempt == max_attempts - 1:
                        shutil.copy2(processed_file, error_dir / os.path.basename(processed_file))
                        print_progress(f"Max attempts reached. File moved to error folder.", RED)
                    else:
                        print_progress(f"Retrying LLM classification for {processed_file} (attempt {attempt+2}/{max_attempts})...", YELLOW)
            os.remove(processed_file)
        except Exception as e:
            processing_errors.append((processed_file, str(e)))
    return processing_errors

def validate_author_folders(finally_processed_dir, validate_author_name_with_llm, print_progress, RED, CYAN):
    """
    Validates all author folders in the final directory using the reasoning LLM.
    Moves invalid author folders and their files to a dedicated error directory.
    """
    error_dir = finally_processed_dir / "invalid_author_folders"
    error_dir.mkdir(exist_ok=True)
    for author_folder in [d for d in finally_processed_dir.iterdir() if d.is_dir() and d.name != "invalid_author_folders"]:
        is_valid, reason = validate_author_name_with_llm(author_folder.name)
        if not is_valid:
            print_progress(f"Invalid author folder: {author_folder.name} ({reason})", RED)
            for file in author_folder.iterdir():
                shutil.move(str(file), error_dir / file.name)
            author_folder.rmdir()
    print_progress("Author folder validation complete!", CYAN)
