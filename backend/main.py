from fastapi import FastAPI, APIRouter
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import os

# Corrected imports: 'app' is now a sub-directory
from app.core.config import settings
from app.api.endpoints import upload, query # Import endpoint routers

# --- Lifespan Function (optional: for setup/teardown like loading models) ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- Startup ---
    print("Starting up backend server...")
    # Ensure necessary directories exist (using paths from settings)
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    os.makedirs(settings.INDEX_DIR, exist_ok=True) # Use INDEX_DIR from config

    # TODO: Load models (e.g., embedding model) if needed on startup
    # print("Loading embedding model...")
    # app.state.embedder = load_my_embedding_model() # Example
    # print("Model loaded.")
    print("[Lifespan] Backend setup complete.")
    yield # API is ready to serve requests

    # --- Shutdown ---
    print("Shutting down backend server...")
    # Add any cleanup logic here

# --- FastAPI App Instance ---
# Pass lifespan context manager to FastAPI app
app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    lifespan=lifespan # Register lifespan manager
)

# --- API Router Setup ---
# The router imports within endpoints/upload.py etc. should still work
# as they use relative imports like 'from app.core...' which find 'app'
# because the execution context starts relative to 'backend' now.
api_router = APIRouter()
# Include routers from the 'app' sub-package
api_router.include_router(upload.router, prefix="/upload", tags=["Upload"])
api_router.include_router(query.router, prefix="/ask", tags=["Query"])

# Mount the main API router
app.include_router(api_router, prefix=settings.API_V1_STR)

# --- Root Endpoint (optional: for health check) ---
@app.get("/", tags=["Root"])
async def read_root():
    return {"message": f"Welcome to {settings.PROJECT_NAME}"}

# --- Allow CORS (Cross-Origin Resource Sharing) for Frontend ---
# IMPORTANT: Adjust origins as needed for deployment
origins = [
    "http://localhost",      # Base localhost
    "http://localhost:8501", # Default Streamlit port
    # Add the deployed frontend URL here if applicable
    # "*" # Allows all origins (use with caution)
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins, # Or ["*"] for testing
    allow_credentials=True,
    allow_methods=["*"], # Allows all methods (GET, POST, etc.)
    allow_headers=["*"], # Allows all headers
)

