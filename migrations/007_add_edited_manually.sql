-- ============================================================================
-- ADD EDITED_MANUALLY COLUMN FOR NOTE EDITING TRACKING
-- Date: 2025-01-18
-- Description: Adds column to track whether note text was manually edited by user
-- Instructions: Run this script in Supabase SQL Editor
-- Safe to run multiple times (uses IF NOT EXISTS)
-- ============================================================================

-- Add edited_manually column (default to false)
-- TRUE = user manually edited the extracted_text
-- FALSE = extracted_text is from automated extraction only
ALTER TABLE notes 
ADD COLUMN IF NOT EXISTS edited_manually BOOLEAN DEFAULT FALSE;

-- Create index for analytics queries
CREATE INDEX IF NOT EXISTS idx_notes_edited_manually ON notes(edited_manually);

-- Add comment to document the column
COMMENT ON COLUMN notes.edited_manually IS 'TRUE if user manually edited extracted_text, FALSE if only from automated extraction';

-- Success message
DO $$ 
BEGIN
    RAISE NOTICE '';
    RAISE NOTICE '========================================';
    RAISE NOTICE '✅ edited_manually column added!';
    RAISE NOTICE '========================================';
    RAISE NOTICE '';
    RAISE NOTICE 'New column added:';
    RAISE NOTICE '  ✓ edited_manually (boolean, default: false)';
    RAISE NOTICE '';
    RAISE NOTICE '📝 Existing notes set to FALSE (not edited)';
    RAISE NOTICE '🎉 Ready for Phase 3: Note Editing!';
    RAISE NOTICE '========================================';
END $$;
