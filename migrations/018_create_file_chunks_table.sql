-- Migration 018: Create file_chunks table for LangChain document processing
-- Purpose: Store extracted text chunks and their embeddings for RAG retrieval
-- Date: 2025-10-26

-- ============================================================================
-- FILE_CHUNKS TABLE
-- ============================================================================
-- Stores chunks of text extracted from uploaded files
-- Each chunk has its own embedding for semantic search

CREATE TABLE IF NOT EXISTS file_chunks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    file_id UUID NOT NULL REFERENCES files(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES auth.users(id),
    chunk_index INTEGER NOT NULL,
    content TEXT NOT NULL,
    start_position INTEGER,
    end_position INTEGER,
    embedding vector(384),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
    CONSTRAINT file_chunks_file_id_chunk_index_unique UNIQUE (file_id, chunk_index)
);

-- Index for efficient chunk retrieval by file
CREATE INDEX IF NOT EXISTS idx_file_chunks_file_id 
ON file_chunks(file_id);

-- Index for user queries
CREATE INDEX IF NOT EXISTS idx_file_chunks_user_file 
ON file_chunks(user_id, file_id);

-- Vector similarity search index (approximate nearest neighbor)
-- Using ivfflat for fast similarity search
CREATE INDEX IF NOT EXISTS idx_file_chunks_embedding 
ON file_chunks 
USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);

-- ============================================================================
-- FILE_EMBEDDINGS TABLE (ensure exists)
-- ============================================================================
-- Stores file-level embeddings (average of all chunk embeddings)
-- Used for fast file-level similarity search

CREATE TABLE IF NOT EXISTS file_embeddings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    file_id UUID NOT NULL UNIQUE REFERENCES files(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES auth.users(id),
    content_hash TEXT NOT NULL,
    model TEXT DEFAULT 'sentence-transformers/all-MiniLM-L6-v2',
    embedding vector(384),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now()
);

-- Index for file embeddings
CREATE INDEX IF NOT EXISTS idx_file_embeddings_user_id 
ON file_embeddings(user_id);

-- Vector similarity search index for file embeddings
CREATE INDEX IF NOT EXISTS idx_file_embeddings_embedding 
ON file_embeddings 
USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);

-- ============================================================================
-- UTILITY FUNCTIONS
-- ============================================================================

-- Function to search file chunks by similarity
CREATE OR REPLACE FUNCTION search_file_chunks(
    p_query_embedding vector(384),
    p_file_id UUID,
    p_user_id UUID,
    p_limit INT DEFAULT 5
)
RETURNS TABLE (
    chunk_id UUID,
    file_id UUID,
    chunk_index INT,
    content TEXT,
    similarity FLOAT
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        fc.id,
        fc.file_id,
        fc.chunk_index,
        fc.content,
        (1 - (fc.embedding <=> p_query_embedding))::FLOAT as similarity
    FROM file_chunks fc
    WHERE fc.file_id = p_file_id 
      AND fc.user_id = p_user_id
    ORDER BY fc.embedding <=> p_query_embedding
    LIMIT p_limit;
END;
$$ LANGUAGE plpgsql;

-- Function to search chunks across all user's files
CREATE OR REPLACE FUNCTION search_all_user_chunks(
    p_query_embedding vector(384),
    p_user_id UUID,
    p_limit INT DEFAULT 10
)
RETURNS TABLE (
    chunk_id UUID,
    file_id UUID,
    chunk_index INT,
    content TEXT,
    similarity FLOAT
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        fc.id,
        fc.file_id,
        fc.chunk_index,
        fc.content,
        (1 - (fc.embedding <=> p_query_embedding))::FLOAT as similarity
    FROM file_chunks fc
    WHERE fc.user_id = p_user_id
    ORDER BY fc.embedding <=> p_query_embedding
    LIMIT p_limit;
END;
$$ LANGUAGE plpgsql;

-- Function to get file statistics
CREATE OR REPLACE FUNCTION get_file_chunk_stats(p_file_id UUID)
RETURNS TABLE (
    total_chunks INT,
    total_characters BIGINT,
    average_chunk_size INT,
    created_at TIMESTAMP WITH TIME ZONE,
    updated_at TIMESTAMP WITH TIME ZONE
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        COUNT(*)::INT as total_chunks,
        SUM(LENGTH(content))::BIGINT as total_characters,
        AVG(LENGTH(content))::INT as average_chunk_size,
        MIN(fc.created_at) as created_at,
        MAX(fc.updated_at) as updated_at
    FROM file_chunks fc
    WHERE fc.file_id = p_file_id;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- COMMENTS
-- ============================================================================

COMMENT ON TABLE file_chunks IS 'Stores chunks of text extracted from uploaded files for LangChain RAG';
COMMENT ON COLUMN file_chunks.chunk_index IS 'Sequential index of chunk within file (0-based)';
COMMENT ON COLUMN file_chunks.content IS 'Text content of the chunk';
COMMENT ON COLUMN file_chunks.embedding IS '384-dimensional embedding vector for semantic search';
COMMENT ON FUNCTION search_file_chunks IS 'Search chunks within a specific file by similarity';
COMMENT ON FUNCTION search_all_user_chunks IS 'Search chunks across all user files by similarity';
COMMENT ON FUNCTION get_file_chunk_stats IS 'Get statistics about chunks in a file';