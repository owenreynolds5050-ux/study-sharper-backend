-- ============================================================================
-- FIX flashcard_sets.source_note_ids COLUMN TYPE
-- Changes from TEXT[] to UUID[] for proper type matching
-- ============================================================================

-- Change the column type from TEXT[] to UUID[]
ALTER TABLE flashcard_sets 
ALTER COLUMN source_note_ids TYPE UUID[] USING source_note_ids::UUID[];

-- Success message
DO $$ 
BEGIN
    RAISE NOTICE '';
    RAISE NOTICE '========================================';
    RAISE NOTICE '✅ Fixed flashcard_sets.source_note_ids column!';
    RAISE NOTICE '========================================';
    RAISE NOTICE '';
    RAISE NOTICE 'Changed from TEXT[] to UUID[]';
    RAISE NOTICE '';
    RAISE NOTICE '🎉 Type mismatch resolved!';
    RAISE NOTICE '========================================';
END $$;
