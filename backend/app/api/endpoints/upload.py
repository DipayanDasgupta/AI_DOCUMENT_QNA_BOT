from fastapi import APIRouter, UploadFile, File, HTTPException, BackgroundTasks
from typing import List, Dict, Any
import shutil
import os
import uuid
import asyncio
import traceback
import pandas as pd

from app.models.api_models import UploadResponse
from app.core.config import settings
from app.services.parser.main_parser import process_document
# Correctly import necessary functions from indexer and crawler
from app.services.knowledge.indexer import index_content, clear_session_data, store_structured_data
from app.services.knowledge.crawler import crawl_and_chunk_url
from app.models.data_models import DocumentChunk
# Import state store correctly within the background task function later

router = APIRouter()

# --- Revised Background Task Orchestration ---
async def background_process_files(files_data: List[Dict[str, str]], session_id: str):
    print(f"[Background Task:{session_id}] Started.")
    # Import state store inside the async function
    from app.core.state import session_status_store

    all_parsed_chunks: List[DocumentChunk] = []
    extracted_urls: set[str] = set()
    crawled_chunks: List[DocumentChunk] = []
    dataframes_to_store: Dict[str, pd.DataFrame] = {}
    processing_errors: List[str] = []
    total_chunks_indexed = 0
    final_status = "processing"

    # Set initial status
    session_status_store[session_id] = {"status": "processing", "message": "Parsing files..."}

    try:
        # --- Stage 1: Parse Uploaded Files ---
        print(f"[Background Task:{session_id}] Stage 1: Parsing uploaded files...")
        for file_data in files_data:
            file_path = file_data["path"]
            original_name = file_data["name"]
            print(f"[Background Task:{session_id}]   Parsing: {original_name}")
            # --- Start of the Corrected Inner Try/Except/Finally ---
            try:
                # Process document now returns (chunks, urls_list, Optional[dataframe])
                parsed_chunks_list, file_urls_list, df = await process_document(file_path, original_name, session_id)

                # Check and extend parsed chunks
                if parsed_chunks_list:
                    all_parsed_chunks.extend(parsed_chunks_list)
                    print(f"[Background Task:{session_id}]   Parsed {len(parsed_chunks_list)} chunks from {original_name}")

                # Check and update extracted URLs
                if file_urls_list:
                    valid_urls = {url for url in file_urls_list if url.startswith(('http://', 'https://'))}
                    extracted_urls.update(valid_urls)
                    print(f"[Background Task:{session_id}]   Extracted {len(valid_urls)} valid URLs")

                # Store DataFrame if one was generated
                if df is not None:
                    dataframes_to_store[original_name] = df
                    print(f"[Background Task:{session_id}]   Generated DataFrame for {original_name}")

            except Exception as e:
                 error_msg = f"Failed to parse {original_name}: {e}"
                 print(f"[Background Task:{session_id}]   ERROR: {error_msg}")
                 traceback.print_exc()
                 processing_errors.append(error_msg)
            finally:
                 # Clean up the temporary file after parsing attempt
                 if os.path.exists(file_path):
                    try:
                        os.remove(file_path)
                    except OSError as e_remove: # Catch specific OS error
                         print(f"[Background Task:{session_id}]   Warning: Failed to remove temp file {file_path}: {e_remove}")
                    except Exception as e_remove_other: # Catch other potential errors
                         print(f"[Background Task:{session_id}]   Warning: Unexpected error removing file {file_path}: {e_remove_other}")
            # --- End of the Corrected Inner Try/Except/Finally ---
        print(f"[Background Task:{session_id}] Stage 1 Complete. Parsed Chunks: {len(all_parsed_chunks)}, URLs: {len(extracted_urls)}, DFs: {len(dataframes_to_store)}")

        # --- Stage 1.5: Store DataFrames ---
        if dataframes_to_store:
            print(f"[Background Task:{session_id}] Stage 1.5: Storing {len(dataframes_to_store)} DataFrames...")
            for fname, dataframe in dataframes_to_store.items():
                try:
                    store_structured_data(session_id, fname, dataframe)
                except Exception as store_err:
                    processing_errors.append(f"Failed to store DataFrame for {fname}: {store_err}")
                    print(f"[Background Task:{session_id}] ERROR storing DF: {store_err}")

        # --- Stage 2: Crawl Extracted URLs ---
        if extracted_urls:
            session_status_store[session_id]["message"] = f"Crawling {len(extracted_urls)} URLs..."
            print(f"[Background Task:{session_id}] Stage 2: Crawling {len(extracted_urls)} URLs sequentially...")
            url_list = sorted(list(extracted_urls))
            for i, url in enumerate(url_list):
                if i % 2 == 0: # Update status periodically
                     session_status_store[session_id]["message"] = f"Crawling URL {i+1}/{len(url_list)}..."
                print(f"[Background Task:{session_id}]   Crawling URL {i+1}/{len(url_list)}: {url}")
                try:
                    url_chunks = await crawl_and_chunk_url(url, session_id, depth=0)
                    if url_chunks:
                        crawled_chunks.extend(url_chunks)
                        print(f"[Background Task:{session_id}]   Crawled {len(url_chunks)} chunks from {url}")
                    # else: # Optional: log if no chunks returned
                    #      print(f"[Background Task:{session_id}]   No chunks returned from crawling {url}")
                except Exception as crawl_err:
                     error_msg = f"Failed to crawl/chunk URL {url}: {crawl_err}"
                     print(f"[Background Task:{session_id}]   ERROR: {error_msg}")
                     traceback.print_exc()
                     processing_errors.append(error_msg)
                await asyncio.sleep(0.1) # Be polite
            print(f"[Background Task:{session_id}] Stage 2 Complete. Crawled Chunks: {len(crawled_chunks)}")
        else:
            print(f"[Background Task:{session_id}] Stage 2: No URLs to crawl.")


        # --- Stage 3: Index Combined Content ---
        final_chunks_to_index = all_parsed_chunks + crawled_chunks
        if final_chunks_to_index:
            session_status_store[session_id]["message"] = f"Indexing {len(final_chunks_to_index)} chunks..."
            print(f"[Background Task:{session_id}] Stage 3: Indexing {len(final_chunks_to_index)} total chunks...")
            try:
                index_success = await index_content(final_chunks_to_index, session_id)
                if index_success:
                    total_chunks_indexed = len(final_chunks_to_index)
                    print(f"[Background Task:{session_id}] Stage 3: Indexing successful.")
                    final_status = "ready"
                else:
                     print(f"[Background Task:{session_id}] Stage 3: ERROR during indexing call.")
                     processing_errors.append("Indexing failed for processed content.")
                     final_status = "error"
            except Exception as index_err:
                 error_msg = f"Critical error during indexing call: {index_err}"
                 print(f"[Background Task:{session_id}] Stage 3: ERROR: {error_msg}")
                 traceback.print_exc()
                 processing_errors.append(error_msg)
                 final_status = "error"
        else:
             print(f"[Background Task:{session_id}] Stage 3: No content chunks available to index.")
             final_status = "ready" if not processing_errors else "error"

    except Exception as outer_err:
        # Catch unexpected errors in the overall task flow
        error_msg = f"Unexpected error in background task: {outer_err}"
        print(f"[Background Task:{session_id}] CRITICAL ERROR: {error_msg}")
        traceback.print_exc()
        processing_errors.append(error_msg)
        final_status = "error"

    # --- Final Status Update ---
    final_status_msg = f"Completed. Indexed Chunks: {total_chunks_indexed}."
    if processing_errors:
        final_status_msg += f" ERRORS: {'; '.join(processing_errors)}"
        final_status = "error" # Ensure status reflects errors

    session_status_store[session_id] = {"status": final_status, "message": final_status_msg}
    print(f"[Background Task:{session_id}] Final Status Update: {session_status_store[session_id]}")


# --- API Endpoint (Remains the same) ---
@router.post("/", response_model=UploadResponse, status_code=202)
async def handle_file_upload(
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(...)
):
    session_id = str(uuid.uuid4())
    saved_files_data = []
    if not files: raise HTTPException(status_code=400, detail="No files uploaded.")

    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    await clear_session_data(session_id)
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
            for saved in saved_files_data:
                 if os.path.exists(saved["path"]):
                      try: os.remove(saved["path"])
                      except: pass # Ignore cleanup errors on primary error
            raise HTTPException(status_code=500, detail=f"Could not save file: {safe_filename}. Error: {e}")
        finally:
            await file.close() # Important: Close async file handle

    if not saved_files_data: raise HTTPException(status_code=400, detail="No valid files saved.")

    background_tasks.add_task(background_process_files, saved_files_data, session_id)
    print(f"API: Scheduled background task for session {session_id} with {len(saved_files_data)} file(s).")

    return UploadResponse(status="processing", session_id=session_id, message="File processing started.")

