-- Migration: Consolidate notes system into files system - FINAL VERSION
-- This migration replaces the notes table with the files table
-- and ensures all functionality is preserved
-- 
-- Safe to run: Uses IF NOT EXISTS and checks for existing state

BEGIN;

-- ============================================================================
-- STEP 1: Add missing columns to files table
-- ============================================================================

ALTER TABLE files ADD COLUMN IF NOT EXISTS summary text;
ALTER TABLE files ADD COLUMN IF NOT EXISTS tags text[] DEFAULT '{}';
ALTER TABLE files ADD COLUMN IF NOT EXISTS transcription text;
ALTER TABLE files ADD COLUMN IF NOT EXISTS ocr_processed boolean DEFAULT false;
ALTER TABLE files ADD COLUMN IF NOT EXISTS edited_manually boolean DEFAULT false;
ALTER TABLE files ADD COLUMN IF NOT EXISTS subject text;

-- ============================================================================
-- STEP 2: Consolidate folder tables FIRST
-- ============================================================================

-- Merge file_folders into note_folders
INSERT INTO note_folders (id, user_id, name, color, created_at)
SELECT id, user_id, name, color, created_at
FROM file_folders
WHERE id NOT IN (SELECT id FROM note_folders)
ON CONFLICT (id) DO NOTHING;

-- Drop and recreate the files.folder_id foreign key to point to note_folders
ALTER TABLE files DROP CONSTRAINT IF EXISTS files_folder_id_fkey;
ALTER TABLE files 
ADD CONSTRAINT files_folder_id_fkey 
FOREIGN KEY (folder_id) REFERENCES note_folders(id) ON DELETE SET NULL;

-- ============================================================================
-- STEP 3: Migrate notes data to files table
-- ============================================================================

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
    COALESCE(n.content, ''),  -- Ensure not null
    COALESCE(n.original_filename, n.title || '.md'),
    COALESCE(n.file_type, 'md'),
    COALESCE(n.file_size_bytes, 0),
    COALESCE(CAST(n.processing_status AS text), 'completed'),
    n.extraction_method,
    n.error_message,
    COALESCE(n.has_images, false),
    n.summary,
    COALESCE(n.tags, '{}'),
    n.transcription,
    COALESCE(n.ocr_processed, false),
    COALESCE(n.edited_manually, false),
    n.subject,
    COALESCE(n.created_at, now()),
    COALESCE(n.updated_at, now()),
    COALESCE(n.updated_at, now())
FROM notes n
WHERE n.id NOT IN (SELECT id FROM files)
ON CONFLICT (id) DO NOTHING;

-- ============================================================================
-- STEP 4: Migrate note_embeddings to file_embeddings
-- ============================================================================

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
WHERE ne.note_id IN (SELECT id FROM files)
AND ne.note_id NOT IN (SELECT COALESCE(file_id, '00000000-0000-0000-0000-000000000000'::uuid) FROM file_embeddings)
ON CONFLICT (file_id) DO NOTHING;

-- ============================================================================
-- STEP 5: Update foreign key references - Flashcards
-- ============================================================================

-- Drop old constraint
ALTER TABLE flashcards DROP CONSTRAINT IF EXISTS flashcards_source_note_id_fkey;

-- Rename column
ALTER TABLE flashcards RENAME COLUMN source_note_id TO source_file_id;

-- Add new constraint
ALTER TABLE flashcards 
ADD CONSTRAINT flashcards_source_file_id_fkey 
FOREIGN KEY (source_file_id) REFERENCES files(id) ON DELETE SET NULL;

-- ============================================================================
-- STEP 6: Update foreign key references - Study Sessions
-- ============================================================================

-- Drop old constraint
ALTER TABLE study_sessions DROP CONSTRAINT IF EXISTS study_sessions_note_id_fkey;

-- Rename column
ALTER TABLE study_sessions RENAME COLUMN note_id TO file_id;

-- Add new constraint
ALTER TABLE study_sessions 
ADD CONSTRAINT study_sessions_file_id_fkey 
FOREIGN KEY (file_id) REFERENCES files(id) ON DELETE SET NULL;

-- ============================================================================
-- STEP 7: Update flashcard_sets array column
-- ============================================================================

ALTER TABLE flashcard_sets RENAME COLUMN source_note_ids TO source_file_ids;

-- ============================================================================
-- STEP 8: Handle embedding_queue (if exists)
-- ============================================================================

DO $$ 
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'embedding_queue') THEN
        -- Drop old constraint
        ALTER TABLE embedding_queue DROP CONSTRAINT IF EXISTS embedding_queue_note_id_fkey;
        
        -- Rename column
        ALTER TABLE embedding_queue RENAME COLUMN note_id TO file_id;
        
        -- Add new constraint
        ALTER TABLE embedding_queue 
        ADD CONSTRAINT embedding_queue_file_id_fkey 
        FOREIGN KEY (file_id) REFERENCES files(id) ON DELETE CASCADE;
    END IF;
END $$;

-- ============================================================================
-- STEP 9: Drop old tables
-- ============================================================================

DROP TABLE IF EXISTS note_embeddings CASCADE;
DROP TABLE IF EXISTS notes CASCADE;
DROP TABLE IF EXISTS file_folders CASCADE;

-- ============================================================================
-- STEP 10: Create indexes for performance
-- ============================================================================

CREATE INDEX IF NOT EXISTS idx_files_user_id_updated_at ON files(user_id, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_files_folder_id ON files(folder_id);
CREATE INDEX IF NOT EXISTS idx_files_processing_status ON files(processing_status);
CREATE INDEX IF NOT EXISTS idx_file_embeddings_user_id ON file_embeddings(user_id);
CREATE INDEX IF NOT EXISTS idx_flashcards_source_file_id ON flashcards(source_file_id);
CREATE INDEX IF NOT EXISTS idx_study_sessions_file_id ON study_sessions(file_id);

-- ============================================================================
-- STEP 11: Update RLS policies on files table
-- ============================================================================

ALTER TABLE files ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Users can view their own files" ON files;
DROP POLICY IF EXISTS "Users can insert their own files" ON files;
DROP POLICY IF EXISTS "Users can update their own files" ON files;
DROP POLICY IF EXISTS "Users can delete their own files" ON files;

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
-- STEP 12: Create/update triggers
-- ============================================================================

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

COMMIT;

-- ============================================================================
-- Migration complete! Run verification queries below separately:
-- ============================================================================

-- SELECT COUNT(*) as total_files FROM files;
-- SELECT COUNT(*) as total_folders FROM note_folders;
-- SELECT COUNT(*) as total_embeddings FROM file_embeddings;
-- SELECT COUNT(*) as flashcards_with_files FROM flashcards WHERE source_file_id IS NOT NULL;
-- 
-- -- Verify old tables are gone
-- SELECT table_name FROM information_schema.tables 
-- WHERE table_schema = 'public' 
-- AND table_name IN ('notes', 'note_embeddings', 'file_folders');
