import re
from typing import List
from nltk.tokenize import sent_tokenize
import nltk
from app.core.config import settings

# Download 'punkt' sentence tokenizer model if not already downloaded
try:
    nltk.data.find('tokenizers/punkt')
except nltk.downloader.DownloadError:
    print("NLTK 'punkt' model not found. Downloading...")
    nltk.download('punkt')

def chunk_text(text: str, chunk_size: int = settings.CHUNK_SIZE, chunk_overlap: int = settings.CHUNK_OVERLAP) -> List[str]:
    """
    Splits text into chunks of a target size with overlap, trying to respect sentence boundaries.
    """
    if not text or chunk_size <= 0:
        return []
    if chunk_overlap >= chunk_size:
        chunk_overlap = int(chunk_size / 4) # Sensible default overlap

    sentences = sent_tokenize(text)
    chunks = []
    current_chunk_sentences = []
    current_length = 0

    for sentence in sentences:
        sentence_length = len(sentence)
        if current_length + sentence_length <= chunk_size:
            current_chunk_sentences.append(sentence)
            current_length += sentence_length
        else:
            # Finalize the current chunk
            if current_chunk_sentences:
                 chunks.append(" ".join(current_chunk_sentences))

            # Start new chunk, considering overlap
            # Find sentences from the end of the previous chunk to form the overlap
            overlap_sentences = []
            overlap_len = 0
            for s in reversed(current_chunk_sentences):
                s_len = len(s)
                if overlap_len + s_len <= chunk_overlap:
                    overlap_sentences.insert(0, s) # Add to beginning
                    overlap_len += s_len
                else:
                    break # Overlap is full enough

            # Start the new chunk with overlap (if any) and the current sentence
            current_chunk_sentences = overlap_sentences + [sentence]
            current_length = overlap_len + sentence_length

            # Handle cases where a single sentence is longer than chunk_size
            if not overlap_sentences and sentence_length > chunk_size:
                 # Split the long sentence itself (basic split by space near chunk_size)
                 parts = []
                 start = 0
                 while start < sentence_length:
                    end = min(start + chunk_size, sentence_length)
                    # Try to find a space to break near the end point
                    split_pos = sentence.rfind(' ', start, end)
                    if split_pos != -1 and end < sentence_length: # Found a space before the end
                        parts.append(sentence[start:split_pos].strip())
                        start = split_pos + 1
                    else: # No space or at the very end
                        parts.append(sentence[start:end].strip())
                        start = end
                 chunks.extend([p for p in parts if p]) # Add non-empty parts
                 current_chunk_sentences = [] # Reset as the long sentence was fully processed
                 current_length = 0


    # Add the last chunk if it has content
    if current_chunk_sentences:
        chunks.append(" ".join(current_chunk_sentences))

    # Filter out any potentially empty chunks
    return [chunk for chunk in chunks if chunk.strip()]

# --- Add URL Extraction ---
URL_REGEX = r'https?://[^\s<>"]+|www\.[^\s<>"]+'

def extract_urls(text: str) -> List[str]:
    """Finds potential URLs in a block of text."""
    return re.findall(URL_REGEX, text)

