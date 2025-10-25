-- Migration: Add folder nesting support to note_folders table
-- Adds parent_folder_id and depth columns to support folder hierarchy

-- Add parent_folder_id column (nullable, for root folders)
ALTER TABLE public.note_folders 
ADD COLUMN IF NOT EXISTS parent_folder_id uuid REFERENCES public.note_folders(id) ON DELETE CASCADE;

-- Add depth column (0 for root folders, 1 for subfolders)
ALTER TABLE public.note_folders 
ADD COLUMN IF NOT EXISTS depth integer DEFAULT 0 CHECK (depth >= 0 AND depth <= 2);

-- Create index on parent_folder_id for faster lookups
CREATE INDEX IF NOT EXISTS idx_note_folders_parent_folder_id 
ON public.note_folders(parent_folder_id);

-- Create index on user_id and parent_folder_id for efficient folder hierarchy queries
CREATE INDEX IF NOT EXISTS idx_note_folders_user_parent 
ON public.note_folders(user_id, parent_folder_id);

-- Create index on depth for depth validation queries
CREATE INDEX IF NOT EXISTS idx_note_folders_depth 
ON public.note_folders(depth);
