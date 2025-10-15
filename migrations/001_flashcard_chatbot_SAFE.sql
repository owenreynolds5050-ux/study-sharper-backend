-- ============================================================================
-- FLASHCARD CHATBOT SCHEMA EXTENSIONS - SAFE VERSION
-- Handles existing tables and columns gracefully
-- ============================================================================

-- ============================================================================
-- SECTION 1: EXTEND flashcard_sets TABLE
-- ============================================================================

ALTER TABLE flashcard_sets 
ADD COLUMN IF NOT EXISTS generation_status TEXT DEFAULT 'complete';

ALTER TABLE flashcard_sets 
ADD COLUMN IF NOT EXISTS verification_summary JSONB DEFAULT '{}'::jsonb;

ALTER TABLE flashcard_sets 
ADD COLUMN IF NOT EXISTS ai_generated BOOLEAN DEFAULT false;

ALTER TABLE flashcard_sets 
ADD COLUMN IF NOT EXISTS source_note_ids TEXT[] DEFAULT ARRAY[]::TEXT[];

DO $$ 
BEGIN
    ALTER TABLE flashcard_sets DROP CONSTRAINT IF EXISTS flashcard_sets_generation_status_check;
    ALTER TABLE flashcard_sets 
    ADD CONSTRAINT flashcard_sets_generation_status_check 
    CHECK (generation_status IN ('pending', 'generating', 'verifying', 'partial', 'complete', 'failed'));
EXCEPTION
    WHEN duplicate_object THEN NULL;
END $$;

-- ============================================================================
-- SECTION 2: EXTEND flashcards TABLE
-- ============================================================================

ALTER TABLE flashcards 
ADD COLUMN IF NOT EXISTS failed_verification BOOLEAN DEFAULT false;

ALTER TABLE flashcards 
ADD COLUMN IF NOT EXISTS verification_attempts INTEGER DEFAULT 0;

ALTER TABLE flashcards 
ADD COLUMN IF NOT EXISTS ai_generated BOOLEAN DEFAULT false;

ALTER TABLE flashcards 
ADD COLUMN IF NOT EXISTS source_note_id UUID;

ALTER TABLE flashcards 
ADD COLUMN IF NOT EXISTS explanation TEXT;

DO $$ 
BEGIN
    ALTER TABLE flashcards DROP CONSTRAINT IF EXISTS flashcards_source_note_id_fkey;
    ALTER TABLE flashcards 
    ADD CONSTRAINT flashcards_source_note_id_fkey 
    FOREIGN KEY (source_note_id) REFERENCES notes(id) ON DELETE SET NULL;
EXCEPTION
    WHEN duplicate_object THEN NULL;
END $$;

-- ============================================================================
-- SECTION 3: DROP AND RECREATE flashcard_chat_history TABLE
-- ============================================================================

-- Drop table if exists (to ensure clean state)
DROP TABLE IF EXISTS flashcard_chat_history CASCADE;

-- Create table
CREATE TABLE flashcard_chat_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    session_id TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
    message TEXT NOT NULL,
    context JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create indexes
CREATE INDEX idx_flashcard_chat_history_user_id 
    ON flashcard_chat_history(user_id);
    
CREATE INDEX idx_flashcard_chat_history_session_id 
    ON flashcard_chat_history(session_id);
    
CREATE INDEX idx_flashcard_chat_history_user_session 
    ON flashcard_chat_history(user_id, session_id);
    
CREATE INDEX idx_flashcard_chat_history_created_at 
    ON flashcard_chat_history(created_at DESC);

-- Enable RLS
ALTER TABLE flashcard_chat_history ENABLE ROW LEVEL SECURITY;

-- RLS policies
CREATE POLICY "Users can view their own chat history"
ON flashcard_chat_history FOR SELECT
USING (auth.uid() = user_id);

CREATE POLICY "Users can insert their own chat history"
ON flashcard_chat_history FOR INSERT
WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update their own chat history"
ON flashcard_chat_history FOR UPDATE
USING (auth.uid() = user_id);

CREATE POLICY "Users can delete their own chat history"
ON flashcard_chat_history FOR DELETE
USING (auth.uid() = user_id);

-- ============================================================================
-- SECTION 4: DROP AND RECREATE flashcard_generation_jobs TABLE
-- ============================================================================

-- Drop table if exists
DROP TABLE IF EXISTS flashcard_generation_jobs CASCADE;

-- Create table
CREATE TABLE flashcard_generation_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    job_id TEXT UNIQUE NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'generating', 'verifying', 'partial', 'complete', 'failed')),
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

-- Create indexes
CREATE INDEX idx_flashcard_generation_jobs_user_id 
    ON flashcard_generation_jobs(user_id);
    
CREATE INDEX idx_flashcard_generation_jobs_job_id 
    ON flashcard_generation_jobs(job_id);
    
CREATE INDEX idx_flashcard_generation_jobs_status 
    ON flashcard_generation_jobs(status);

-- Enable RLS
ALTER TABLE flashcard_generation_jobs ENABLE ROW LEVEL SECURITY;

