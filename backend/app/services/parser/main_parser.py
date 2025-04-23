import os
import uuid
from typing import List, Dict, Any, Tuple

# Parsing Libraries
from pypdf import PdfReader
import docx

# OCR & Image Handling
from PIL import Image
from pdf2image import convert_from_path # Import pdf2image
from pdf2image.exceptions import PDFInfoNotInstalledError, PDFPageCountError, PDFSyntaxError

# Local Imports
from app.models.data_models import DocumentChunk
from app.services.parser.ocr import perform_ocr
from app.services.text_splitter import chunk_text, extract_urls
from app.core.config import settings

async def _parse_pdf(file_path: str, original_name: str, session_id: str) -> Tuple[List[DocumentChunk], List[str]]:
    """Parses PDF, handles text extraction and OCR fallback using pdf2image."""
    chunks = []
    urls = set() # Use set for unique URLs within the PDF
    try:
        # Check if poppler is installed (pdf2image depends on it)
        try:
            page_count_check = len(convert_from_path(file_path, first_page=1, last_page=1, fmt='jpeg', thread_count=1))
            if page_count_check < 1: raise ValueError("Test conversion failed")
            print("[Parser] Poppler (for pdf2image) seems available.")
            poppler_available = True
        except (PDFInfoNotInstalledError, FileNotFoundError, ValueError) as poppler_err:
            print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
            print("!!! WARNING: pdf2image dependency 'poppler' not found or not working. !!!")
            print("!!!          OCR fallback for image-based PDFs will be skipped.        !!!")
            print(f"!!!          Error details: {poppler_err}                      !!!")
            print("!!!          Install 'poppler-utils' (Debian/Ubuntu) or equivalent.  !!!")
            print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
            poppler_available = False
        except Exception as conversion_err:
             print(f"[Parser] Warning: Unexpected error during Poppler check: {conversion_err}")
             poppler_available = False # Assume not available on other errors


        reader = PdfReader(file_path)
        num_pages = len(reader.pages)
        print(f"[Parser] Processing PDF: {original_name}, Pages: {num_pages}")

        for page_num in range(num_pages):
            page_content = ""
            ocr_attempted = False
            page = reader.pages[page_num]
            print(f"[Parser] --- Page {page_num + 1}/{num_pages} ---")

            # 1. Try direct text extraction
            try:
                page_text = page.extract_text()
                if page_text and page_text.strip():
                    page_content = page_text
                    print(f"[Parser] Extracted text directly.")
                else:
                     print(f"[Parser] No direct text found.")
                     page_content = "" # Ensure it's empty if only whitespace
            except Exception as extract_err:
                print(f"[Parser] Error during direct text extraction: {extract_err}")
                page_content = ""

            # 2. If no text found and poppler is available, try OCR
            if not page_content and poppler_available:
                ocr_attempted = True
                print(f"[Parser] Attempting OCR fallback...")
                try:
                    # Convert current page to a PIL Image object
                    images = convert_from_path(
                        file_path,
                        dpi=200, # Resolution for OCR
                        first_page=page_num + 1,
                        last_page=page_num + 1,
                        fmt='jpeg', # Format for PIL
                        thread_count=1 # Process one page at a time
                    )
                    if images:
                        # Pass the PIL image directly to OCR function
                        ocr_text = perform_ocr(images[0])
                        if ocr_text:
                            page_content = ocr_text
                            print(f"[Parser] OCR successful.")
                        else:
                            print(f"[Parser] OCR completed but no text found.")
                    else:
                         print(f"[Parser] pdf2image conversion yielded no image for page.")

                except Exception as ocr_err:
                    print(f"[Parser] ERROR during OCR fallback for page {page_num + 1}: {ocr_err}")


            # 3. Process the content (either extracted text or OCR result)
            if page_content:
                page_urls = extract_urls(page_content)
                urls.update(page_urls) # Add unique URLs found on this page
                split_chunks = chunk_text(page_content)
                for text_chunk in split_chunks:
                    chunks.append(DocumentChunk(
                        session_id=session_id,
                        source=original_name,
                        text=text_chunk,
                        page=page_num + 1,
                        metadata={"parser": "pypdf", "ocr_attempted": ocr_attempted}
                    ))
                print(f"[Parser] Added {len(split_chunks)} chunks for page {page_num + 1}. Total Chunks: {len(chunks)}")
            else:
                 print(f"[Parser] No content (text or OCR) found for page {page_num + 1}.")


    except Exception as e:
        print(f"[Parser] ERROR Failed to process PDF {original_name}: {e}")
        import traceback
        traceback.print_exc()

    return chunks, list(urls) # Return unique URLs found across all pages

