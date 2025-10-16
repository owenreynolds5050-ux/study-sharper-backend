-- ============================================================================
-- NOTE EMBEDDINGS & VECTOR SEARCH FUNCTIONS
-- Required for AI chat and RAG features
-- ============================================================================

-- ============================================================================
-- SECTION 1: CREATE note_embeddings TABLE (if not exists)
-- ============================================================================

DO $$ 
BEGIN
    IF NOT EXISTS (SELECT FROM pg_tables WHERE schemaname = 'public' AND tablename = 'note_embeddings') THEN
        CREATE TABLE note_embeddings (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            note_id UUID NOT NULL REFERENCES notes(id) ON DELETE CASCADE,
            user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
            embedding vector(384),  -- For sentence-transformers/all-MiniLM-L6-v2
            content_hash TEXT NOT NULL,
            model TEXT NOT NULL,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            UNIQUE(note_id)
        );
        
        RAISE NOTICE '✅ Created table: note_embeddings';
    ELSE
        RAISE NOTICE '⏭️  Table note_embeddings already exists, skipping...';
    END IF;
END $$;

-- Create indexes for note_embeddings
CREATE INDEX IF NOT EXISTS idx_note_embeddings_note_id ON note_embeddings(note_id);
CREATE INDEX IF NOT EXISTS idx_note_embeddings_user_id ON note_embeddings(user_id);

-- Create vector similarity index (using ivfflat for performance)
-- This requires pgvector extension
DO $$
BEGIN
    -- Try to create the index, skip if it already exists
    IF NOT EXISTS (
        SELECT 1 FROM pg_indexes 
        WHERE schemaname = 'public' 
        AND tablename = 'note_embeddings' 
        AND indexname = 'idx_note_embeddings_embedding'
    ) THEN
        CREATE INDEX idx_note_embeddings_embedding 
        ON note_embeddings 
        USING ivfflat (embedding vector_cosine_ops)
        WITH (lists = 100);
        
        RAISE NOTICE '✅ Created vector index on note_embeddings';
    ELSE
        RAISE NOTICE '⏭️  Vector index already exists, skipping...';
    END IF;
EXCEPTION
    WHEN undefined_object THEN
        RAISE NOTICE '⚠️  pgvector extension not available, creating basic index instead';
        CREATE INDEX IF NOT EXISTS idx_note_embeddings_embedding_basic ON note_embeddings(note_id);
END $$;

-- Enable RLS
ALTER TABLE note_embeddings ENABLE ROW LEVEL SECURITY;

