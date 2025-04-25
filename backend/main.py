# backend/main.py
from fastapi import FastAPI, APIRouter, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import os
from typing import Dict, Any # Keep Dict, Any

# Import state store
from app.core import state as app_state # Import the new state module
from app.core.config import settings
from app.api.endpoints import upload, query # Import endpoint routers
from app.api.endpoints import status as status_endpoint # Added status endpoint

# --- Lifespan Function ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- Startup ---
    print("Starting up backend server...")
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    os.makedirs(settings.INDEX_DIR, exist_ok=True)

    # Initialize stores if needed (they are global dicts, so already exist)
    # You could add logic here to load state from disk if implementing persistence
    app_state.session_status_store.clear() # Ensure store is empty on startup

    if not settings.TAVILY_API_KEY: print("WARNING: TAVILY_API_KEY not set. Web search will be disabled.")
    print("[Lifespan] Backend setup complete.")
    yield # API ready

    # --- Shutdown ---
    print("Shutting down backend server...")

# --- FastAPI App Instance ---
app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    lifespan=lifespan
)

# --- API Router Setup ---
api_router = APIRouter()
api_router.include_router(upload.router, prefix="/upload", tags=["Upload"])
api_router.include_router(query.router, prefix="/ask", tags=["Query"])
api_router.include_router(status_endpoint.router, prefix="/status", tags=["Status"]) # This import is now safe

app.include_router(api_router, prefix=settings.API_V1_STR)

# --- Root Endpoint ---
@app.get("/", tags=["Root"])
async def read_root():
    return {"message": f"Welcome to {settings.PROJECT_NAME}"}

# --- CORS Middleware ---
origins = [
    "http://localhost",
    "http://localhost:8501",
    # "*" # Uncomment for testing if needed, but be specific for production
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)