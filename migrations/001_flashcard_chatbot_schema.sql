-- ============================================================================
-- FLASHCARD CHATBOT SCHEMA EXTENSIONS
-- Adds fields and tables required for the new flashcard chatbot feature
-- ============================================================================

-- ============================================================================
-- 1. EXTEND flashcard_sets TABLE
-- ============================================================================

-- Add generation status and verification tracking
ALTER TABLE flashcard_sets 
ADD COLUMN IF NOT EXISTS generation_status TEXT DEFAULT 'complete' 
    CHECK (generation_status IN ('pending', 'generating', 'verifying', 'partial', 'complete', 'failed'));

ALTER TABLE flashcard_sets 
ADD COLUMN IF NOT EXISTS verification_summary JSONB DEFAULT '{}'::jsonb;

ALTER TABLE flashcard_sets 
ADD COLUMN IF NOT EXISTS ai_generated BOOLEAN DEFAULT false;

ALTER TABLE flashcard_sets 
ADD COLUMN IF NOT EXISTS source_note_ids TEXT[] DEFAULT ARRAY[]::TEXT[];

-- ============================================================================
-- 2. EXTEND flashcards TABLE
-- ============================================================================

-- Add verification tracking fields
ALTER TABLE flashcards 
ADD COLUMN IF NOT EXISTS failed_verification BOOLEAN DEFAULT false;

ALTER TABLE flashcards 
ADD COLUMN IF NOT EXISTS verification_attempts INTEGER DEFAULT 0;

ALTER TABLE flashcards 
ADD COLUMN IF NOT EXISTS ai_generated BOOLEAN DEFAULT false;

ALTER TABLE flashcards 
ADD COLUMN IF NOT EXISTS source_note_id UUID REFERENCES notes(id) ON DELETE SET NULL;

ALTER TABLE flashcards 
ADD COLUMN IF NOT EXISTS explanation TEXT;

-- ============================================================================
-- 3. CREATE flashcard_chat_history TABLE
-- ============================================================================

CREATE TABLE IF NOT EXISTS flashcard_chat_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    session_id TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
    message TEXT NOT NULL,
    context JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes for chat history
CREATE INDEX IF NOT EXISTS idx_flashcard_chat_history_user_id 
    ON flashcard_chat_history(user_id);
CREATE INDEX IF NOT EXISTS idx_flashcard_chat_history_session_id 
    ON flashcard_chat_history(session_id);
CREATE INDEX IF NOT EXISTS idx_flashcard_chat_history_user_session 
    ON flashcard_chat_history(user_id, session_id);
CREATE INDEX IF NOT EXISTS idx_flashcard_chat_history_created_at 
    ON flashcard_chat_history(created_at DESC);

-- RLS policies for chat history
ALTER TABLE flashcard_chat_history ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Users can view their own chat history" ON flashcard_chat_history;
CREATE POLICY "Users can view their own chat history"
ON flashcard_chat_history FOR SELECT
USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can insert their own chat history" ON flashcard_chat_history;
CREATE POLICY "Users can insert their own chat history"
ON flashcard_chat_history FOR INSERT
WITH CHECK (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can update their own chat history" ON flashcard_chat_history;
CREATE POLICY "Users can update their own chat history"
ON flashcard_chat_history FOR UPDATE
USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can delete their own chat history" ON flashcard_chat_history;
CREATE POLICY "Users can delete their own chat history"
ON flashcard_chat_history FOR DELETE
USING (auth.uid() = user_id);

-- ============================================================================
-- 4. CREATE flashcard_generation_jobs TABLE
-- ============================================================================

CREATE TABLE IF NOT EXISTS flashcard_generation_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    job_id TEXT UNIQUE NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending' 
        CHECK (status IN ('pending', 'generating', 'verifying', 'partial', 'complete', 'failed')),
    parameters JSONB NOT NULL,
    result JSONB DEFAULT '{}'::jsonb,
    error_message TEXT,
    progress INTEGER DEFAULT 0,
    total_cards INTEGER DEFAULT 0,
    verified_cards INTEGER DEFAULT 0,
    failed_cards INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    completed_at TIMESTAMP WITH TIME ZONE
);

