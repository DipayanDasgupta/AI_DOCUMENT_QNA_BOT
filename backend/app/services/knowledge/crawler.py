import trafilatura; from trafilatura.settings import use_config; from typing import Optional, List; import asyncio; import time; import traceback
from app.core.config import settings; from app.models.data_models import DocumentChunk; from app.services.text_splitter import chunk_text
async def fetch_and_extract_url_trafilatura(url: str) -> Optional[str]:
    downloaded = None; extracted_text = None; loop = asyncio.get_running_loop(); print(f"[Crawler] Fetching URL: {url}")
    try:
        downloaded = await loop.run_in_executor(None, lambda: trafilatura.fetch_url(url));
        if downloaded:
            print(f"[Crawler] Fetched {url}. Extracting..."); extracted_text = await loop.run_in_executor(None, lambda: trafilatura.extract(downloaded, url=url, include_comments=False, include_tables=False, favour_precision=False))
            if extracted_text: print(f"[Crawler] Extracted {len(extracted_text)} chars from {url}.")
            else: print(f"[Crawler] Trafilatura extracted no content from {url}")
        else: print(f"[Crawler] Fetch failed for {url}")
    except Exception as e: print(f"[Crawler] ERROR processing {url}: {e}")
    return extracted_text
async def crawl_and_chunk_url(url: str, session_id: str, depth: int = 0) -> Optional[List[DocumentChunk]]:
    if depth > settings.CRAWLER_MAX_DEPTH: return None
    main_text = await fetch_and_extract_url_trafilatura(url); parsed_chunks = []
    if main_text:
        try:
            split_chunks = chunk_text(main_text)
            for text_chunk in split_chunks: parsed_chunks.append(DocumentChunk(session_id=session_id, source=url, text=text_chunk, metadata={"parser": "trafilatura_crawler", "depth": depth}))
            print(f"[Crawler] Created {len(parsed_chunks)} chunks from {url}.")
        except Exception as chunk_err: print(f"[Crawler] ERROR chunking {url}: {chunk_err}")
    return parsed_chunks if parsed_chunks else None
