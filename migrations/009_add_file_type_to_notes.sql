-- ============================================================================
-- ADD file_type COLUMN TO NOTES TABLE
-- Ensures manual notes and file uploads can record their type
-- ============================================================================

ALTER TABLE notes
ADD COLUMN IF NOT EXISTS file_type TEXT DEFAULT 'md';

-- Backfill existing rows to the default where NULL
UPDATE notes
SET file_type = 'md'
WHERE file_type IS NULL;

-- Optional index to speed up queries filtering by file type
CREATE INDEX IF NOT EXISTS idx_notes_file_type ON notes(file_type);

-- Completion notice
DO $$
BEGIN
    RAISE NOTICE '✅ Added file_type column to notes table (default md).';
END $$;
