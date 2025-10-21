-- ============================================================================
-- FIX NOTE_EMBEDDINGS TABLE - CONVERT TO PROPER PGVECTOR
-- ============================================================================
-- This migration fixes the note_embeddings table to use proper vector type
-- instead of USER-DEFINED type, enabling embedding generation to work correctly.
-- ============================================================================

-- Enable pgvector extension if not already enabled
CREATE EXTENSION IF NOT EXISTS vector;

-- Drop and recreate the embedding column with proper vector type
-- Note: This will delete existing embeddings, but they will be regenerated
ALTER TABLE note_embeddings 
DROP COLUMN IF EXISTS embedding CASCADE;

ALTER TABLE note_embeddings 
ADD COLUMN embedding vector(384);

-- Create vector similarity index for fast searches
CREATE INDEX IF NOT EXISTS idx_note_embeddings_embedding 
ON note_embeddings 
USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);

-- Verify the change
DO $$ 
BEGIN
    RAISE NOTICE '';
    RAISE NOTICE '========================================';
    RAISE NOTICE '✅ note_embeddings table fixed!';
    RAISE NOTICE '========================================';
    RAISE NOTICE '';
    RAISE NOTICE 'Changes made:';
    RAISE NOTICE '  ✓ embedding column now uses vector(384) type';
    RAISE NOTICE '  ✓ Vector similarity index created';
    RAISE NOTICE '';
    RAISE NOTICE '⚠️  Note: Existing embeddings were deleted';
    RAISE NOTICE '   They will be regenerated automatically';
    RAISE NOTICE '   when notes are edited or processed.';
    RAISE NOTICE '========================================';
END $$;
