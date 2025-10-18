-- ============================================================================
-- ADD OCR TRACKING COLUMN
-- Date: 2025-01-18
-- Description: Adds column to track which notes required OCR processing
-- Instructions: Run this script in Supabase SQL Editor
-- Safe to run multiple times (uses IF NOT EXISTS)
-- ============================================================================

-- Add OCR processed tracking column
ALTER TABLE notes 
ADD COLUMN IF NOT EXISTS ocr_processed BOOLEAN DEFAULT FALSE;

-- Create index for analytics queries
CREATE INDEX IF NOT EXISTS idx_notes_ocr_processed ON notes(ocr_processed) WHERE ocr_processed = TRUE;

-- Add comment to document the column
COMMENT ON COLUMN notes.ocr_processed IS 'TRUE if note required OCR for text extraction (scanned document)';

-- Success message
DO $$ 
BEGIN
    RAISE NOTICE '';
    RAISE NOTICE '========================================';
    RAISE NOTICE '✅ OCR tracking column added!';
    RAISE NOTICE '========================================';
    RAISE NOTICE '';
    RAISE NOTICE 'New column added:';
    RAISE NOTICE '  ✓ ocr_processed (boolean, default FALSE)';
    RAISE NOTICE '';
    RAISE NOTICE '📊 Use for analytics on scanned documents';
    RAISE NOTICE '🎉 Ready for Phase 2 OCR processing!';
    RAISE NOTICE '========================================';
END $$;
