-- Migration: Consolidate notes system into files system
-- This migration replaces the notes table with the files table
-- and ensures all functionality is preserved

-- ============================================================================
-- STEP 1: Add missing columns to files table
-- ============================================================================

-- Add columns that exist in notes but not in files
ALTER TABLE files ADD COLUMN IF NOT EXISTS summary text;
ALTER TABLE files ADD COLUMN IF NOT EXISTS tags text[] DEFAULT '{}';
ALTER TABLE files ADD COLUMN IF NOT EXISTS transcription text;
ALTER TABLE files ADD COLUMN IF NOT EXISTS ocr_processed boolean DEFAULT false;
ALTER TABLE files ADD COLUMN IF NOT EXISTS edited_manually boolean DEFAULT false;
ALTER TABLE files ADD COLUMN IF NOT EXISTS subject text;

-- ============================================================================
-- STEP 2: Migrate data from notes to files
-- ============================================================================

-- Insert all notes into files table (if there are any existing notes not already in files)
INSERT INTO files (
    id,
    user_id,
    folder_id,
    title,
    content,
    original_filename,
    file_type,
    file_size_bytes,
    processing_status,
    extraction_method,
    error_message,
    has_images,
    summary,
    tags,
    transcription,
    ocr_processed,
    edited_manually,
    subject,
    created_at,
    updated_at,
    last_accessed_at
)
SELECT 
    n.id,
    n.user_id,
    n.folder_id,
    n.title,
    n.content,
    COALESCE(n.original_filename, n.title || '.md'),
    COALESCE(n.file_type, 'md'),
    n.file_size_bytes,
    CAST(n.processing_status AS text),
    n.extraction_method,
    n.error_message,
    n.has_images,
    n.summary,
    n.tags,
    n.transcription,
    n.ocr_processed,
    n.edited_manually,
    n.subject,
    n.created_at,
    n.updated_at,
    n.updated_at
FROM notes n
WHERE n.id NOT IN (SELECT id FROM files)
ON CONFLICT (id) DO NOTHING;

-- ============================================================================
-- STEP 3: Update foreign key references from notes to files
-- ============================================================================

-- Update flashcards table
-- First, check if the foreign key constraint exists and drop it
DO $$ 
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.table_constraints 
        WHERE constraint_name = 'flashcards_source_note_id_fkey'
        AND table_name = 'flashcards'
    ) THEN
        ALTER TABLE flashcards DROP CONSTRAINT flashcards_source_note_id_fkey;
    END IF;
END $$;

-- Rename the column to source_file_id
ALTER TABLE flashcards RENAME COLUMN source_note_id TO source_file_id;

-- Add new foreign key constraint pointing to files
ALTER TABLE flashcards 
ADD CONSTRAINT flashcards_source_file_id_fkey 
FOREIGN KEY (source_file_id) REFERENCES files(id) ON DELETE SET NULL;

-- Update study_sessions table
DO $$ 
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.table_constraints 
        WHERE constraint_name = 'study_sessions_note_id_fkey'
        AND table_name = 'study_sessions'
    ) THEN
        ALTER TABLE study_sessions DROP CONSTRAINT study_sessions_note_id_fkey;
    END IF;
END $$;

ALTER TABLE study_sessions RENAME COLUMN note_id TO file_id;

ALTER TABLE study_sessions 
ADD CONSTRAINT study_sessions_file_id_fkey 
FOREIGN KEY (file_id) REFERENCES files(id) ON DELETE SET NULL;

-- Update embedding_queue table
DO $$ 
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.table_constraints 
        WHERE constraint_name = 'embedding_queue_note_id_fkey'
        AND table_name = 'embedding_queue'
    ) THEN
        ALTER TABLE embedding_queue DROP CONSTRAINT embedding_queue_note_id_fkey;
    END IF;
END $$;

ALTER TABLE embedding_queue RENAME COLUMN note_id TO file_id;

ALTER TABLE embedding_queue 
ADD CONSTRAINT embedding_queue_file_id_fkey 
FOREIGN KEY (file_id) REFERENCES files(id) ON DELETE CASCADE;

-- ============================================================================
-- STEP 4: Consolidate folder tables
-- ============================================================================

