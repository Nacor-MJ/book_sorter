import os
import docx
import PyPDF2
from ebooklib import epub, ITEM_DOCUMENT
from bs4 import BeautifulSoup

def extract_first_1000_words(file_path: str, max_chars: int = 10000) -> str:
    SUPPORTED_EXTENSIONS = {'.prc', '.pdb', '.fb2', '.docx', '.txt', '.doc', '.epub', '.mobi', '.pdf', '.azw3', '.opf', '.db'}
    ext = os.path.splitext(file_path)[1].lower()
    if ext == '.jpg' or ext not in SUPPORTED_EXTENSIONS:
        raise Exception(f"File extension {ext} is not supported for text extraction.")
    buffer = []
    def add_words(text):
        words = text.split()
        needed = 1000 - len(buffer)
        buffer.extend(words[:needed])
    if ext in {'.txt', '.fb2', '.opf'}:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            for line in f:
                add_words(line)
                if len(buffer) >= 1000:
                    break
    elif ext == '.docx':
        doc = docx.Document(file_path)
        for para in doc.paragraphs:
            add_words(para.text)
            if len(buffer) >= 1000:
                break
    elif ext == '.pdf':
        with open(file_path, 'rb') as f:
            reader = PyPDF2.PdfReader(f)
            for page in reader.pages:
                add_words(page.extract_text() or "")
                if len(buffer) >= 1000:
                    break
    elif ext == '.epub':
        try:
            book = epub.read_epub(file_path)
            for item in book.get_items():
                if item.get_type() == ITEM_DOCUMENT:
                    soup = BeautifulSoup(item.get_content().decode(errors='ignore'), 'html.parser')
                    add_words(soup.get_text(separator=' '))
                    if len(buffer) >= 1000:
                        break
        except KeyError as e:
            # Skip missing image or resource errors in EPUBs
            pass
    elif ext in {'.mobi', '.azw3', '.prc', '.pdb', '.doc'}:
        raise Exception(f"Extraction for {ext} not implemented. Use Calibre or similar tools.")
    elif ext == '.db':
        raise Exception(".db file extraction not implemented. Please specify the schema.")
    return ' '.join(buffer)
