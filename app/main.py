from fastapi import FastAPI, HTTPException, Request
from contextlib import asynccontextmanager
import logging
import time

# Import components and models
from .config import logger # Use logger from config
from .log_config import setup_app_logging # Optional: Apply dictConfig
from .models import ChatRequest, ChatResponse
from .rag import load_rag_components # Function to load index/metadata
from .chatbot_logic import run_chat_logic

# Optional: Apply advanced logging configuration
# setup_app_logging()

# --- Application State --- 
# Use a dictionary to hold components loaded during lifespan
# This avoids global variables in modules like rag.py
app_state = {
    "rag_loaded": False
}

# --- Lifespan Management (Load RAG on startup) ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Application startup...")
    logger.info("Loading RAG components...")
    load_rag_components() # This function should load index/metadata
    # We might want to check if loading was successful here
    # For simplicity, rag.py logs errors if files are missing.
    # We could check a global status variable set by load_rag_components if needed.
    app_state["rag_loaded"] = True # Indicate loading attempted
    logger.info("RAG components loading attempted.")
    yield
    # Shutdown
    logger.info("Application shutdown...")
    # Cleanup resources if needed
    app_state.clear()

# --- FastAPI App ---
app = FastAPI(lifespan=lifespan)

# --- Middleware (Example: Request Timing) ---
@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = str(process_time)
    # Optional: Log request details here
    # logger.info(f"{request.method} {request.url.path} - Completed in {process_time:.4f}s - Status: {response.status_code}")
    return response

# --- API Endpoints ---

@app.get("/health", tags=["General"])
async def health_check():
    """Basic health check endpoint."""
    # Could add checks for RAG loading status, DB connection etc. later
    return {"status": "ok", "rag_loaded": app_state.get("rag_loaded", False)}

@app.post("/chat", response_model=ChatResponse, tags=["Chatbot"])
async def chat_endpoint(request: ChatRequest):
    """Handles incoming chat messages and routes to logic based on phase."""
    try:
        # Basic check if RAG is needed but not loaded for QA phase
        # Note: rag.py functions handle internal checks for loaded components
        # if request.phase == "qa" and not app_state.get("rag_loaded"): 
        #     logger.error("QA request received but RAG components not loaded.")
        #     raise HTTPException(status_code=503, detail="Service Unavailable: Knowledge base not loaded.")
        
        # Run the main chat logic
        response = run_chat_logic(request)
        
        # Check if the logic returned an error to signal to the client
        if response.error:
            # Log the error that was already set in the response by chatbot_logic
            logger.error(f"Chat logic returned error: {response.error}")
            # You might want to return a specific HTTP status code based on the error
            # For now, return 200 OK but with error detail in the response body
            # raise HTTPException(status_code=500, detail=response.error)
        
        return response

    except Exception as e:
        logger.error(f"Unhandled exception in /chat endpoint: {e}", exc_info=True)
        # Return a generic server error response
        # Avoid leaking internal details in production
        raise HTTPException(status_code=500, detail="Internal Server Error")

# --- Optional: Run directly with uvicorn for local dev ---
# if __name__ == "__main__":
#     import uvicorn
#     uvicorn.run(app, host="0.0.0.0", port=8000) 