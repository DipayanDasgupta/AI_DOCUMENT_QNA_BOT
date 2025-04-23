from fastapi import APIRouter, UploadFile, File, HTTPException, BackgroundTasks
from typing import List, Dict, Any
import shutil
import os
import uuid
import asyncio

from app.models.api_models import UploadResponse
from app.core.config import settings
from app.services.parser.main_parser import process_document
from app.services.knowledge.indexer import index_content, clear_session_data
from app.services.knowledge.crawler import fetch_and_parse_url
from app.models.data_models import DocumentChunk

router = APIRouter()

# --- Background Task Orchestration ---
async def background_process_files(files_data: List[Dict[str, str]], session_id: str):
    print(f"[Background Task:{session_id}] Started.")
    all_parsed_chunks: List[DocumentChunk] = []
    extracted_urls: set[str] = set() # Use set for unique URLs
    processing_errors: List[str] = []

    # 1. Parse Uploaded Files
    for file_data in files_data:
        file_path = file_data["path"]
        original_name = file_data["name"]
        print(f"[Background Task:{session_id}] Parsing file: {original_name}")
        try:
            parsed_chunks, file_urls = await process_document(file_path, original_name, session_id)
            if parsed_chunks:
                all_parsed_chunks.extend(parsed_chunks)
                print(f"[Background Task:{session_id}] Parsed {len(parsed_chunks)} chunks from {original_name}")
            if file_urls:
                extracted_urls.update(file_urls) # Add unique URLs
                print(f"[Background Task:{session_id}] Extracted {len(file_urls)} URLs from {original_name}")
        except Exception as e:
            error_msg = f"Failed to parse {original_name}: {e}"
            print(f"[Background Task:{session_id}] ERROR: {error_msg}")
            processing_errors.append(error_msg)
        finally:
            if os.path.exists(file_path):
                try: os.remove(file_path)
                except Exception as remove_err: print(f"[Background Task:{session_id}] ERROR: Failed to remove temp file {file_path}: {remove_err}")

    # 2. Crawl Extracted URLs (if any)
    crawled_chunks: List[DocumentChunk] = []
    if extracted_urls:
        print(f"[Background Task:{session_id}] Crawling {len(extracted_urls)} unique URLs...")
        # Create crawl tasks to run concurrently
        crawl_tasks = [fetch_and_parse_url(url, session_id, depth=0) for url in extracted_urls]
        crawl_results = await asyncio.gather(*crawl_tasks, return_exceptions=True)

        for result in crawl_results:
            if isinstance(result, list) and result: # Successful crawl returning chunks
                crawled_chunks.extend(result)
            elif isinstance(result, Exception):
                 print(f"[Background Task:{session_id}] ERROR during crawling: {result}")
                 processing_errors.append(f"Crawling failed: {result}")
            # Ignore None results (e.g., max depth, non-HTML)

        print(f"[Background Task:{session_id}] Crawling complete. Got {len(crawled_chunks)} chunks from web.")

    # Combine parsed and crawled chunks
    final_chunks_to_index = all_parsed_chunks + crawled_chunks

    # 3. Index Combined Content
    if final_chunks_to_index:
        print(f"[Background Task:{session_id}] Indexing {len(final_chunks_to_index)} total chunks...")
        try:
            index_success = await index_content(final_chunks_to_index, session_id)
            if index_success:
                print(f"[Background Task:{session_id}] Indexing successful.")
            else:
                 print(f"[Background Task:{session_id}] ERROR during indexing.")
                 processing_errors.append("Indexing failed for processed content.")
        except Exception as e:
             error_msg = f"Critical error during indexing call: {e}"
             print(f"[Background Task:{session_id}] ERROR: {error_msg}")
             processing_errors.append(error_msg)
    else:
         print(f"[Background Task:{session_id}] No content (parsed or crawled) to index.")


    # 4. Final Status Log
    if processing_errors:
        print(f"[Background Task:{session_id}] Completed with ERRORS: {processing_errors}")
    else:
        print(f"[Background Task:{session_id}] Completed successfully.")
    # TODO: Persistently store final status for session_id if needed

# --- API Endpoint ---
@router.post("/", response_model=UploadResponse, status_code=202)
async def handle_file_upload(
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(...)
):
    """
    Handles uploads, saves files, clears old session data, starts background processing.
    """
    session_id = str(uuid.uuid4())
    saved_files_data = []
    if not files: raise HTTPException(status_code=400, detail="No files uploaded.")

    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    await clear_session_data(session_id) # Clear any potential stale data first
    print(f"API: Handling upload for new session: {session_id}")

    for file in files:
        if not file.filename: continue
        safe_filename = os.path.basename(file.filename)
        temp_file_path = os.path.join(settings.UPLOAD_DIR, f"{session_id}_{safe_filename}")
        try:
            print(f"API: Saving temporary file: {temp_file_path}")
            with open(temp_file_path, "wb") as buffer: shutil.copyfileobj(file.file, buffer)
            saved_files_data.append({"path": temp_file_path, "name": safe_filename})
        except Exception as e:
            # Cleanup on save error
            for saved in saved_files_data:
                 if os.path.exists(saved["path"]):
                      try: os.remove(saved["path"])
                      except: pass
            raise HTTPException(status_code=500, detail=f"Could not save file: {safe_filename}. Error: {e}")
        finally:
            await file.close()

    if not saved_files_data: raise HTTPException(status_code=400, detail="No valid files saved.")

    background_tasks.add_task(background_process_files, saved_files_data, session_id)
    print(f"API: Scheduled background task for session {session_id} with {len(saved_files_data)} file(s).")

    return UploadResponse(status="processing", session_id=session_id, message="File processing started.")

