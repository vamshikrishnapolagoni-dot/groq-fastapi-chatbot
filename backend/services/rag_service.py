import os
import uuid
from typing import List, Dict, Any, Optional
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document as LangChainDocument
from pypdf import PdfReader
import docx
import logging
from backend.config import settings

logger = logging.getLogger("rag_service")

# Initialize embeddings model globally to cache weights in memory
# Loader will pull "all-MiniLM-L6-v2" locally (it's around 90MB and highly efficient)
embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")

class RAGService:
    def __init__(self):
        self.persist_directory = settings.CHROMA_PERSIST_DIR
        os.makedirs(self.persist_directory, exist_ok=True)

    def extract_text_from_pdf(self, file_path: str) -> List[LangChainDocument]:
        """Extract text page by page from PDF to retain page citations"""
        documents = []
        try:
            reader = PdfReader(file_path)
            filename = os.path.basename(file_path)
            for page_index, page in enumerate(reader.pages):
                text = page.extract_text()
                if text and text.strip():
                    documents.append(
                        LangChainDocument(
                            page_content=text,
                            metadata={
                                "source": filename,
                                "page": page_index + 1,
                            }
                        )
                    )
            logger.info(f"Extracted {len(documents)} pages from PDF: {filename}")
        except Exception as e:
            logger.error(f"Error reading PDF {file_path}: {e}")
            raise ValueError(f"Could not parse PDF: {str(e)}")
        return documents

    def extract_text_from_docx(self, file_path: str) -> List[LangChainDocument]:
        """Extract text from DOCX document"""
        try:
            doc = docx.Document(file_path)
            filename = os.path.basename(file_path)
            full_text = []
            for paragraph in doc.paragraphs:
                if paragraph.text.strip():
                    full_text.append(paragraph.text)
            
            text_content = "\n".join(full_text)
            if not text_content.strip():
                return []
            
            return [
                LangChainDocument(
                    page_content=text_content,
                    metadata={
                        "source": filename,
                        "page": 1,
                    }
                )
            ]
        except Exception as e:
            logger.error(f"Error reading Docx {file_path}: {e}")
            raise ValueError(f"Could not parse DOCX: {str(e)}")

    def extract_text_from_txt(self, file_path: str) -> List[LangChainDocument]:
        """Extract text from standard text document"""
        try:
            filename = os.path.basename(file_path)
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
            if not content.strip():
                return []
            return [
                LangChainDocument(
                    page_content=content,
                    metadata={
                        "source": filename,
                        "page": 1,
                    }
                )
            ]
        except Exception as e:
            logger.error(f"Error reading TXT {file_path}: {e}")
            raise ValueError(f"Could not parse Text file: {str(e)}")

    def process_and_vectorize_file(self, file_path: str, chat_id: str) -> Dict[str, Any]:
        """Loads, chunks, and writes document embeddings into ChromaDB collection specific to the chat"""
        ext = os.path.splitext(file_path)[1].lower()
        if ext == ".pdf":
            raw_docs = self.extract_text_from_pdf(file_path)
        elif ext == ".docx":
            raw_docs = self.extract_text_from_docx(file_path)
        elif ext in [".txt", ".md"]:
            raw_docs = self.extract_text_from_txt(file_path)
        else:
            raise ValueError(f"Unsupported file format: {ext}")

        if not raw_docs:
            return {"chunks_created": 0, "status": "empty"}

        # Use splitter to chunk document
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200
        )
        
        # Split documents retaining metadata
        split_docs = text_splitter.split_documents(raw_docs)
        
        # Append chat ID to metadata of every split to partition queries
        for doc in split_docs:
            doc.metadata["chat_id"] = str(chat_id)

        # Write to ChromaDB
        # We index using a sub-directory or a single Chroma collection. 
        # Using a unified collection 'chat_documents' partitioned by chat_id in database queries is standard and robust.
        vector_store = Chroma(
            collection_name=f"chat_docs",
            embedding_function=embeddings,
            persist_directory=self.persist_directory
        )
        
        vector_store.add_documents(split_docs)
        logger.info(f"Successfully vectorized {len(split_docs)} chunks for chat {chat_id}")
        
        return {
            "chunks_created": len(split_docs),
            "filename": os.path.basename(file_path),
            "status": "success"
        }

    def query_rag(self, chat_id: str, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """Queries the Chroma database for chunks associated with the specific chat_id"""
        vector_store = Chroma(
            collection_name=f"chat_docs",
            embedding_function=embeddings,
            persist_directory=self.persist_directory
        )

        # Filter chunks by the current chat_id to prevent leakages
        results = vector_store.similarity_search_with_score(
            query,
            k=top_k,
            filter={"chat_id": str(chat_id)}
        )

        formatted_results = []
        for doc, score in results:
            # Score details (Chroma returns distance, lower is better. Under ~1.2 is usually relevant)
            formatted_results.append({
                "page_content": doc.page_content,
                "metadata": doc.metadata,
                "score": float(score)
            })
        
        return formatted_results

# Singleton instantiation
rag_service = RAGService()
