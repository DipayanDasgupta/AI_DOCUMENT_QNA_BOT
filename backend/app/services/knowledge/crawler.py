import trafilatura
from typing import Optional, List
import asyncio

from app.core.config import settings
from app.models.data_models import DocumentChunk
from app.services.text_splitter import chunk_text # Still use our chunker

async def fetch_and_parse_url(url: str, session_id: str, depth: int = 0) -> Optional[List[DocumentChunk]]:
    """
    Fetches content from a URL using Trafilatura, extracts main text,
    chunks it, and returns DocumentChunks.
    """
    if depth > settings.CRAWLER_MAX_DEPTH:
        print(f"[Crawler] Max depth ({settings.CRAWLER_MAX_DEPTH}) reached for URL: {url}")
        return None

    print(f"[Crawler] Fetching and extracting URL (Depth {depth}) using Trafilatura: {url}")
    parsed_chunks = []

    try:
        # Use asyncio's event loop to run the blocking Trafilatura fetch/extract
        loop = asyncio.get_running_loop()

        # 1. Fetch the URL (Trafilatura handles redirects, basic fetching)
        # Consider adding timeout configuration to fetch_url if needed
        downloaded = await loop.run_in_executor(None, lambda: trafilatura.fetch_url(url))

        if downloaded is None:
            print(f"[Crawler] ERROR: Trafilatura failed to fetch URL: {url}")
            return None

        # 2. Extract main text content
        # include_comments=False, include_tables=True (optional, default is False)
        # target_language='en' (optional, helps focus extraction)
        extracted_text = await loop.run_in_executor(None, lambda: trafilatura.extract(
            downloaded,
            include_comments=False,
            include_tables=False, # Usually ignore tables for general text Q&A
            output_format='txt', # Ensure plain text output
            # url=url # Providing URL might help extraction
        ))

        if extracted_text and extracted_text.strip():
            print(f"[Crawler] Extracted text from {url} using Trafilatura. Length: {len(extracted_text)}")
            # 3. Chunk the extracted text
            split_chunks = chunk_text(extracted_text)
            for text_chunk in split_chunks:
                 parsed_chunks.append(DocumentChunk(
                     session_id=session_id,
                     source=url, # Use URL as the source
                     text=text_chunk,
                     metadata={"parser": "trafilatura_crawler", "depth": depth}
                 ))
            print(f"[Crawler] Created {len(split_chunks)} chunks from crawled content.")
        else:
             print(f"[Crawler] Trafilatura extracted no significant text from {url}")

    except Exception as e:
        # Catch potential errors during fetch or extract
        print(f"[Crawler] ERROR: Failed processing URL {url} with Trafilatura: {e}")
        import traceback
        traceback.print_exc() # Log full traceback

    return parsed_chunks if parsed_chunks else None

