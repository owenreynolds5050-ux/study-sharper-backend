-- ============================================================================
-- BASE FLASHCARD SCHEMA
-- Creates the foundational flashcard tables
-- Run this FIRST before any other flashcard migrations
-- ============================================================================

-- ============================================================================
-- SECTION 1: CREATE flashcard_sets TABLE
-- ============================================================================

CREATE TABLE IF NOT EXISTS flashcard_sets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    description TEXT,
    total_cards INTEGER DEFAULT 0,
    mastered_cards INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- Extended fields for AI generation
    generation_status TEXT DEFAULT 'complete' CHECK (generation_status IN ('pending', 'generating', 'verifying', 'partial', 'complete', 'failed')),
    verification_summary JSONB DEFAULT '{}'::jsonb,
    ai_generated BOOLEAN DEFAULT false,
    source_note_ids TEXT[] DEFAULT ARRAY[]::TEXT[],
    
    -- Suggested flashcards fields
    is_suggested BOOLEAN DEFAULT false,
    is_accepted BOOLEAN DEFAULT NULL
);

-- Create indexes for flashcard_sets
CREATE INDEX IF NOT EXISTS idx_flashcard_sets_user_id ON flashcard_sets(user_id);
CREATE INDEX IF NOT EXISTS idx_flashcard_sets_created_at ON flashcard_sets(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_flashcard_sets_ai_generated ON flashcard_sets(ai_generated);
CREATE INDEX IF NOT EXISTS idx_flashcard_sets_is_suggested ON flashcard_sets(is_suggested) WHERE is_suggested = true;

-- Enable RLS
ALTER TABLE flashcard_sets ENABLE ROW LEVEL SECURITY;

-- RLS policies for flashcard_sets
DROP POLICY IF EXISTS "Users can view their own flashcard sets" ON flashcard_sets;
CREATE POLICY "Users can view their own flashcard sets"
ON flashcard_sets FOR SELECT
USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can create their own flashcard sets" ON flashcard_sets;
CREATE POLICY "Users can create their own flashcard sets"
ON flashcard_sets FOR INSERT
WITH CHECK (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can update their own flashcard sets" ON flashcard_sets;
CREATE POLICY "Users can update their own flashcard sets"
ON flashcard_sets FOR UPDATE
USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can delete their own flashcard sets" ON flashcard_sets;
CREATE POLICY "Users can delete their own flashcard sets"
ON flashcard_sets FOR DELETE
USING (auth.uid() = user_id);

-- ============================================================================
-- SECTION 2: CREATE flashcards TABLE
-- ============================================================================

CREATE TABLE IF NOT EXISTS flashcards (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    set_id UUID NOT NULL REFERENCES flashcard_sets(id) ON DELETE CASCADE,
    front TEXT NOT NULL,
    back TEXT NOT NULL,
    explanation TEXT,
    position INTEGER DEFAULT 0,
    
    -- Spaced repetition fields
    mastery_level INTEGER DEFAULT 0,
    times_reviewed INTEGER DEFAULT 0,
    times_correct INTEGER DEFAULT 0,
    times_incorrect INTEGER DEFAULT 0,
    last_reviewed_at TIMESTAMP WITH TIME ZONE,
    next_review_at TIMESTAMP WITH TIME ZONE,
    
    -- AI generation fields
    ai_generated BOOLEAN DEFAULT false,
    source_note_id UUID REFERENCES notes(id) ON DELETE SET NULL,
    failed_verification BOOLEAN DEFAULT false,
    verification_attempts INTEGER DEFAULT 0,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create indexes for flashcards
CREATE INDEX IF NOT EXISTS idx_flashcards_user_id ON flashcards(user_id);
CREATE INDEX IF NOT EXISTS idx_flashcards_set_id ON flashcards(set_id);
CREATE INDEX IF NOT EXISTS idx_flashcards_position ON flashcards(set_id, position);
CREATE INDEX IF NOT EXISTS idx_flashcards_next_review ON flashcards(user_id, next_review_at) WHERE next_review_at IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_flashcards_source_note ON flashcards(source_note_id) WHERE source_note_id IS NOT NULL;

-- Enable RLS
ALTER TABLE flashcards ENABLE ROW LEVEL SECURITY;

-- RLS policies for flashcards
DROP POLICY IF EXISTS "Users can view their own flashcards" ON flashcards;
CREATE POLICY "Users can view their own flashcards"
ON flashcards FOR SELECT
USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can create their own flashcards" ON flashcards;
CREATE POLICY "Users can create their own flashcards"
ON flashcards FOR INSERT
WITH CHECK (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can update their own flashcards" ON flashcards;
CREATE POLICY "Users can update their own flashcards"
ON flashcards FOR UPDATE
USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can delete their own flashcards" ON flashcards;
CREATE POLICY "Users can delete their own flashcards"
ON flashcards FOR DELETE
USING (auth.uid() = user_id);

-- ============================================================================
-- SECTION 3: CREATE flashcard_chat_history TABLE
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

-- Create indexes for flashcard_chat_history
CREATE INDEX IF NOT EXISTS idx_flashcard_chat_history_user_id ON flashcard_chat_history(user_id);
CREATE INDEX IF NOT EXISTS idx_flashcard_chat_history_session_id ON flashcard_chat_history(session_id);
CREATE INDEX IF NOT EXISTS idx_flashcard_chat_history_user_session ON flashcard_chat_history(user_id, session_id);
CREATE INDEX IF NOT EXISTS idx_flashcard_chat_history_created_at ON flashcard_chat_history(created_at DESC);

-- Enable RLS
ALTER TABLE flashcard_chat_history ENABLE ROW LEVEL SECURITY;

-- RLS policies for flashcard_chat_history
DROP POLICY IF EXISTS "Users can view their own chat history" ON flashcard_chat_history;
CREATE POLICY "Users can view their own chat history"
ON flashcard_chat_history FOR SELECT
USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can insert their own chat history" ON flashcard_chat_history;
CREATE POLICY "Users can insert their own chat history"
ON flashcard_chat_history FOR INSERT
WITH CHECK (auth.uid() = user_id);

-- ============================================================================
-- SECTION 4: CREATE flashcard_generation_jobs TABLE
-- ============================================================================

CREATE TABLE IF NOT EXISTS flashcard_generation_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    job_id TEXT NOT NULL UNIQUE,
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'generating', 'verifying', 'complete', 'failed')),
    parameters JSONB NOT NULL,
    progress INTEGER DEFAULT 0,
    total_cards INTEGER DEFAULT 0,
    verified_cards INTEGER DEFAULT 0,
    failed_cards INTEGER DEFAULT 0,
    result JSONB,
    error_message TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    completed_at TIMESTAMP WITH TIME ZONE
);

-- Create indexes for flashcard_generation_jobs
CREATE INDEX IF NOT EXISTS idx_flashcard_generation_jobs_user_id ON flashcard_generation_jobs(user_id);
CREATE INDEX IF NOT EXISTS idx_flashcard_generation_jobs_job_id ON flashcard_generation_jobs(job_id);
CREATE INDEX IF NOT EXISTS idx_flashcard_generation_jobs_status ON flashcard_generation_jobs(status);
CREATE INDEX IF NOT EXISTS idx_flashcard_generation_jobs_created_at ON flashcard_generation_jobs(created_at DESC);

-- Enable RLS
ALTER TABLE flashcard_generation_jobs ENABLE ROW LEVEL SECURITY;

-- RLS policies for flashcard_generation_jobs
DROP POLICY IF EXISTS "Users can view their own generation jobs" ON flashcard_generation_jobs;
CREATE POLICY "Users can view their own generation jobs"
ON flashcard_generation_jobs FOR SELECT
USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can create their own generation jobs" ON flashcard_generation_jobs;
CREATE POLICY "Users can create their own generation jobs"
ON flashcard_generation_jobs FOR INSERT
WITH CHECK (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can update their own generation jobs" ON flashcard_generation_jobs;
CREATE POLICY "Users can update their own generation jobs"
ON flashcard_generation_jobs FOR UPDATE
USING (auth.uid() = user_id);

-- ============================================================================
-- SECTION 5: CREATE HELPER FUNCTIONS
-- ============================================================================

-- Function to update total_cards count
-- Drop existing function first to avoid conflicts
DROP FUNCTION IF EXISTS update_flashcard_set_total_cards() CASCADE;

CREATE OR REPLACE FUNCTION update_flashcard_set_total_cards()
RETURNS TRIGGER AS $$
BEGIN
    UPDATE flashcard_sets
    SET total_cards = (
        SELECT COUNT(*) FROM flashcards WHERE set_id = NEW.set_id
    ),
    updated_at = NOW()
    WHERE id = NEW.set_id;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger to update total_cards on flashcard insert/delete
DROP TRIGGER IF EXISTS trigger_update_flashcard_set_total_cards ON flashcards;
CREATE TRIGGER trigger_update_flashcard_set_total_cards
AFTER INSERT OR DELETE ON flashcards
FOR EACH ROW
EXECUTE FUNCTION update_flashcard_set_total_cards();

-- Function to get suggested flashcard sets
-- Drop existing function first to avoid conflicts
DROP FUNCTION IF EXISTS get_suggested_flashcard_sets(UUID);

CREATE OR REPLACE FUNCTION get_suggested_flashcard_sets(p_user_id UUID)
RETURNS TABLE (
    id UUID,
    title TEXT,
    description TEXT,
    total_cards INTEGER,
    source_note_ids TEXT[],
    created_at TIMESTAMP WITH TIME ZONE
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        fs.id,
        fs.title,
        fs.description,
        fs.total_cards,
        fs.source_note_ids,
        fs.created_at
    FROM flashcard_sets fs
    WHERE fs.user_id = p_user_id
      AND fs.is_suggested = true
      AND (fs.is_accepted IS NULL OR fs.is_accepted = false)
    ORDER BY fs.created_at DESC
    LIMIT 10;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- ============================================================================
-- COMPLETION MESSAGE
-- ============================================================================

DO $$ 
BEGIN
    RAISE NOTICE '✅ Base flashcard schema created successfully!';
    RAISE NOTICE 'Tables created: flashcard_sets, flashcards, flashcard_chat_history, flashcard_generation_jobs';
    RAISE NOTICE 'You can now run additional flashcard migrations if needed.';
END $$;
