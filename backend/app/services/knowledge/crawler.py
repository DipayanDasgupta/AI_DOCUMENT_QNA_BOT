import trafilatura
from trafilatura.settings import use_config
from typing import Optional, List
import asyncio
import time
import traceback

from app.core.config import settings
from app.models.data_models import DocumentChunk
from app.services.text_splitter import chunk_text

# config = use_config(); config.set("DEFAULT", "TIMEOUT", "15") # Example config

async def fetch_and_extract_url_trafilatura(url: str, retries: int = 2) -> Optional[str]:
    """Fetches URL content and extracts main text using Trafilatura with retries."""
    downloaded = None
    extracted_text = None
    loop = asyncio.get_running_loop()
    last_exception = None

    for attempt in range(retries + 1):
        print(f"[Crawler] Attempt {attempt+1}/{retries+1} Fetching URL: {url}")
        try:
            # Run synchronous fetch in executor
            downloaded = await loop.run_in_executor(None, lambda: trafilatura.fetch_url(url))

            if downloaded:
                print(f"[Crawler] Fetched {url}. Extracting...")
                # Run synchronous extract in executor
                extracted_text = await loop.run_in_executor(
                    None, lambda: trafilatura.extract(downloaded, url=url, include_comments=False, include_tables=False)
                )
                if extracted_text:
                    print(f"[Crawler] Extracted {len(extracted_text)} chars from {url}.")
                    return extracted_text # SUCCESS - Return text
                else:
                    print(f"[Crawler] Trafilatura extracted no content from {url}.")
                    # Treat as failure for retry purposes if needed, or return None now
                    # Let's return None here as extraction failed.
                    return None
            else:
                print(f"[Crawler] Trafilatura fetch returned None for {url}.")
                last_exception = ValueError("fetch_url returned None") # Treat as error

        except Exception as e:
            last_exception = e
            print(f"[Crawler] Attempt {attempt+1} ERROR for {url}: {e}")

        # If not successful, wait before retrying (except for the last attempt)
        if attempt < retries:
            wait_time = 1 * (attempt + 1) # Simple linear backoff
            print(f"[Crawler] Waiting {wait_time}s before retry...")
            await asyncio.sleep(wait_time)

    # If loop finishes without success
    print(f"[Crawler] All {retries+1} attempts failed for URL {url}. Last error: {last_exception}")
    return None # Return None after all retries fail

async def crawl_and_chunk_url(url: str, session_id: str, depth: int = 0) -> Optional[List[DocumentChunk]]:
    """Fetches, extracts text using Trafilatura (with retries), chunks it, returns DocumentChunks."""
    if depth > settings.CRAWLER_MAX_DEPTH: return None

    # Call the fetch function which now includes retries
    main_text = await fetch_and_extract_url_trafilatura(url)
    parsed_chunks = []

    if main_text:
        try:
            split_chunks = chunk_text(main_text)
            for text_chunk in split_chunks:
                 parsed_chunks.append(DocumentChunk(session_id=session_id, source=url, text=text_chunk, metadata={"parser": "trafilatura_crawler", "depth": depth}))
            print(f"[Crawler] Created {len(parsed_chunks)} chunks from {url}.")
        except Exception as chunk_err: print(f"[Crawler] ERROR chunking crawled text from {url}: {chunk_err}")
    # else: print(f"[Crawler] No text available to chunk for {url}.") # Already logged in fetch func

    return parsed_chunks if parsed_chunks else None