-- Migrate file_folders data to note_folders if needed
-- (In this case, we'll keep note_folders as the primary folder table)

INSERT INTO note_folders (id, user_id, name, color, created_at)
SELECT id, user_id, name, color, created_at
FROM file_folders
WHERE id NOT IN (SELECT id FROM note_folders)
ON CONFLICT (id) DO NOTHING;

-- Update files table to reference note_folders
-- (files.folder_id already references this in schema)

-- ============================================================================
-- STEP 5: Update note_embeddings to file_embeddings structure
-- ============================================================================

-- Migrate note_embeddings to file_embeddings
INSERT INTO file_embeddings (
    id,
    file_id,
    user_id,
    content_hash,
    model,
    embedding,
    created_at,
    updated_at
)
SELECT 
    ne.id,
    ne.note_id,
    ne.user_id,
    ne.content_hash,
    ne.model,
    ne.embedding,
    ne.created_at,
    ne.updated_at
FROM note_embeddings ne
WHERE ne.note_id NOT IN (SELECT file_id FROM file_embeddings)
ON CONFLICT (file_id) DO NOTHING;

-- ============================================================================
-- STEP 6: Update flashcard_sets.source_note_ids to source_file_ids
-- ============================================================================

ALTER TABLE flashcard_sets RENAME COLUMN source_note_ids TO source_file_ids;

-- ============================================================================
-- STEP 7: Drop old tables
-- ============================================================================

-- Drop tables that are no longer needed
DROP TABLE IF EXISTS note_embeddings CASCADE;
DROP TABLE IF EXISTS embedding_queue CASCADE;
DROP TABLE IF EXISTS notes CASCADE;
DROP TABLE IF EXISTS file_folders CASCADE;

-- ============================================================================
-- STEP 8: Add indexes for performance
-- ============================================================================

-- Add indexes on commonly queried columns
CREATE INDEX IF NOT EXISTS idx_files_user_id_updated_at ON files(user_id, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_files_folder_id ON files(folder_id);
CREATE INDEX IF NOT EXISTS idx_files_processing_status ON files(processing_status);
CREATE INDEX IF NOT EXISTS idx_file_embeddings_user_id ON file_embeddings(user_id);
CREATE INDEX IF NOT EXISTS idx_flashcards_source_file_id ON flashcards(source_file_id);
CREATE INDEX IF NOT EXISTS idx_study_sessions_file_id ON study_sessions(file_id);

-- ============================================================================
-- STEP 9: Update RLS policies
-- ============================================================================

-- Enable RLS on files table if not already enabled
ALTER TABLE files ENABLE ROW LEVEL SECURITY;

-- Drop existing policies if they exist
DROP POLICY IF EXISTS "Users can view their own files" ON files;
DROP POLICY IF EXISTS "Users can insert their own files" ON files;
DROP POLICY IF EXISTS "Users can update their own files" ON files;
DROP POLICY IF EXISTS "Users can delete their own files" ON files;

-- Create RLS policies for files table
CREATE POLICY "Users can view their own files"
ON files FOR SELECT
USING (auth.uid() = user_id);

CREATE POLICY "Users can insert their own files"
ON files FOR INSERT
WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update their own files"
ON files FOR UPDATE
USING (auth.uid() = user_id)
WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can delete their own files"
ON files FOR DELETE
USING (auth.uid() = user_id);

-- ============================================================================
-- STEP 10: Update triggers and functions
-- ============================================================================

-- Drop old note triggers if they exist
DROP TRIGGER IF EXISTS update_notes_updated_at ON notes;
DROP TRIGGER IF EXISTS handle_note_embedding_on_insert ON notes;
DROP TRIGGER IF EXISTS handle_note_embedding_on_update ON notes;

-- Create trigger to auto-update updated_at on files
CREATE OR REPLACE FUNCTION update_files_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS update_files_updated_at ON files;
CREATE TRIGGER update_files_updated_at
    BEFORE UPDATE ON files
    FOR EACH ROW
    EXECUTE FUNCTION update_files_updated_at();

-- ============================================================================
-- VERIFICATION QUERIES (Run these after migration)
-- ============================================================================

-- Check file counts
-- SELECT COUNT(*) as total_files FROM files;

-- Check folder counts  
-- SELECT COUNT(*) as total_folders FROM note_folders;

-- Check file embeddings
-- SELECT COUNT(*) as total_file_embeddings FROM file_embeddings;

-- Check flashcards with file references
-- SELECT COUNT(*) as flashcards_with_files FROM flashcards WHERE source_file_id IS NOT NULL;

-- ============================================================================
-- ROLLBACK INSTRUCTIONS (In case of issues)
-- ============================================================================

-- If you need to rollback, you would need to:
-- 1. Restore from backup
-- 2. Or recreate the notes table and reverse the column renames
-- IMPORTANT: Test this migration on a development database first!

-- ============================================================================
-- NOTES
-- ============================================================================

-- This migration is DESTRUCTIVE and cannot be easily reversed
-- Make sure to:
-- 1. BACKUP YOUR DATABASE before running this
-- 2. Test on a development/staging environment first
-- 3. Verify all data migrated correctly
-- 4. Update all application code before running in production
