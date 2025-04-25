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
from app.services.knowledge.indexer import index_content, clear_session_data, store_structured_data
from app.services.knowledge.crawler import crawl_and_chunk_url # Corrected import
from app.models.data_models import DocumentChunk

router = APIRouter()

async def background_process_files(files_data: List[Dict[str, str]], session_id: str):
    print(f"[Background Task:{session_id}] Started.")
    from app.core.state import session_status_store # Import here

    all_parsed_chunks: List[DocumentChunk] = []; extracted_urls: set[str] = set()
    crawled_chunks: List[DocumentChunk] = []; dataframes_to_store: Dict[str, pd.DataFrame] = {}
    processing_errors: List[str] = []; total_chunks_indexed = 0; final_status = "processing"

    session_status_store[session_id] = {"status": "processing", "message": "Parsing files..."}

    try:
        # --- Stage 1: Parse ---
        print(f"[Background Task:{session_id}] Stage 1: Parsing...")
        for file_data in files_data:
            file_path = file_data["path"]; original_name = file_data["name"]
            print(f"[Background Task:{session_id}]   Parsing: {original_name}")
            try:
                parsed_chunks_list, file_urls_list, df = await process_document(file_path, original_name, session_id)
                if parsed_chunks_list: all_parsed_chunks.extend(parsed_chunks_list)
                if file_urls_list: valid_urls = {url for url in file_urls_list if url.startswith(('http://', 'https://'))}; extracted_urls.update(valid_urls)
                if df is not None: dataframes_to_store[original_name] = df
            except Exception as e: error_msg = f"Parse failed {original_name}: {e}"; print(f"[Background Task:{session_id}]   ERROR: {error_msg}"); traceback.print_exc(); processing_errors.append(error_msg)
            finally:
                 if os.path.exists(file_path):
                    try: os.remove(file_path)
                    except Exception as re: print(f"[BG Task:{session_id}] Error removing {file_path}: {re}")
        print(f"[Background Task:{session_id}] Stage 1 Done. Parsed: {len(all_parsed_chunks)}, URLs: {len(extracted_urls)}, DFs: {len(dataframes_to_store)}")

        # --- Stage 1.5: Store DFs ---
        if dataframes_to_store:
            print(f"[Background Task:{session_id}] Stage 1.5: Storing DFs...")
            for fname, dataframe in dataframes_to_store.items():
                try: store_structured_data(session_id, fname, dataframe)
                except Exception as se: processing_errors.append(f"Store DF {fname}: {se}"); print(f"[BG Task:{session_id}] ERROR storing DF: {se}")

        # --- Stage 2: Crawl ---
        if extracted_urls:
            session_status_store[session_id]["message"] = f"Crawling {len(extracted_urls)} URLs..."
            print(f"[Background Task:{session_id}] Stage 2: Crawling {len(extracted_urls)} URLs...")
            url_list = sorted(list(extracted_urls))
            for i, url in enumerate(url_list):
                if i % 2 == 0: session_status_store[session_id]["message"] = f"Crawling URL {i+1}/{len(url_list)}..."
                print(f"[Background Task:{session_id}]   Crawling: {url}")
                try:
                    url_chunks = await crawl_and_chunk_url(url, session_id, depth=0)
                    if url_chunks: crawled_chunks.extend(url_chunks)
                except Exception as ce: error_msg = f"Crawl failed {url}: {ce}"; print(f"[BG Task:{session_id}]   ERROR: {error_msg}"); traceback.print_exc(); processing_errors.append(error_msg)
                await asyncio.sleep(0.1) # Be polite
            print(f"[Background Task:{session_id}] Stage 2 Done. Crawled Chunks: {len(crawled_chunks)}")
        else: print(f"[Background Task:{session_id}] Stage 2: No URLs.")

        # --- Stage 3: Index ---
        final_chunks_to_index = all_parsed_chunks + crawled_chunks
        if final_chunks_to_index:
            session_status_store[session_id]["message"] = f"Indexing {len(final_chunks_to_index)} chunks..."
            print(f"[Background Task:{session_id}] Stage 3: Indexing {len(final_chunks_to_index)} chunks...")
            try:
                index_success = await index_content(final_chunks_to_index, session_id)
                if index_success: total_chunks_indexed = len(final_chunks_to_index); print(f"[BG Task:{session_id}] Stage 3: Indexing OK."); final_status = "ready"
                else: print(f"[BG Task:{session_id}] Stage 3: Indexing ERROR."); processing_errors.append("Indexing failed."); final_status = "error"
            except Exception as ie: error_msg = f"Indexing error: {ie}"; print(f"[BG Task:{session_id}] Stage 3: ERROR: {error_msg}"); traceback.print_exc(); processing_errors.append(error_msg); final_status = "error"
        else:
             print(f"[Background Task:{session_id}] Stage 3: No content to index."); final_status = "ready" if not processing_errors else "error"

    except Exception as outer_err: error_msg = f"Unexpected task error: {outer_err}"; print(f"[BG Task:{session_id}] CRITICAL ERROR: {error_msg}"); traceback.print_exc(); processing_errors.append(error_msg); final_status = "error"

    # --- Final Status Update ---
    final_status_msg = f"Completed. Indexed Chunks: {total_chunks_indexed}."
    if processing_errors: final_status_msg += f" ERRORS: {'; '.join(processing_errors)}"; final_status = "error"
    session_status_store[session_id] = {"status": final_status, "message": final_status_msg}
    print(f"[Background Task:{session_id}] Final Status Update: {session_status_store[session_id]}")

@router.post("/", response_model=UploadResponse, status_code=202)
async def handle_file_upload(background_tasks: BackgroundTasks, files: List[UploadFile] = File(...)):
    session_id = str(uuid.uuid4()); saved_files_data = []
    if not files: raise HTTPException(status_code=400, detail="No files uploaded.")
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    await clear_session_data(session_id)
    print(f"API: Handling upload for new session: {session_id}")
    for file in files:
        if not file.filename: continue
        safe_filename = os.path.basename(file.filename)
        temp_file_path = os.path.join(settings.UPLOAD_DIR, f"{session_id}_{safe_filename}")
        try:
            print(f"API: Saving temp file: {temp_file_path}")
            with open(temp_file_path, "wb") as buffer: shutil.copyfileobj(file.file, buffer)
            saved_files_data.append({"path": temp_file_path, "name": safe_filename})
        except Exception as e:
            for saved in saved_files_data:
                 if os.path.exists(saved["path"]):
                     try:
                         os.remove(saved["path"])
                     except OSError as e_remove:
                         print(f"  - Warning: Failed to remove partially saved file {saved["path"]}: {e_remove}")
                     except Exception as e_remove_other: # Catch other potential errors
                         print(f"  - Warning: Unexpected error removing file {saved["path"]}: {e_remove_other}")
            raise HTTPException(status_code=500, detail=f"Could not save file: {safe_filename}. Error: {e}")
        finally: await file.close()
    if not saved_files_data: raise HTTPException(status_code=400, detail="No valid files saved.")
    background_tasks.add_task(background_process_files, saved_files_data, session_id)
    print(f"API: Scheduled background task for session {session_id} with {len(saved_files_data)} file(s).")
    return UploadResponse(status="processing", session_id=session_id, message="File processing started.")

