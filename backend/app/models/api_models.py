from pydantic import BaseModel
from typing import List, Optional, Dict, Any

class UploadResponse(BaseModel):
    status: str
    session_id: Optional[str] = None
    message: Optional[str] = None

class AskRequest(BaseModel):
    question: str
    session_id: str

class AskResponse(BaseModel):
    answer: str
    type: str # 'text', 'data_table', 'data_chart', 'not_found', 'error'
    sources: List[str] = []
    data: Optional[Dict[str, Any]] = None # For table data: {"columns": [...], "rows": [[...]]}
    chart_data: Optional[Dict[str, Any]] = None # For chart data (e.g., Plotly JSON format)
    status: Optional[str] = None # Optional: To signal success/error explicitly
    message: Optional[str] = None # Optional: Error message

