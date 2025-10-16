-- ============================================================================
-- ADD MISSING COLUMNS TO NOTES TABLE
-- Fixes: column notes.subject does not exist
-- ============================================================================

-- Add subject column if it doesn't exist
ALTER TABLE notes 
ADD COLUMN IF NOT EXISTS subject TEXT;

-- Add other commonly used columns that might be missing
ALTER TABLE notes 
ADD COLUMN IF NOT EXISTS tags TEXT[] DEFAULT ARRAY[]::TEXT[];

ALTER TABLE notes 
ADD COLUMN IF NOT EXISTS folder_id UUID REFERENCES note_folders(id) ON DELETE SET NULL;

ALTER TABLE notes 
ADD COLUMN IF NOT EXISTS file_path TEXT;

ALTER TABLE notes 
ADD COLUMN IF NOT EXISTS extracted_text TEXT;

ALTER TABLE notes 
ADD COLUMN IF NOT EXISTS summary TEXT;

ALTER TABLE notes 
ADD COLUMN IF NOT EXISTS transcription TEXT;

-- Create indexes for better performance
CREATE INDEX IF NOT EXISTS idx_notes_subject ON notes(subject);
CREATE INDEX IF NOT EXISTS idx_notes_folder_id ON notes(folder_id);
CREATE INDEX IF NOT EXISTS idx_notes_user_id ON notes(user_id);
CREATE INDEX IF NOT EXISTS idx_notes_created_at ON notes(created_at DESC);

-- Success message
DO $$ 
BEGIN
    RAISE NOTICE '';
    RAISE NOTICE '========================================';
    RAISE NOTICE '✅ Notes table columns added!';
    RAISE NOTICE '========================================';
    RAISE NOTICE '';
    RAISE NOTICE 'Columns added:';
    RAISE NOTICE '  ✓ subject';
    RAISE NOTICE '  ✓ tags';
    RAISE NOTICE '  ✓ folder_id';
    RAISE NOTICE '  ✓ file_path';
    RAISE NOTICE '  ✓ extracted_text';
    RAISE NOTICE '  ✓ summary';
    RAISE NOTICE '  ✓ transcription';
    RAISE NOTICE '';
    RAISE NOTICE '🎉 AI chat should now work!';
    RAISE NOTICE '========================================';
END $$;
