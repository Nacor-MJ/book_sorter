import re
import subprocess
from pathlib import Path
from typing import List, Tuple, Optional
import sys

LLM_MODEL = "qwen2:7b"
LLM_REASONING = "qwen2:7b"

# Default known languages
KNOWN_LANGUAGES = {"english", "czech"}

# Cache for encountered languages (persisted in memory for this run)
encountered_languages = set(KNOWN_LANGUAGES)

# ANSI color codes for colorful output (for debugging)
YELLOW = '\033[93m'
RESET = '\033[0m'

def check_ollama_model_installed(model_name: str):
    try:
        result = subprocess.run(["ollama", "list"], capture_output=True, text=True)
        if result.returncode != 0:
            print(f"{model_name} model check failed. Is Ollama installed and in PATH?")
            sys.exit(1)
        if model_name not in result.stdout:
            print(f"Model '{model_name}' is not installed. To install, run:")
            print(f"ollama pull {model_name}")
            sys.exit(1)
    except Exception as e:
        print(f"Error checking Ollama model: {e}")
        sys.exit(1)

# Check model on import
check_ollama_model_installed(LLM_MODEL)
check_ollama_model_installed(LLM_REASONING)


def standardize_filename(author: str, title: str, language: str, ext: str) -> str:
    """
    Create a safe, standardized filename for a book.
    Removes or replaces characters not allowed in Windows filenames.
    """
    def clean(s):
        # Remove invalid filename characters for Windows
        return re.sub(r'[<>:"/\\|?*]', '_', s).strip().replace(' ', '_')
    author_clean = clean(author)
    title_clean = clean(title)
    language_clean = clean(language)
    ext_clean = clean(ext)
    return f"{author_clean}-{title_clean}-{language_clean}{ext_clean}"


def get_existing_authors(finally_processed_dir: Path) -> List[str]:
    if not finally_processed_dir.exists():
        return []
    return [d.name for d in finally_processed_dir.iterdir() if d.is_dir()]


def categorize_with_llm(buffer: str, file_path: str, existing_authors: list[str]) -> Tuple[str, str, str]:
    # Add language recognition and pass known/encountered languages
    prompt = (
        f"Given the following text excerpt (first 1000 words) from a book file, "
        f"and the file path: {file_path},\n"
        f"You may use the file name and path to deduce the author, title, and language.\n"
        f"Please extract ONLY the author, title, and language.\n"
        f"Do NOT attempt to categorize or assign a genre.\n"
        f"Do NOT include any commentary, disclaimers, or extra information.\n"
        f"Return ONLY the author, title, and language in the format: AUTHOR|||TITLE|||LANGUAGE.\n"
        f"Do NOT output a header or example like 'AUTHOR|||TITLE|||LANGUAGE'. Only output the actual values.\n"
        f"Remove any redundant information from the title, such as file extensions, (epub), or similar tags. The title should be clean and not contain format or file type info.\n"
        f"The AUTHOR field must be the actual name of the author (e.g. 'Agatha Christie', 'J.K. Rowling'). Never use placeholders like 'AUTHOR', 'UNKNOWN', 'TITLE', 'BOOK', 'N/A', 'ANONYMOUS', or anything that is not a real person's name. If you cannot determine the author, output 'unknown_author'.\n"
        f"The TITLE field must be the actual book title, not the author name or a placeholder. If you cannot determine the title, output 'unknown_title'.\n"
        f"The LANGUAGE field must be the language only (e.g. 'English', 'Czech'), not a phrase or label.\n"
        f"If you are unsure, prefer 'unknown_author' for author and 'unknown_title' for title, but NEVER output 'AUTHOR', 'TITLE', 'BOOK', 'N/A', 'ANONYMOUS', or similar placeholders.\n"
        f"For clarity, here is a Python snippet showing how your output will be parsed:\n"
        f"\noutput = 'your_response_here'\nfor line in output.splitlines():\n    if '|||' in line:\n        author, title, language = line.split('|||')\n"
        f"Excerpt:\n{buffer}"
    )
    result = subprocess.run([
        "ollama", "run", LLM_MODEL, prompt
    ], capture_output=True, text=True, encoding='utf-8', errors="replace")
    output = result.stdout.strip()
    print(f"{YELLOW}Raw LLM output: {output}{RESET}")
    # Remove any header line like 'AUTHOR|||TITLE|||LANGUAGE' if present
    lines = [line for line in output.splitlines() if line.strip()]
    if lines and lines[0].strip().upper() == 'AUTHOR|||TITLE|||LANGUAGE':
        lines = lines[1:]
    output_clean = '\n'.join(lines).strip()
    # Now parse the first line with '|||' as the actual result
    for line in output_clean.splitlines():
        if '|||' in line:
            parts = line.split('|||')
            if len(parts) >= 3:
                author, title, language = parts[0].strip(), parts[1].strip(), parts[2].strip()
            else:
                author, title, language = parts[0].strip(), parts[1].strip(), "unknown"
            encountered_languages.add(language.lower())
            # If author is a forbidden placeholder, treat as error
            forbidden = {"author", "title", "book", "n/a", "anonymous"}
            if author.strip().lower() in forbidden:
                raise ValueError(f"LLM returned forbidden author placeholder '{author}' for file: {file_path}")
            # If both author and title are unknown, treat as error
            if (author.lower() == 'unknown_author' and title.lower() == 'unknown_title'):
                raise ValueError("LLM returned unknown_author, unknown_title for file: " + str(file_path))
            return author, title, language
    # If no valid line found, treat as error
    raise ValueError(f"LLM did not return a valid AUTHOR|||TITLE|||LANGUAGE line for file: {file_path}. Output: {output}")

