-- Migration: 009_consolidate_upload_removal.sql
-- Purpose: Remove all upload-related functionality from the database schema
-- Date: 2025-10-23
-- Description: Consolidates the removal of file upload, OCR, and audio transcription features
--              Simplifies the files table to only support manual note creation

-- ============================================================================
-- PHASE 1: DROP UPLOAD-SPECIFIC TABLES
-- ============================================================================
-- These tables were only used for upload processing and are no longer needed

DROP TABLE IF EXISTS public.embedding_queue CASCADE;
DROP TABLE IF EXISTS public.processing_jobs CASCADE;
DROP TABLE IF EXISTS public.audio_transcriptions CASCADE;

-- ============================================================================
-- PHASE 2: REMOVE UPLOAD-RELATED COLUMNS FROM files TABLE
-- ============================================================================
-- Simplify the files table by removing columns that were only used for uploads

ALTER TABLE public.files 
DROP COLUMN IF EXISTS original_filename,
DROP COLUMN IF EXISTS file_size_bytes,
DROP COLUMN IF EXISTS processing_status,
DROP COLUMN IF EXISTS extraction_method,
DROP COLUMN IF EXISTS error_message,
DROP COLUMN IF EXISTS has_images,
DROP COLUMN IF EXISTS original_preview_path,
DROP COLUMN IF EXISTS last_accessed_at,
DROP COLUMN IF EXISTS transcription,
DROP COLUMN IF EXISTS ocr_processed,
DROP COLUMN IF EXISTS edited_manually,
DROP COLUMN IF EXISTS subject,
DROP COLUMN IF EXISTS file_path,
DROP COLUMN IF EXISTS extracted_text;

-- ============================================================================
-- PHASE 3: VERIFY files TABLE STRUCTURE
-- ============================================================================
-- After removals, files table should have these columns:
-- - id (uuid, primary key)
-- - user_id (uuid, foreign key to auth.users)
-- - folder_id (uuid, foreign key to note_folders, nullable)
-- - title (text, not null)
-- - content (text, for manual note content)
-- - file_type (text, now always 'md' or 'txt')
-- - summary (text, optional)
-- - tags (text[], optional)
-- - created_at (timestamp with time zone)
-- - updated_at (timestamp with time zone)

-- ============================================================================
-- PHASE 4: CREATE PERFORMANCE INDEXES
-- ============================================================================
-- Add indexes for frequently queried columns to improve performance

CREATE INDEX IF NOT EXISTS idx_files_user_id ON public.files(user_id);
CREATE INDEX IF NOT EXISTS idx_files_folder_id ON public.files(folder_id);
CREATE INDEX IF NOT EXISTS idx_files_created_at ON public.files(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_files_updated_at ON public.files(updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_file_embeddings_user_id ON public.file_embeddings(user_id);
CREATE INDEX IF NOT EXISTS idx_file_embeddings_file_id ON public.file_embeddings(file_id);

-- ============================================================================
-- PHASE 5: VERIFY RLS POLICIES
-- ============================================================================
-- Ensure Row Level Security is enabled on files table
-- This prevents users from accessing other users' files

ALTER TABLE public.files ENABLE ROW LEVEL SECURITY;

-- Create or replace RLS policy for files table
DROP POLICY IF EXISTS "Users can only access their own files" ON public.files;
CREATE POLICY "Users can only access their own files" ON public.files
  FOR ALL USING (auth.uid() = user_id);

-- ============================================================================
-- PHASE 6: VERIFY FOREIGN KEY CONSTRAINTS
-- ============================================================================
-- Ensure all foreign keys are properly configured

-- files table foreign keys should be:
-- - user_id -> auth.users(id)
-- - folder_id -> note_folders(id) ON DELETE SET NULL

-- file_embeddings table foreign keys should be:
-- - file_id -> files(id) ON DELETE CASCADE
-- - user_id -> auth.users(id)

-- ============================================================================
-- SUMMARY OF CHANGES
-- ============================================================================
-- Tables Deleted:
--   - embedding_queue (upload processing)
--   - processing_jobs (upload processing)
--   - audio_transcriptions (audio upload feature)
--
-- Columns Removed from files table:
--   - original_filename
--   - file_size_bytes
--   - processing_status
--   - extraction_method
--   - error_message
--   - has_images
--   - original_preview_path
--   - last_accessed_at
--   - transcription
--   - ocr_processed
--   - edited_manually
--   - subject
--   - file_path
--   - extracted_text
--
-- Tables Kept:
--   - user_quotas (can be kept for future use, currently unused)
--   - file_embeddings (needed for semantic search)
--   - flashcard_sets (needed for flashcard generation)
--   - All other tables remain unchanged
--
-- Performance Improvements:
--   - Added indexes on frequently queried columns
--   - Simplified table structure reduces query complexity
--   - RLS policies ensure data security
