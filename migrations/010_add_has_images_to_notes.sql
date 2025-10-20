-- ============================================================================
-- ADD has_images COLUMN TO NOTES TABLE
-- Ensures queries expecting has_images column do not fail
-- ============================================================================

ALTER TABLE notes
ADD COLUMN IF NOT EXISTS has_images BOOLEAN DEFAULT FALSE;

-- Backfill existing rows to the default where NULL
UPDATE notes
SET has_images = FALSE
WHERE has_images IS NULL;

-- Optional index to speed up queries filtering by has_images
CREATE INDEX IF NOT EXISTS idx_notes_has_images ON notes(has_images);

-- Completion notice
DO $$
BEGIN
    RAISE NOTICE '✅ Added has_images column to notes table (default FALSE).';
END $$;
