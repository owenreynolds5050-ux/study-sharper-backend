-- 017_add_folder_hierarchy.sql
-- Adds parent/child relationships to note_folders

ALTER TABLE note_folders
    ADD COLUMN IF NOT EXISTS parent_folder_id UUID REFERENCES note_folders(id) ON DELETE SET NULL;

ALTER TABLE note_folders
    ADD CONSTRAINT note_folders_parent_self CHECK (
        parent_folder_id IS NULL OR parent_folder_id <> id
    );

CREATE INDEX IF NOT EXISTS idx_note_folders_parent ON note_folders(parent_folder_id);