# --- Other Parsing Functions (_parse_docx, _parse_txt, _parse_image) remain the same ---
# Copy them here if they weren't in the previous update, otherwise this is fine

async def _parse_docx(file_path: str, original_name: str, session_id: str) -> Tuple[List[DocumentChunk], List[str]]:
    """Parses DOCX files."""
    chunks = []
    urls = set()
    try:
        doc = docx.Document(file_path)
        print(f"[Parser] Processing DOCX: {original_name}")
        full_text = "\n".join([para.text for para in doc.paragraphs if para.text])
        if full_text:
            urls.update(extract_urls(full_text))
            split_chunks = chunk_text(full_text)
            for text_chunk in split_chunks:
                chunks.append(DocumentChunk(
                    session_id=session_id,
                    source=original_name,
                    text=text_chunk,
                    metadata={"parser": "python-docx"}
                ))
    except Exception as e:
        print(f"[Parser] ERROR Failed to read DOCX {original_name}: {e}")
    return chunks, list(urls)

async def _parse_txt(file_path: str, original_name: str, session_id: str) -> Tuple[List[DocumentChunk], List[str]]:
    """Parses plain text files."""
    chunks = []
    urls = set()
    try:
        print(f"[Parser] Processing TXT: {original_name}")
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            full_text = f.read()
        if full_text:
            urls.update(extract_urls(full_text))
            split_chunks = chunk_text(full_text)
            for text_chunk in split_chunks:
                chunks.append(DocumentChunk(
                    session_id=session_id,
                    source=original_name,
                    text=text_chunk,
                    metadata={"parser": "text"}
                ))
    except Exception as e:
        print(f"[Parser] ERROR Failed to read TXT {original_name}: {e}")
    return chunks, list(urls)

async def _parse_image(file_path: str, original_name: str, session_id: str) -> Tuple[List[DocumentChunk], List[str]]:
    """Handles image files using OCR."""
    chunks = []
    urls = set()
    print(f"[Parser] Processing Image for OCR: {original_name}")
    ocr_text = perform_ocr(file_path)
    if ocr_text:
        urls.update(extract_urls(ocr_text))
        split_chunks = chunk_text(ocr_text)
        for text_chunk in split_chunks:
            chunks.append(DocumentChunk(
                session_id=session_id,
                source=original_name,
                text=text_chunk,
                metadata={"parser": "ocr"}
            ))
    else:
        print(f"[Parser] No text extracted via OCR from {original_name}")
    return chunks, list(urls)

# --- Main Parsing Function ---
async def process_document(file_path: str, original_name: str, session_id: str) -> Tuple[List[DocumentChunk], List[str]]:
    """Routes file processing based on extension."""
    print(f"[Parser Service] Routing: {original_name} (Session: {session_id})")
    file_extension = os.path.splitext(original_name)[1].lower()
    chunks = []
    urls = [] # Now stores unique URLs gathered from sub-parsers

    try:
        if file_extension == '.pdf':
            chunks, urls_list = await _parse_pdf(file_path, original_name, session_id)
            urls.extend(urls_list) # Use extend for list
        elif file_extension == '.docx':
             chunks, urls_list = await _parse_docx(file_path, original_name, session_id)
             urls.extend(urls_list)
        elif file_extension == '.txt':
             chunks, urls_list = await _parse_txt(file_path, original_name, session_id)
             urls.extend(urls_list)
        elif file_extension in ['.png', '.jpg', '.jpeg', '.tiff', '.bmp', '.gif']:
            chunks, urls_list = await _parse_image(file_path, original_name, session_id)
            urls.extend(urls_list)
        # Add elif blocks for other formats here if needed
        else:
            print(f"[Parser Service] Warning: Unsupported file type '{file_extension}' for {original_name}")

        unique_urls = sorted(list(set(urls))) # Ensure final list is unique
        print(f"[Parser Service] Finished processing {original_name}. Found {len(chunks)} chunks, {len(unique_urls)} unique URLs.")

    except Exception as e:
         print(f"[Parser Service] CRITICAL ERROR during processing of {original_name}: {e}")
         import traceback
         traceback.print_exc()

    return chunks, unique_urls # Return chunks and unique URLs

