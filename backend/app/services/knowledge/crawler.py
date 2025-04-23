import requests
from bs4 import BeautifulSoup
from typing import Optional, List
from urllib.parse import urljoin, urlparse
from app.core.config import settings
from app.models.data_models import DocumentChunk
from app.services.text_splitter import chunk_text
import asyncio

async def fetch_and_parse_url(url: str, session_id: str, depth: int = 0) -> Optional[List[DocumentChunk]]:
    """Fetches content from a URL, parses text, chunks it, and returns DocumentChunks."""
    if depth > settings.CRAWLER_MAX_DEPTH:
        print(f"[Crawler] Max depth ({settings.CRAWLER_MAX_DEPTH}) reached for URL: {url}")
        return None

    print(f"[Crawler] Fetching URL (Depth {depth}): {url}")
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'} # Be a polite crawler
    parsed_chunks = []

    try:
        # Use asyncio's event loop to run the blocking requests call in a thread pool
        loop = asyncio.get_running_loop()
        response = await loop.run_in_executor(
            None, # Use default executor
            lambda: requests.get(url, headers=headers, timeout=settings.CRAWLER_TIMEOUT, allow_redirects=True)
        )
        response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)

        content_type = response.headers.get('content-type', '').lower()

        # Only parse HTML content
        if 'text/html' in content_type:
            soup = BeautifulSoup(response.content, 'html.parser') # Or 'lxml' if installed

            # Remove script and style elements
            for script_or_style in soup(['script', 'style', 'nav', 'footer', 'header', 'aside']):
                script_or_style.decompose()

            # Get text, trying common content tags first
            body = soup.find('body')
            if body:
                 # Attempt to find main content area (common patterns, may need adjustment)
                 main_content = body.find('main') or body.find('article') or body.find(role='main') or body
                 text = main_content.get_text(separator='\n', strip=True)
            else:
                 text = soup.get_text(separator='\n', strip=True) # Fallback to all text

            if text:
                print(f"[Crawler] Extracted text from {url}. Length: {len(text)}")
                split_chunks = chunk_text(text)
                for text_chunk in split_chunks:
                     parsed_chunks.append(DocumentChunk(
                         session_id=session_id,
                         source=url, # Use URL as the source
                         text=text_chunk,
                         metadata={"parser": "crawler", "depth": depth}
                     ))
            else:
                 print(f"[Crawler] No significant text extracted from {url}")
        else:
            print(f"[Crawler] Skipping non-HTML content type '{content_type}' for URL: {url}")

    except requests.exceptions.Timeout:
        print(f"[Crawler] ERROR: Timeout fetching URL: {url}")
    except requests.exceptions.RequestException as e:
        print(f"[Crawler] ERROR: Failed to fetch URL {url}: {e}")
    except Exception as e:
        print(f"[Crawler] ERROR: Failed parsing content from {url}: {e}")

    return parsed_chunks if parsed_chunks else None