def validate_author_name_with_llm(author_name: str, max_retries: int = 10, title: Optional[str] = None, language: Optional[str] = None) -> tuple[bool, str]:
    """
    Use the LLM to check if the given author folder name is a valid, real author name.
    Also checks that the title and language make sense together with the author.
    Returns (is_valid, reason). Retries up to max_retries if the LLM output is unclear.
    Accepts unknown_author as valid if the title is known and plausible.
    """
    import subprocess
    import time
    forbidden = {"author", "title", "book", "n/a", "anonymous"}
    if author_name.strip().lower() in forbidden:
        return (False, f"Author is a forbidden placeholder: {author_name}")
    if author_name.strip().lower() == "unknown_author" and title and title.strip().lower() != "unknown_title":
        # Still check that the title and language are plausible
        pass  # Continue to LLM check below
    prompt = (
        f"You are given the following metadata for a book file:\n"
        f"Author: '{author_name}'\n"
        f"Title: '{title}'\n"
        f"Language: '{language}'\n"
        f"Check all three fields together.\n"
        f"Is the author a real, plausible author name (not a placeholder or nonsense)?\n"
        f"Is the title a plausible book title (not a placeholder, not the author name, not nonsense)?\n"
        f"Is the language a plausible language for a book (e.g. 'English', 'Czech', etc.)?\n"
        f"If all three are plausible, return 'VALID|||reason'.\n"
        f"If any are not plausible, return 'INVALID|||reason' and explain which field(s) are problematic.\n"
        f"Do NOT include commentary, headers, or extra lines.\n"
        f"For example, 'AUTHOR', 'UNKNOWN', 'AUTHOR-TITLE', 'TITLE', 'BOOK', 'N/A', 'ANONYMOUS', or anything that is not a plausible human name or book title should be INVALID.\n"
        f"Output format: VALID|||reason or INVALID|||reason.\n"
        f"Here is a Python snippet showing how your output will be parsed:\n"
        f"output = 'your_response_here'\nfor line in output.splitlines():\n    if '|||' in line:\n        status, reason = line.split('|||')\n"
        f"Author: {author_name}\nTitle: {title}\nLanguage: {language}"
    )
    last_output = ""
    for attempt in range(max_retries):
        result = subprocess.run([
            "ollama", "run", LLM_REASONING, prompt
        ], capture_output=True, text=True, encoding='utf-8', errors="replace")
        output = result.stdout.strip()
        last_output = output
        for line in output.splitlines():
            if '|||' in line:
                status, reason = line.split('|||', 1)
                status = status.strip().upper()
                reason = reason.strip()
                if status in ("VALID", "INVALID"):
                    return (status == "VALID", reason)
        time.sleep(0.5)  # brief pause before retry
    return (False, f"LLM failed to validate after {max_retries} attempts. Last output: {last_output}")