-- Indexes for generation jobs
CREATE INDEX IF NOT EXISTS idx_flashcard_generation_jobs_user_id 
    ON flashcard_generation_jobs(user_id);
CREATE INDEX IF NOT EXISTS idx_flashcard_generation_jobs_job_id 
    ON flashcard_generation_jobs(job_id);
CREATE INDEX IF NOT EXISTS idx_flashcard_generation_jobs_status 
    ON flashcard_generation_jobs(status);

-- RLS policies for generation jobs
ALTER TABLE flashcard_generation_jobs ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Users can view their own generation jobs" ON flashcard_generation_jobs;
CREATE POLICY "Users can view their own generation jobs"
ON flashcard_generation_jobs FOR SELECT
USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can insert their own generation jobs" ON flashcard_generation_jobs;
CREATE POLICY "Users can insert their own generation jobs"
ON flashcard_generation_jobs FOR INSERT
WITH CHECK (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can update their own generation jobs" ON flashcard_generation_jobs;
CREATE POLICY "Users can update their own generation jobs"
ON flashcard_generation_jobs FOR UPDATE
USING (auth.uid() = user_id);

-- ============================================================================
-- 5. CREATE flashcard_embeddings TABLE
-- ============================================================================

CREATE TABLE IF NOT EXISTS flashcard_embeddings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    flashcard_id UUID NOT NULL REFERENCES flashcards(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    embedding VECTOR(384),  -- Using sentence-transformers (384 dimensions)
    content_hash TEXT NOT NULL,
    model TEXT NOT NULL DEFAULT 'sentence-transformers/all-MiniLM-L6-v2',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(flashcard_id)
);

-- Indexes for flashcard embeddings
CREATE INDEX IF NOT EXISTS idx_flashcard_embeddings_flashcard_id 
    ON flashcard_embeddings(flashcard_id);
CREATE INDEX IF NOT EXISTS idx_flashcard_embeddings_user_id 
    ON flashcard_embeddings(user_id);

-- HNSW index for fast vector similarity search
CREATE INDEX IF NOT EXISTS idx_flashcard_embeddings_embedding 
    ON flashcard_embeddings USING hnsw (embedding vector_cosine_ops);

-- RLS policies for flashcard embeddings
ALTER TABLE flashcard_embeddings ENABLE ROW LEVEL SECURITY;

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
-- 6. EXTEND profiles TABLE
-- ============================================================================

-- Add grade field for difficulty inference
ALTER TABLE profiles 
ADD COLUMN IF NOT EXISTS grade TEXT;

-- Add premium status for limit enforcement
ALTER TABLE profiles 
ADD COLUMN IF NOT EXISTS is_premium BOOLEAN DEFAULT false;

-- Add generation rate limiting
ALTER TABLE profiles 
ADD COLUMN IF NOT EXISTS flashcard_sets_generated_today INTEGER DEFAULT 0;

ALTER TABLE profiles 
ADD COLUMN IF NOT EXISTS last_generation_date DATE DEFAULT CURRENT_DATE;

-- ============================================================================
-- 7. CREATE RPC FUNCTION: update_note_embeddings_dimension
-- ============================================================================

-- Update existing note_embeddings table to use 384 dimensions (if needed)
-- Only run this if you're switching from 1536 to 384 dimensions

-- DROP FUNCTION IF EXISTS update_note_embeddings_dimension();
-- 
-- CREATE OR REPLACE FUNCTION update_note_embeddings_dimension()
-- RETURNS void AS $$
-- BEGIN
--     -- Drop existing index
--     DROP INDEX IF EXISTS idx_note_embeddings_embedding;
--     
--     -- Alter column type
--     ALTER TABLE note_embeddings 
--     ALTER COLUMN embedding TYPE VECTOR(384);
--     
--     -- Recreate index
--     CREATE INDEX idx_note_embeddings_embedding 
--     ON note_embeddings USING hnsw (embedding vector_cosine_ops);
-- END;
-- $$ LANGUAGE plpgsql;

-- ============================================================================
-- 8. CREATE RPC FUNCTION: search_flashcards_by_similarity
-- ============================================================================

DROP FUNCTION IF EXISTS search_flashcards_by_similarity(JSONB, UUID, FLOAT, INT);

CREATE OR REPLACE FUNCTION search_flashcards_by_similarity(
    query_embedding JSONB,
    user_id_param UUID,
    match_threshold FLOAT DEFAULT 0.7,
    match_count INT DEFAULT 10
)
RETURNS TABLE (
    flashcard_id UUID,
    front TEXT,
    back TEXT,
    similarity FLOAT
)
LANGUAGE plpgsql
AS $$
DECLARE
    embedding_vector VECTOR(384);
BEGIN
    -- Convert JSONB to vector
    embedding_vector := query_embedding::TEXT::VECTOR(384);
    
    RETURN QUERY
    SELECT 
        f.id AS flashcard_id,
        f.front,
        f.back,
        1 - (fe.embedding <=> embedding_vector) AS similarity
    FROM flashcard_embeddings fe
    INNER JOIN flashcards f ON fe.flashcard_id = f.id
    WHERE fe.user_id = user_id_param
        AND 1 - (fe.embedding <=> embedding_vector) > match_threshold
    ORDER BY fe.embedding <=> embedding_vector
    LIMIT match_count;
END;
$$;

-- ============================================================================
-- 9. CREATE RPC FUNCTION: reset_daily_generation_count
-- ============================================================================

DROP FUNCTION IF EXISTS reset_daily_generation_count();

CREATE OR REPLACE FUNCTION reset_daily_generation_count()
RETURNS void AS $$
BEGIN
    UPDATE profiles
    SET flashcard_sets_generated_today = 0
    WHERE last_generation_date < CURRENT_DATE;
    
    UPDATE profiles
    SET last_generation_date = CURRENT_DATE
    WHERE last_generation_date < CURRENT_DATE;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- 10. CREATE RPC FUNCTION: increment_generation_count
-- ============================================================================

DROP FUNCTION IF EXISTS increment_generation_count(UUID);

CREATE OR REPLACE FUNCTION increment_generation_count(
    user_id_param UUID
)
RETURNS INTEGER AS $$
DECLARE
    new_count INTEGER;
BEGIN
    -- Reset if new day
    IF (SELECT last_generation_date FROM profiles WHERE id = user_id_param) < CURRENT_DATE THEN
        UPDATE profiles
        SET flashcard_sets_generated_today = 0,
            last_generation_date = CURRENT_DATE
        WHERE id = user_id_param;
    END IF;
    
    -- Increment count
    UPDATE profiles
    SET flashcard_sets_generated_today = flashcard_sets_generated_today + 1
    WHERE id = user_id_param
    RETURNING flashcard_sets_generated_today INTO new_count;
    
    RETURN new_count;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- VERIFICATION QUERIES
-- ============================================================================

-- Check that all tables exist
SELECT table_name 
FROM information_schema.tables 
WHERE table_schema = 'public' 
AND table_name IN ('flashcard_chat_history', 'flashcard_generation_jobs', 'flashcard_embeddings');

-- Check that all columns were added
SELECT column_name, data_type 
FROM information_schema.columns 
WHERE table_name = 'flashcard_sets' 
AND column_name IN ('generation_status', 'verification_summary', 'ai_generated');

-- Check that all RPC functions exist
SELECT routine_name 
FROM information_schema.routines 
WHERE routine_schema = 'public' 
AND routine_name IN ('search_flashcards_by_similarity', 'reset_daily_generation_count', 'increment_generation_count');
