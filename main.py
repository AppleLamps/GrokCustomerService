from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from api.endpoints import router
from core.config import get_settings

app = FastAPI(
    title="QA Assistant API",
    description="A question-answering assistant with text and voice capabilities",
    version="0.1.0"
)

# CORS setup
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Consider setting specific origins in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve static frontend
app.mount("/", StaticFiles(directory="static", html=True), name="static")

# Mount API routes
app.include_router(router, prefix="/api/v1")

# Startup config validation
@app.on_event("startup")
async def startup_event():
    try:
        settings = get_settings()
        if not settings.API_KEY:
            raise ValueError("API_KEY not set in environment")
    except Exception as e:
        raise RuntimeError(f"Configuration error: {str(e)}")
