# Ctecka Book Processing Pipeline

This project provides a robust, modular Python pipeline for recursively processing a directory of book files, extracting metadata, and organizing them by author using LLM (Ollama) reasoning.

## Features
- **Recursive Directory Processing:** Handles large, nested directories of book files.
- **Format Extraction:** Extracts the first 1000 words (with a character cap) from supported file types (e.g., EPUB, TXT, PDF, etc.).
- **LLM Metadata Extraction:** Uses an LLM (via Ollama) to deduce and extract the author, title, and language for each book file, using both file content and filename/path.
- **Strict Prompting:** LLM is instructed to avoid placeholders (e.g., 'AUTHOR', 'UNKNOWN') and only output real author names, clean titles, and language.
- **Optional Sandbox:** You can choose to process files in a sandbox copy or in-place, preserving changes between runs and allowing incremental processing.
- **Immediate LLM Validation:** After each file is classified, a second LLM (reasoning model) validates the author name (up to 5 times). Only valid results are saved to the final directory; invalids go to an error folder.
- **File Organization:** Files are moved/copied to a final directory structure by author, with filenames including author, title, and language (all sanitized for Windows/UTF-8).
- **Error Handling & Logging:** All errors (extraction, LLM, file ops) are logged and summarized at the end, with color-coded output for clarity.
- **Modular Codebase:** Main logic is split into `main.py`, `extract.py`, `file_utils.py`, and `llm_utils.py` for maintainability.

## Directory Structure
```
finally_finally_processed/
    <Author Name>/
        <Author>-<Title>-<Language>.<ext>
    invalid_classification/
        ...
processed/
sandbox/
```

## Usage
1. **Install Requirements:**
   ```
   pip install -r requirements.txt
   ```
2. **Install Ollama and Models:**
   - [Ollama](https://ollama.com/) must be installed and in your PATH.
   - Required models (e.g., `qwen2:7b`, `deepseek-r1:8b`) must be pulled:
     ```
     ollama pull qwen2:7b
     ollama pull deepseek-r1:8b
     ```
3. **Configure Input Directory:**
   - Set `root_path` in `main.py` to your source directory of book files.
4. **Choose Processing Mode:**
   - In `main.py`, set `use_sandbox=True` to process a sandbox copy, or `use_sandbox=False` to process files in place and keep changes between runs.
5. **Run the Pipeline:**
   ```
   python main.py
   ```
6. **Review Results:**
   - Processed and categorized files will be in `finally_finally_processed/`.
   - Invalid classifications will be in `finally_finally_processed/invalid_classification/`.
   - Errors and progress are printed to the console with color coding.

## Customization
- **Supported File Types:**
  - Add or modify extraction logic in `extract.py`.
- **LLM Prompting:**
  - Adjust prompt logic in `llm_utils.py` for different metadata extraction or stricter validation.
- **Directory Structure:**
  - Change output structure in `main.py` as needed.

## Troubleshooting
- **Ollama Not Found:** Ensure Ollama is installed and in your PATH.
- **Model Not Installed:** Run `ollama pull <model>` for any missing models.
- **Extraction Errors:** Unsupported or corrupt files will be reported at the end.
- **LLM Output Issues:** If the LLM outputs placeholders or invalid data, check and refine the prompt in `llm_utils.py`.

## License
MIT License

---

**Author:** Nacor-MJ

For questions or contributions, please open an issue or pull request.
