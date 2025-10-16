-- ============================================================================
-- FIX get_suggested_flashcard_sets FUNCTION
-- Fixes: Returned type uuid[] does not match expected type text[]
-- ============================================================================

-- Drop the existing function completely
DROP FUNCTION IF EXISTS get_suggested_flashcard_sets(UUID);

-- Recreate with correct return type (uuid[] not text[])
CREATE OR REPLACE FUNCTION get_suggested_flashcard_sets(p_user_id UUID)
RETURNS TABLE (
    id UUID,
    title TEXT,
    description TEXT,
    total_cards INTEGER,
    source_note_ids UUID[],  -- Changed from TEXT[] to UUID[]
    created_at TIMESTAMP WITH TIME ZONE
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        fs.id,
        fs.title,
        fs.description,
        fs.total_cards,
        fs.source_note_ids::UUID[],  -- Cast to UUID[]
        fs.created_at
    FROM flashcard_sets fs
    WHERE fs.user_id = p_user_id
      AND fs.is_suggested = true
      AND (fs.is_accepted IS NULL OR fs.is_accepted = false)
    ORDER BY fs.created_at DESC
    LIMIT 10;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Success message
DO $$ 
BEGIN
    RAISE NOTICE '';
    RAISE NOTICE '========================================';
    RAISE NOTICE '✅ Fixed get_suggested_flashcard_sets function!';
    RAISE NOTICE '========================================';
    RAISE NOTICE '';
    RAISE NOTICE 'Changed source_note_ids from TEXT[] to UUID[]';
    RAISE NOTICE '';
    RAISE NOTICE '🎉 Flashcard suggestions should now work!';
    RAISE NOTICE '========================================';
END $$;
