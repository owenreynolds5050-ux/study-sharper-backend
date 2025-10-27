"""
LangChain-based document processor for Study Sharper
Handles: PDF/DOCX/TXT extraction, chunking, and embedding generation
"""

import logging
import hashlib
from typing import Dict, List
from pathlib import Path

from langchain_community.document_loaders import (
    PyPDFLoader,
    Docx2txtLoader,
    TextLoader,
)
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_core.documents import Document

logger = logging.getLogger(__name__)


class LangChainProcessor:
    """Process documents: extract text, chunk, and generate embeddings."""

    def __init__(self):
        """Initialize processor with embeddings model."""
        self.embeddings = HuggingFaceEmbeddings(
            model_name="sentence-transformers/all-MiniLM-L6-v2",
            model_kwargs={"device": "cpu"},
        )
        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=100,
            separators=["\n\n", "\n", " ", ""],
        )
        logger.info("LangChainProcessor initialized with all-MiniLM-L6-v2 embeddings")

    def load_document(self, file_path: str, file_type: str) -> List[Document]:
        """
        Load document based on file type.

        Args:
            file_path: Path to the file
            file_type: File extension (pdf, docx, txt)

        Returns:
            List of LangChain Document objects

        Raises:
            ValueError: If file type is not supported
            Exception: If file loading fails
        """
        file_type = file_type.lower().strip(".")

        try:
            if file_type == "pdf":
                loader = PyPDFLoader(file_path)
            elif file_type == "docx":
                loader = Docx2txtLoader(file_path)
            elif file_type == "txt":
                loader = TextLoader(file_path)
            else:
                raise ValueError(f"Unsupported file type: {file_type}")

            docs = loader.load()
            logger.info(f"Loaded {len(docs)} pages/sections from {file_type} file")
            return docs

        except Exception as e:
            logger.error(f"Error loading {file_type} document from {file_path}: {e}")
            raise

    def extract_text(self, docs: List[Document]) -> str:
        """
        Extract and combine text from all pages/sections.

        Args:
            docs: List of LangChain Document objects

        Returns:
            Combined text content
        """
        full_text = "\n".join([doc.page_content for doc in docs])
        logger.info(f"Extracted {len(full_text)} characters from document")
        return full_text

    def chunk_text(self, text: str) -> List[Document]:
        """
        Split text into chunks with overlap.

        Args:
            text: Full text content to chunk

        Returns:
            List of LangChain Document chunks
        """
        doc = Document(page_content=text)
        chunks = self.splitter.split_documents([doc])
        logger.info(f"Split text into {len(chunks)} chunks")
        return chunks

    def generate_embeddings(self, chunks: List[Document]) -> List[List[float]]:
        """
        Generate embeddings for each chunk.

        Args:
            chunks: List of text chunks

        Returns:
            List of embedding vectors (each 384-dimensional)
        """
        embeddings_list = []
        for i, chunk in enumerate(chunks):
            embedding = self.embeddings.embed_query(chunk.page_content)
            embeddings_list.append(embedding)
            if (i + 1) % 10 == 0:
                logger.debug(f"Generated embeddings for {i + 1}/{len(chunks)} chunks")

        logger.info(f"Generated {len(embeddings_list)} embeddings")
        return embeddings_list

    def compute_content_hash(self, text: str) -> str:
        """
        Compute SHA-256 hash of text content.

        Args:
            text: Text to hash

        Returns:
            Hex-encoded SHA-256 hash
        """
        return hashlib.sha256(text.encode()).hexdigest()

    async def process_file(
        self, file_path: str, file_type: str, file_id: str, user_id: str
    ) -> Dict:
        """
        Full processing pipeline: load → extract → chunk → embed.

        Args:
            file_path: Path to uploaded file
            file_type: File type (pdf, docx, txt)
            file_id: UUID of file record
            user_id: UUID of user

        Returns:
            Dictionary with processing results:
            {
                "status": "success" | "error",
                "full_text": str,
                "chunks": List[Document],
                "embeddings": List[List[float]],
                "chunk_count": int,
                "content_hash": str,
                "error_message": str (if failed)
            }
        """
        try:
            logger.info(f"Starting file processing: file_id={file_id}, type={file_type}")

            # Step 1: Load document
            docs = self.load_document(file_path, file_type)

            # Step 2: Extract full text
            full_text = self.extract_text(docs)

            # Step 3: Split into chunks
            chunks = self.chunk_text(full_text)

            # Step 4: Generate embeddings
            embeddings = self.generate_embeddings(chunks)

            # Step 5: Compute hash
            content_hash = self.compute_content_hash(full_text)

            logger.info(
                f"File processing complete: {len(chunks)} chunks, "
                f"{len(full_text)} characters"
            )

            return {
                "status": "success",
                "full_text": full_text,
                "chunks": chunks,
                "embeddings": embeddings,
                "chunk_count": len(chunks),
                "content_hash": content_hash,
            }

        except Exception as e:
            logger.error(f"Error processing file {file_id}: {e}", exc_info=True)
            return {"status": "error", "error_message": str(e)}


# Singleton instance for use throughout the app
langchain_processor = LangChainProcessor()