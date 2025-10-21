-- Migration: Add missing file_path column to files table
-- This column is needed for file deletion to work properly

BEGIN;

-- Add file_path column (stores the path to the file in Supabase Storage)
ALTER TABLE files ADD COLUMN IF NOT EXISTS file_path text;

-- Add extracted_text column (used for text extraction from files)
ALTER TABLE files ADD COLUMN IF NOT EXISTS extracted_text text;

-- Add index for performance
CREATE INDEX IF NOT EXISTS idx_files_file_path ON files(file_path) WHERE file_path IS NOT NULL;

COMMIT;

-- Verification query (run after migration):
-- SELECT column_name FROM information_schema.columns 
-- WHERE table_name = 'files' AND column_name IN ('file_path', 'extracted_text');
