-- Quick check to see which tables exist and their structure
-- Run this in Supabase SQL Editor

-- Check if notes table still exists
SELECT 'notes table exists' as status, COUNT(*) as record_count 
FROM notes
UNION ALL
-- Check if files table exists and has data
SELECT 'files table exists' as status, COUNT(*) as record_count 
FROM files;

-- Check files table columns
SELECT column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_name = 'files'
ORDER BY ordinal_position;
