from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
import uuid

class DocumentChunk(BaseModel):
    """Represents a processed piece of content, ready for indexing and retrieval."""
    session_id: str
    source: str  # Original filename or URL
    chunk_id: str = Field(default_factory=lambda: str(uuid.uuid4())) # Auto-generate unique ID
    text: str
    page: Optional[int] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    embedding: Optional[List[float]] = None # Populated during indexing

    class Config:
        frozen = True # Hashable