-- RLS policies for note_embeddings
DROP POLICY IF EXISTS "Users can view their own note embeddings" ON note_embeddings;
CREATE POLICY "Users can view their own note embeddings"
ON note_embeddings FOR SELECT
USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can insert their own note embeddings" ON note_embeddings;
CREATE POLICY "Users can insert their own note embeddings"
ON note_embeddings FOR INSERT
WITH CHECK (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can update their own note embeddings" ON note_embeddings;
CREATE POLICY "Users can update their own note embeddings"
ON note_embeddings FOR UPDATE
USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can delete their own note embeddings" ON note_embeddings;
CREATE POLICY "Users can delete their own note embeddings"
ON note_embeddings FOR DELETE
USING (auth.uid() = user_id);

-- ============================================================================
-- SECTION 2: CREATE VECTOR SEARCH FUNCTION
-- ============================================================================

-- Drop existing function if it exists
DROP FUNCTION IF EXISTS search_similar_notes(vector, UUID, FLOAT, INT);
DROP FUNCTION IF EXISTS search_similar_notes(TEXT, UUID, FLOAT, INT);
DROP FUNCTION IF EXISTS search_similar_notes(JSONB, UUID, FLOAT, INT);

-- Create the search function
-- Note: This function expects the embedding as a JSONB array (e.g., "[0.1, 0.2, ...]")
CREATE OR REPLACE FUNCTION search_similar_notes(
    query_embedding JSONB,
    user_id_param UUID,
    match_threshold FLOAT DEFAULT 0.5,
    match_count INT DEFAULT 10
)
RETURNS TABLE (
    note_id UUID,
    title TEXT,
    content TEXT,
    extracted_text TEXT,
    subject TEXT,
    folder_id UUID,
    similarity FLOAT,
    created_at TIMESTAMP WITH TIME ZONE
) AS $$
DECLARE
    embedding_vector vector(384);
BEGIN
    -- Convert JSONB array to vector
    -- The query_embedding should be a JSONB array like [0.1, 0.2, 0.3, ...]
    BEGIN
        embedding_vector := query_embedding::text::vector(384);
    EXCEPTION WHEN OTHERS THEN
        RAISE NOTICE 'Error converting embedding: %', SQLERRM;
        RETURN;
    END;
    
    -- Perform similarity search
    RETURN QUERY
    SELECT 
        n.id as note_id,
        n.title,
        n.content,
        n.extracted_text,
        n.subject,
        n.folder_id,
        1 - (ne.embedding <=> embedding_vector) as similarity,
        n.created_at
    FROM note_embeddings ne
    JOIN notes n ON n.id = ne.note_id
    WHERE ne.user_id = user_id_param
      AND 1 - (ne.embedding <=> embedding_vector) >= match_threshold
    ORDER BY ne.embedding <=> embedding_vector
    LIMIT match_count;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- ============================================================================
-- SECTION 3: CREATE FLASHCARD EMBEDDINGS TABLE (if not exists)
-- ============================================================================

DO $$ 
BEGIN
    IF NOT EXISTS (SELECT FROM pg_tables WHERE schemaname = 'public' AND tablename = 'flashcard_embeddings') THEN
        CREATE TABLE flashcard_embeddings (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            flashcard_id UUID NOT NULL REFERENCES flashcards(id) ON DELETE CASCADE,
            user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
            embedding vector(384),
            content_hash TEXT NOT NULL,
            model TEXT NOT NULL,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            UNIQUE(flashcard_id)
        );
        
        RAISE NOTICE '✅ Created table: flashcard_embeddings';
    ELSE
        RAISE NOTICE '⏭️  Table flashcard_embeddings already exists, skipping...';
    END IF;
END $$;

-- Create indexes for flashcard_embeddings
CREATE INDEX IF NOT EXISTS idx_flashcard_embeddings_flashcard_id ON flashcard_embeddings(flashcard_id);
CREATE INDEX IF NOT EXISTS idx_flashcard_embeddings_user_id ON flashcard_embeddings(user_id);

-- Enable RLS
ALTER TABLE flashcard_embeddings ENABLE ROW LEVEL SECURITY;

-- RLS policies for flashcard_embeddings
DROP POLICY IF EXISTS "Users can view their own flashcard embeddings" ON flashcard_embeddings;
CREATE POLICY "Users can view their own flashcard embeddings"
ON flashcard_embeddings FOR SELECT
USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can insert their own flashcard embeddings" ON flashcard_embeddings;
CREATE POLICY "Users can insert their own flashcard embeddings"
ON flashcard_embeddings FOR INSERT
WITH CHECK (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can update their own flashcard embeddings" ON flashcard_embeddings;
CREATE POLICY "Users can update their own flashcard embeddings"
ON flashcard_embeddings FOR UPDATE
USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can delete their own flashcard embeddings" ON flashcard_embeddings;
CREATE POLICY "Users can delete their own flashcard embeddings"
ON flashcard_embeddings FOR DELETE
USING (auth.uid() = user_id);

-- ============================================================================
-- COMPLETION MESSAGE
-- ============================================================================

DO $$ 
BEGIN
    RAISE NOTICE '';
    RAISE NOTICE '========================================';
    RAISE NOTICE '✅ Note embeddings & search setup complete!';
    RAISE NOTICE '========================================';
    RAISE NOTICE '';
    RAISE NOTICE 'Tables ready:';
    RAISE NOTICE '  ✓ note_embeddings';
    RAISE NOTICE '  ✓ flashcard_embeddings';
    RAISE NOTICE '';
    RAISE NOTICE 'Functions created:';
    RAISE NOTICE '  ✓ search_similar_notes()';
    RAISE NOTICE '';
    RAISE NOTICE '🎉 AI chat and RAG features are now ready!';
    RAISE NOTICE '========================================';
END $$;
