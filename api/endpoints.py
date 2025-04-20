from fastapi import APIRouter, WebSocket, Depends, HTTPException
from fastapi.responses import StreamingResponse
from services.chat_service import ChatRequest, ChatResponse, handle_chat, stream_chat_response
from services.call_service import handle_call
from core.config import Settings, get_settings
from uuid import uuid4

router = APIRouter()

@router.post("/chat", response_model=None)
async def chat_endpoint(
    request: ChatRequest,
    settings: Settings = Depends(get_settings)
):
    """
    Handle text-based chat interactions via POST requests.
    Supports both streaming and non-streaming responses.
    """
    if not request.conversation_id:
        request.conversation_id = str(uuid4())
    
    try:
        if request.stream:
            # Return streaming response
            generator = stream_chat_response(request.message)
            return StreamingResponse(
                generator,
                media_type="text/plain",
                headers={"X-Conversation-ID": request.conversation_id}
            )
        else:
            # Return regular JSON response
            response = await handle_chat(request)
            return response
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.websocket("/call/{session_id}")
async def call_endpoint(
    websocket: WebSocket,
    session_id: str,
    settings: Settings = Depends(get_settings)
):
    """
    Handle voice-based interactions via WebSocket connection.
    """
    await handle_call(websocket, session_id) 