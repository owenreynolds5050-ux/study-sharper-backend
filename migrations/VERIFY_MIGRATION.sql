-- ============================================================================
-- VERIFICATION QUERY - Run this after migration to verify everything worked
-- ============================================================================

SELECT '=== FILE COUNTS ===' as section, NULL as name, NULL as value
UNION ALL
SELECT 'Total Files', NULL, COUNT(*)::text FROM files
UNION ALL
SELECT 'Total Folders', NULL, COUNT(*)::text FROM note_folders
UNION ALL
SELECT 'Total File Embeddings', NULL, COUNT(*)::text FROM file_embeddings
UNION ALL
SELECT 'Flashcards with Files', NULL, COUNT(*)::text FROM flashcards WHERE source_file_id IS NOT NULL
UNION ALL
SELECT 'Study Sessions with Files', NULL, COUNT(*)::text FROM study_sessions WHERE file_id IS NOT NULL

UNION ALL
SELECT '', NULL, NULL

UNION ALL
SELECT '=== OLD TABLES (should be empty) ===' as section, NULL, NULL
UNION ALL
SELECT 'Old Table', table_name, 'SHOULD NOT EXIST!' 
FROM information_schema.tables 
WHERE table_schema = 'public' 
AND table_name IN ('notes', 'note_embeddings', 'file_folders')

UNION ALL
SELECT '', NULL, NULL

UNION ALL
SELECT '=== COLUMN RENAMES (check new names) ===' as section, NULL, NULL
UNION ALL
SELECT 'Flashcards column', column_name, 'Should be: source_file_id'
FROM information_schema.columns 
WHERE table_name = 'flashcards' 
AND column_name IN ('source_note_id', 'source_file_id')
UNION ALL
SELECT 'Study Sessions column', column_name, 'Should be: file_id'
FROM information_schema.columns 
WHERE table_name = 'study_sessions' 
AND column_name IN ('note_id', 'file_id')
UNION ALL
SELECT 'Flashcard Sets column', column_name, 'Should be: source_file_ids'
FROM information_schema.columns 
WHERE table_name = 'flashcard_sets' 
AND column_name IN ('source_note_ids', 'source_file_ids')

UNION ALL
SELECT '', NULL, NULL

UNION ALL
SELECT '=== NEW COLUMNS ON FILES TABLE ===' as section, NULL, NULL
UNION ALL
SELECT 'Files table column', column_name, 'Added successfully'
FROM information_schema.columns 
WHERE table_name = 'files' 
AND column_name IN ('summary', 'tags', 'transcription', 'ocr_processed', 'edited_manually', 'subject')

UNION ALL
SELECT '', NULL, NULL

UNION ALL
SELECT '=== FOREIGN KEY CONSTRAINTS ===' as section, NULL, NULL
UNION ALL
SELECT 'Files constraint', constraint_name, 'Should point to note_folders'
FROM information_schema.table_constraints 
WHERE table_name = 'files' 
AND constraint_name = 'files_folder_id_fkey'
UNION ALL
SELECT 'Flashcards constraint', constraint_name, 'Should reference files table'
FROM information_schema.table_constraints 
WHERE table_name = 'flashcards' 
AND constraint_name = 'flashcards_source_file_id_fkey'
UNION ALL
SELECT 'Study Sessions constraint', constraint_name, 'Should reference files table'
FROM information_schema.table_constraints 
WHERE table_name = 'study_sessions' 
AND constraint_name = 'study_sessions_file_id_fkey'

ORDER BY section, name;
