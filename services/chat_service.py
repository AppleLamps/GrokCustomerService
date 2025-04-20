import logging
from typing import List, Optional, AsyncGenerator
from datetime import datetime
from pydantic import BaseModel
from openai import OpenAI, OpenAIError
from services.rag_service import rag_service
from core.config import get_settings

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

settings = get_settings()

# Initialize OpenAI client
client = OpenAI(api_key=settings.API_KEY)

class ChatMessage(BaseModel):
    role: str
    content: str
    timestamp: datetime = datetime.now()

class ChatRequest(BaseModel):
    message: str
    conversation_id: Optional[str] = None
    context: Optional[dict] = None
    stream: bool = False

class ChatResponse(BaseModel):
    response: str
    conversation_id: str
    timestamp: datetime = datetime.now()

def _create_chat_messages(context: str, query: str) -> List[dict]:
    """Create the messages list for OpenAI API."""
    return [
        {
            "role": "system",
            "content": "You are a helpful assistant knowledgeable about xAI's Grok model. "
                      "Only answer using the provided context. If the context lacks the answer, "
                      "reply with 'I couldn't find anything in the documentation.'"
        },
        {
            "role": "user",
            "content": f"Context:\n{context}\n\nQuestion: {query}"
        }
    ]

async def stream_chat_response(query: str) -> AsyncGenerator[str, None]:
    """
    Stream chat responses from OpenAI API.
    """
    try:
        # Query RAG service for relevant documents
        docs = await rag_service.query_vector_store(query)
        context = rag_service.format_context(docs)
        
        # Create messages
        messages = _create_chat_messages(context, query)
        
        # Stream response from OpenAI
        try:
            stream = client.responses.create(
                model=settings.MODEL_NAME,
                input=messages,
                stream=True
            )
            
            for event in stream:
                if event.type == "response.output_text.delta":
                    yield event.delta
                    
        except OpenAIError as e:
            logger.error(f"OpenAI API streaming error: {str(e)}")
            yield "I apologize, but I encountered an error processing your request."
            
    except Exception as e:
        logger.error(f"Error in streaming chat response: {str(e)}")
        yield "I apologize, but something went wrong processing your request."

async def handle_chat(request: ChatRequest) -> ChatResponse:
    """
    Handle incoming chat requests with RAG integration.
    Non-streaming fallback handler.
    """
    try:
        # Query RAG service for relevant documents
        docs = await rag_service.query_vector_store(request.message)
        context = rag_service.format_context(docs)
        
        # Create messages
        messages = _create_chat_messages(context, request.message)

        # Call OpenAI API
        try:
            response = client.responses.create(
                model=settings.MODEL_NAME,
                input=messages,
                stream=False
            )
            
            response_text = response.output_text
            
        except OpenAIError as e:
            logger.error(f"OpenAI API error: {str(e)}")
            response_text = "I apologize, but I encountered an error processing your request."
        
        return ChatResponse(
            response=response_text,
            conversation_id=request.conversation_id or "new_conversation"
        )

    except Exception as e:
        logger.error(f"Error handling chat request: {str(e)}")
        return ChatResponse(
            response="I apologize, but something went wrong processing your request.",
            conversation_id=request.conversation_id or "error_conversation"
        ) 