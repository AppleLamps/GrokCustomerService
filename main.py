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

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust this in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
app.mount("/", StaticFiles(directory="static", html=True), name="static")

# Include the router with prefix
app.include_router(router, prefix="/api/v1")

@app.on_event("startup")
async def startup_event():
    """Validate configuration on startup"""
    try:
        settings = get_settings()
        if not settings.API_KEY:
            raise ValueError("API_KEY not set in environment")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Configuration error: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True) 