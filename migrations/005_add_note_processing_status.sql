-- ============================================================================
-- ADD NOTE PROCESSING STATUS COLUMNS
-- Date: 2025-01-18
-- Description: Adds columns to track file processing status and extraction methods
-- Instructions: Run this script in Supabase SQL Editor
-- Safe to run multiple times (uses IF NOT EXISTS)
-- ============================================================================

-- Create processing status enum type
DO $$ BEGIN
    CREATE TYPE note_processing_status AS ENUM ('pending', 'processing', 'completed', 'failed');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- Add processing status column (default to 'completed' for existing notes)
ALTER TABLE notes 
ADD COLUMN IF NOT EXISTS processing_status note_processing_status DEFAULT 'completed';

-- Add extraction method column (tracks which extraction method succeeded)
ALTER TABLE notes 
ADD COLUMN IF NOT EXISTS extraction_method TEXT;

-- Add original filename column
ALTER TABLE notes 
ADD COLUMN IF NOT EXISTS original_filename TEXT;

-- Add file size bytes column (rename from file_size if needed)
DO $$ 
BEGIN
    -- Check if file_size exists and file_size_bytes doesn't
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'notes' AND column_name = 'file_size')
       AND NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'notes' AND column_name = 'file_size_bytes') THEN
        ALTER TABLE notes RENAME COLUMN file_size TO file_size_bytes;
    ELSE
        ALTER TABLE notes ADD COLUMN IF NOT EXISTS file_size_bytes INTEGER;
    END IF;
END $$;

-- Add error message column
ALTER TABLE notes 
ADD COLUMN IF NOT EXISTS error_message TEXT;

-- Add updated_at column if it doesn't exist
ALTER TABLE notes 
ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW();

-- Create function to auto-update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Drop trigger if exists and recreate
DROP TRIGGER IF EXISTS update_notes_updated_at ON notes;
CREATE TRIGGER update_notes_updated_at
    BEFORE UPDATE ON notes
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Create indexes for better query performance
CREATE INDEX IF NOT EXISTS idx_notes_processing_status ON notes(processing_status);
CREATE INDEX IF NOT EXISTS idx_notes_user_processing ON notes(user_id, processing_status);

-- Add comments to document the new columns
COMMENT ON COLUMN notes.processing_status IS 'Current processing status: pending, processing, completed, or failed';
COMMENT ON COLUMN notes.extraction_method IS 'Method used for successful text extraction (e.g., native_pdf, ocr, docx)';
COMMENT ON COLUMN notes.original_filename IS 'Original filename when uploaded';
COMMENT ON COLUMN notes.file_size_bytes IS 'Size of the uploaded file in bytes';
COMMENT ON COLUMN notes.error_message IS 'Error message if processing failed (NULL otherwise)';

-- Success message
DO $$ 
BEGIN
    RAISE NOTICE '';
    RAISE NOTICE '========================================';
    RAISE NOTICE '✅ Note processing status columns added!';
    RAISE NOTICE '========================================';
    RAISE NOTICE '';
    RAISE NOTICE 'New columns added:';
    RAISE NOTICE '  ✓ processing_status (enum)';
    RAISE NOTICE '  ✓ extraction_method';
    RAISE NOTICE '  ✓ original_filename';
    RAISE NOTICE '  ✓ file_size_bytes';
    RAISE NOTICE '  ✓ error_message';
    RAISE NOTICE '';
    RAISE NOTICE '📝 Existing notes set to "completed" status';
    RAISE NOTICE '🎉 Ready for enhanced file processing!';
    RAISE NOTICE '========================================';
END $$;
