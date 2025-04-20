import os
import logging
from typing import List, Optional
from langchain_core.documents import Document
from langchain_openai import OpenAIEmbeddings
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.vectorstores.chroma import Chroma
from core.config import get_settings

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

settings = get_settings()

class RAGService:
    _instance = None
    _retriever = None

    def __init__(self):
        self.embeddings = OpenAIEmbeddings(
            model=settings.EMBEDDING_MODEL,
            openai_api_key=settings.API_KEY
        )
        
        # Ensure directories exist
        os.makedirs(settings.DOCS_DIR, exist_ok=True)
        os.makedirs(settings.VECTOR_STORE_PATH, exist_ok=True)

    @classmethod
    def get_instance(cls) -> 'RAGService':
        if cls._instance is None:
            cls._instance = RAGService()
        return cls._instance

    def _load_documents(self) -> List[Document]:
        """Load documents from the configured directory."""
        if not os.path.exists(settings.DOCS_DIR):
            logger.warning(f"Documents directory {settings.DOCS_DIR} does not exist")
            return []

        documents = []
        for filename in os.listdir(settings.DOCS_DIR):
            if filename.endswith('.txt'):
                file_path = os.path.join(settings.DOCS_DIR, filename)
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        text = f.read()
                        if text.strip():
                            documents.append(Document(page_content=text, metadata={"source": filename}))
                except Exception as e:
                    logger.error(f"Error reading file {filename}: {str(e)}")

        if not documents:
            logger.warning(f"No valid text documents found in {settings.DOCS_DIR}")
        
        return documents

    def _initialize_vector_store(self) -> Optional[Chroma]:
        """Initialize the vector store with documents if it doesn't exist."""
        # Check if vector store already exists
        if os.path.exists(settings.VECTOR_STORE_PATH) and os.listdir(settings.VECTOR_STORE_PATH):
            logger.info("Loading existing vector store...")
            return Chroma(
                persist_directory=settings.VECTOR_STORE_PATH,
                embedding_function=self.embeddings
            )

        # Load and process documents
        documents = self._load_documents()
        if not documents:
            logger.warning("No documents to initialize vector store with")
            return None

        # Split documents
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=settings.CHUNK_SIZE,
            chunk_overlap=settings.CHUNK_OVERLAP,
            length_function=len,
        )
        splits = text_splitter.split_documents(documents)

        # Create and persist vector store
        logger.info("Creating new vector store...")
        vector_store = Chroma.from_documents(
            documents=splits,
            embedding=self.embeddings,
            persist_directory=settings.VECTOR_STORE_PATH
        )
        vector_store.persist()
        return vector_store

    def get_retriever(self):
        """Get or initialize the retriever."""
        if self._retriever is None:
            vector_store = self._initialize_vector_store()
            if vector_store is not None:
                self._retriever = vector_store.as_retriever(
                    search_kwargs={"k": settings.TOP_K_RESULTS}
                )
        return self._retriever

    async def query_vector_store(self, query: str) -> List[Document]:
        """Query the vector store for relevant documents."""
        retriever = self.get_retriever()
        if retriever is None:
            logger.warning("No retriever available - vector store may be empty")
            return []
        
        try:
            return await retriever.ainvoke(query)
        except Exception as e:
            logger.error(f"Error querying vector store: {str(e)}")
            return []

    @staticmethod
    def format_context(docs: List[Document]) -> str:
        """Format retrieved documents into a context string."""
        if not docs:
            return ""
        
        formatted_docs = []
        for i, doc in enumerate(docs, 1):
            source = doc.metadata.get("source", "unknown")
            formatted_docs.append(
                f"[Document {i} from {source}]\n{doc.page_content.strip()}\n"
            )
        
        return "\n\n".join(formatted_docs)

# Initialize the RAG service on module import
rag_service = RAGService.get_instance() 