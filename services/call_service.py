import os
import json
import logging
import asyncio
from typing import Optional
from datetime import datetime
from fastapi import WebSocket
from websockets.client import connect
from websockets.exceptions import WebSocketException
from services.rag_service import rag_service
from core.config import get_settings

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

settings = get_settings()

class CallSession:
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.start_time = datetime.now()
        self.status = "active"
        self.openai_ws = None

    async def connect_to_openai(self) -> bool:
        """Establish WebSocket connection to OpenAI Realtime API."""
        try:
            headers = {
                "Authorization": f"Bearer {settings.API_KEY}",
                "OpenAI-Beta": "realtime=v1"
            }
            
            self.openai_ws = await connect(
                "wss://api.openai.com/v1/realtime"
                f"?model=gpt-4o-realtime-preview-2024-12-17",
                extra_headers=headers
            )

            # Configure passive VAD
            await self.openai_ws.send(json.dumps({
                "type": "session.update",
                "session": {
                    "turn_detection": {
                        "type": "server_vad",
                        "create_response": False,
                        "interrupt_response": False
                    }
                }
            }))
            
            return True
        except WebSocketException as e:
            logger.error(f"Failed to connect to OpenAI: {str(e)}")
            return False

    async def handle_openai_message(self, message: str, client_ws: WebSocket):
        """Handle messages from OpenAI WebSocket."""
        try:
            data = json.loads(message)
            
            if data.get("type") == "response.done":
                # Extract transcript from completed response
                transcript = data.get("response", {}).get("text", "")
                if transcript:
                    # Query RAG service
                    docs = await rag_service.query_vector_store(transcript)
                    context = rag_service.format_context(docs)
                    
                    # Create prompt with context
                    prompt = (
                        "You are a helpful assistant knowledgeable about xAI's Grok model. "
                        "Use the following documentation to answer the question.\n\n"
                        f"Context:\n---\n{context}\n---\n\n"
                        f"Question: {transcript}"
                    )
                    
                    # Send prompt back to OpenAI
                    await self.openai_ws.send(json.dumps({
                        "type": "response.create",
                        "response": {
                            "conversation": "none",
                            "modalities": ["audio"],
                            "instructions": prompt
                        }
                    }))
            
            # Forward all messages to client
            await client_ws.send_text(message)
            
        except json.JSONDecodeError:
            logger.error("Failed to parse OpenAI message")
        except Exception as e:
            logger.error(f"Error handling OpenAI message: {str(e)}")

    async def close(self):
        """Close OpenAI WebSocket connection."""
        if self.openai_ws:
            try:
                await self.openai_ws.close()
            except:
                pass
        self.status = "closed"

async def handle_call(websocket: WebSocket, session_id: str):
    """Handle WebSocket-based voice call sessions with RAG integration."""
    session = CallSession(session_id)
    
    try:
        await websocket.accept()
        
        # Connect to OpenAI
        if not await session.connect_to_openai():
            await websocket.send_text(json.dumps({
                "error": "Failed to connect to voice service"
            }))
            return

        # Handle bidirectional communication
        async def forward_to_openai():
            try:
                while True:
                    data = await websocket.receive_bytes()
                    if session.openai_ws:
                        await session.openai_ws.send(data)
            except Exception as e:
                logger.error(f"Error forwarding to OpenAI: {str(e)}")

        async def receive_from_openai():
            try:
                while True:
                    if session.openai_ws:
                        message = await session.openai_ws.recv()
                        await session.handle_openai_message(message, websocket)
            except Exception as e:
                logger.error(f"Error receiving from OpenAI: {str(e)}")

        # Run both communication directions concurrently
        await asyncio.gather(
            forward_to_openai(),
            receive_from_openai()
        )

    except Exception as e:
        logger.error(f"Error in voice session {session_id}: {str(e)}")
    finally:
        await session.close()
        try:
            await websocket.close()
        except:
            pass 