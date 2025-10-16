-- Phase 2: Context Gathering Tables
-- Run this migration in Supabase SQL Editor

-- ============================================================================
-- 1. User Agent Preferences Table
-- ============================================================================
CREATE TABLE IF NOT EXISTS user_agent_preferences (
    user_id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    preferred_detail_level TEXT DEFAULT 'detailed' CHECK (preferred_detail_level IN ('brief', 'detailed', 'comprehensive')),
    preferred_difficulty TEXT DEFAULT 'adaptive' CHECK (preferred_difficulty IN ('easy', 'medium', 'hard', 'adaptive')),
    auto_context_gathering BOOLEAN DEFAULT true,
    show_agent_progress BOOLEAN DEFAULT true,
    preferences JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Add RLS policies
ALTER TABLE user_agent_preferences ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view own preferences"
    ON user_agent_preferences FOR SELECT
    USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own preferences"
    ON user_agent_preferences FOR INSERT
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update own preferences"
    ON user_agent_preferences FOR UPDATE
    USING (auth.uid() = user_id);

-- ============================================================================
-- 2. Conversation Sessions Table
-- ============================================================================
CREATE TABLE IF NOT EXISTS conversation_sessions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    session_type TEXT DEFAULT 'chat' CHECK (session_type IN ('chat', 'flashcard', 'quiz', 'study_plan')),
    context_data JSONB DEFAULT '{}',
    started_at TIMESTAMPTZ DEFAULT NOW(),
    last_activity TIMESTAMPTZ DEFAULT NOW(),
    ended_at TIMESTAMPTZ,
    CONSTRAINT valid_session_times CHECK (ended_at IS NULL OR ended_at >= started_at)
);

-- Add RLS policies
ALTER TABLE conversation_sessions ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view own sessions"
    ON conversation_sessions FOR SELECT
    USING (auth.uid() = user_id);

CREATE POLICY "Users can create own sessions"
    ON conversation_sessions FOR INSERT
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update own sessions"
    ON conversation_sessions FOR UPDATE
    USING (auth.uid() = user_id);

-- ============================================================================
-- 3. Conversation Messages Table
-- ============================================================================
CREATE TABLE IF NOT EXISTS conversation_messages (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id UUID NOT NULL REFERENCES conversation_sessions(id) ON DELETE CASCADE,
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
    content TEXT NOT NULL,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Add RLS policies
ALTER TABLE conversation_messages ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view messages from own sessions"
    ON conversation_messages FOR SELECT
    USING (
        EXISTS (
            SELECT 1 FROM conversation_sessions
            WHERE conversation_sessions.id = conversation_messages.session_id
            AND conversation_sessions.user_id = auth.uid()
        )
    );

CREATE POLICY "Users can insert messages to own sessions"
    ON conversation_messages FOR INSERT
    WITH CHECK (
        EXISTS (
            SELECT 1 FROM conversation_sessions
            WHERE conversation_sessions.id = conversation_messages.session_id
            AND conversation_sessions.user_id = auth.uid()
        )
    );

-- ============================================================================
-- 4. Flashcard Sessions Table (if not exists)
-- ============================================================================
CREATE TABLE IF NOT EXISTS flashcard_sessions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    cards_studied INTEGER DEFAULT 0,
    correct_count INTEGER DEFAULT 0,
    session_duration_minutes INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT valid_counts CHECK (correct_count <= cards_studied)
);

-- Add RLS policies
ALTER TABLE flashcard_sessions ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view own flashcard sessions"
    ON flashcard_sessions FOR SELECT
    USING (auth.uid() = user_id);

CREATE POLICY "Users can create own flashcard sessions"
    ON flashcard_sessions FOR INSERT
    WITH CHECK (auth.uid() = user_id);

-- ============================================================================
-- 5. Indexes for Performance
-- ============================================================================

-- Conversation messages by session and time
CREATE INDEX IF NOT EXISTS idx_conversation_messages_session 
    ON conversation_messages(session_id, created_at DESC);

-- Conversation sessions by user and activity
CREATE INDEX IF NOT EXISTS idx_conversation_sessions_user 
    ON conversation_sessions(user_id, last_activity DESC);

-- Flashcard sessions by user and time
CREATE INDEX IF NOT EXISTS idx_flashcard_sessions_user 
    ON flashcard_sessions(user_id, created_at DESC);

-- User preferences lookup
CREATE INDEX IF NOT EXISTS idx_user_agent_preferences_user 
    ON user_agent_preferences(user_id);

-- ============================================================================
-- 6. Updated_at Trigger Function
-- ============================================================================

-- Create trigger function if it doesn't exist
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Add trigger to user_agent_preferences
DROP TRIGGER IF EXISTS update_user_agent_preferences_updated_at ON user_agent_preferences;
CREATE TRIGGER update_user_agent_preferences_updated_at
    BEFORE UPDATE ON user_agent_preferences
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- ============================================================================
-- 7. Helper Functions
-- ============================================================================

-- Function to get or create user preferences
CREATE OR REPLACE FUNCTION get_or_create_user_preferences(p_user_id UUID)
RETURNS user_agent_preferences AS $$
DECLARE
    v_prefs user_agent_preferences;
BEGIN
    -- Try to get existing preferences
    SELECT * INTO v_prefs
    FROM user_agent_preferences
    WHERE user_id = p_user_id;
    
    -- If not found, create default preferences
    IF NOT FOUND THEN
        INSERT INTO user_agent_preferences (user_id)
        VALUES (p_user_id)
        RETURNING * INTO v_prefs;
    END IF;
    
    RETURN v_prefs;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Function to end a conversation session
CREATE OR REPLACE FUNCTION end_conversation_session(p_session_id UUID)
RETURNS VOID AS $$
BEGIN
    UPDATE conversation_sessions
    SET ended_at = NOW()
    WHERE id = p_session_id
    AND ended_at IS NULL;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- ============================================================================
-- 8. Verification Queries
-- ============================================================================

-- Run these to verify the migration succeeded:

-- Check tables exist
SELECT table_name 
FROM information_schema.tables 
WHERE table_schema = 'public' 
AND table_name IN (
    'user_agent_preferences',
    'conversation_sessions',
    'conversation_messages',
    'flashcard_sessions'
);

-- Check RLS is enabled
SELECT tablename, rowsecurity 
FROM pg_tables 
WHERE schemaname = 'public' 
AND tablename IN (
    'user_agent_preferences',
    'conversation_sessions',
    'conversation_messages',
    'flashcard_sessions'
);

-- Check indexes exist
SELECT indexname 
FROM pg_indexes 
WHERE schemaname = 'public' 
AND tablename IN (
    'user_agent_preferences',
    'conversation_sessions',
    'conversation_messages',
    'flashcard_sessions'
);

-- ============================================================================
-- NOTES:
-- - All tables have RLS enabled for security
-- - Indexes are added for common query patterns
-- - Helper functions simplify common operations
-- - Constraints ensure data integrity
-- ============================================================================