-- RLS policies
CREATE POLICY "Users can view their own generation jobs"
ON flashcard_generation_jobs FOR SELECT
USING (auth.uid() = user_id);

CREATE POLICY "Users can insert their own generation jobs"
ON flashcard_generation_jobs FOR INSERT
WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update their own generation jobs"
ON flashcard_generation_jobs FOR UPDATE
USING (auth.uid() = user_id);

-- ============================================================================
-- SECTION 5: DROP AND RECREATE flashcard_embeddings TABLE
-- ============================================================================

-- Drop table if exists
DROP TABLE IF EXISTS flashcard_embeddings CASCADE;

-- Create table
CREATE TABLE flashcard_embeddings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    flashcard_id UUID NOT NULL REFERENCES flashcards(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    embedding VECTOR(384),
    content_hash TEXT NOT NULL,
    model TEXT NOT NULL DEFAULT 'sentence-transformers/all-MiniLM-L6-v2',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(flashcard_id)
);

-- Create indexes
CREATE INDEX idx_flashcard_embeddings_flashcard_id 
    ON flashcard_embeddings(flashcard_id);
    
CREATE INDEX idx_flashcard_embeddings_user_id 
    ON flashcard_embeddings(user_id);

-- HNSW index for fast vector similarity search
CREATE INDEX idx_flashcard_embeddings_embedding 
    ON flashcard_embeddings USING hnsw (embedding vector_cosine_ops);

-- Enable RLS
ALTER TABLE flashcard_embeddings ENABLE ROW LEVEL SECURITY;

-- RLS policies
CREATE POLICY "Users can view their own flashcard embeddings"
ON flashcard_embeddings FOR SELECT
USING (auth.uid() = user_id);

CREATE POLICY "Users can insert their own flashcard embeddings"
ON flashcard_embeddings FOR INSERT
WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update their own flashcard embeddings"
ON flashcard_embeddings FOR UPDATE
USING (auth.uid() = user_id);

CREATE POLICY "Users can delete their own flashcard embeddings"
ON flashcard_embeddings FOR DELETE
USING (auth.uid() = user_id);

-- ============================================================================
-- SECTION 6: EXTEND profiles TABLE
-- ============================================================================

ALTER TABLE profiles 
ADD COLUMN IF NOT EXISTS grade TEXT;

ALTER TABLE profiles 
ADD COLUMN IF NOT EXISTS is_premium BOOLEAN DEFAULT false;

ALTER TABLE profiles 
ADD COLUMN IF NOT EXISTS flashcard_sets_generated_today INTEGER DEFAULT 0;

ALTER TABLE profiles 
ADD COLUMN IF NOT EXISTS last_generation_date DATE DEFAULT CURRENT_DATE;

-- ============================================================================
-- SECTION 7: CREATE RPC FUNCTIONS
-- ============================================================================

-- Function: search_flashcards_by_similarity
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

-- Function: reset_daily_generation_count
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

-- Function: increment_generation_count
CREATE OR REPLACE FUNCTION increment_generation_count(
    user_id_param UUID
)
RETURNS INTEGER AS $$
DECLARE
    new_count INTEGER;
BEGIN
    IF (SELECT last_generation_date FROM profiles WHERE id = user_id_param) < CURRENT_DATE THEN
        UPDATE profiles
        SET flashcard_sets_generated_today = 0,
            last_generation_date = CURRENT_DATE
        WHERE id = user_id_param;
    END IF;
    
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

SELECT '=== NEW TABLES CREATED ===' AS status;
SELECT table_name 
FROM information_schema.tables 
WHERE table_schema = 'public' 
AND table_name IN ('flashcard_chat_history', 'flashcard_generation_jobs', 'flashcard_embeddings')
ORDER BY table_name;

SELECT '=== COLUMNS ADDED TO flashcard_sets ===' AS status;
SELECT column_name, data_type 
FROM information_schema.columns 
WHERE table_name = 'flashcard_sets' 
AND column_name IN ('generation_status', 'verification_summary', 'ai_generated', 'source_note_ids')
ORDER BY column_name;

SELECT '=== COLUMNS ADDED TO flashcards ===' AS status;
SELECT column_name, data_type 
FROM information_schema.columns 
WHERE table_name = 'flashcards' 
AND column_name IN ('failed_verification', 'verification_attempts', 'ai_generated', 'source_note_id', 'explanation')
ORDER BY column_name;

SELECT '=== COLUMNS ADDED TO profiles ===' AS status;
SELECT column_name, data_type 
FROM information_schema.columns 
WHERE table_name = 'profiles' 
AND column_name IN ('grade', 'is_premium', 'flashcard_sets_generated_today', 'last_generation_date')
ORDER BY column_name;

SELECT '=== RPC FUNCTIONS CREATED ===' AS status;
SELECT routine_name 
FROM information_schema.routines 
WHERE routine_schema = 'public' 
AND routine_name IN ('search_flashcards_by_similarity', 'reset_daily_generation_count', 'increment_generation_count')
ORDER BY routine_name;

SELECT '✅ MIGRATION COMPLETED SUCCESSFULLY!' AS status;
