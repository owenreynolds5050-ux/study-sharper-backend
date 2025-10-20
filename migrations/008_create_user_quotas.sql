-- Create note_folders table for organizing notes
CREATE TABLE IF NOT EXISTS note_folders (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    color TEXT DEFAULT 'blue',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create index for user_id lookups
CREATE INDEX IF NOT EXISTS idx_note_folders_user_id ON note_folders(user_id);

-- Enable RLS
ALTER TABLE note_folders ENABLE ROW LEVEL SECURITY;

-- Create RLS policy: users can only see their own folders
CREATE POLICY "Users can view their own folders" ON note_folders
    FOR SELECT USING (auth.uid() = user_id);

-- Create RLS policy: users can create their own folders
CREATE POLICY "Users can create their own folders" ON note_folders
    FOR INSERT WITH CHECK (auth.uid() = user_id);

-- Create RLS policy: users can update their own folders
CREATE POLICY "Users can update their own folders" ON note_folders
    FOR UPDATE USING (auth.uid() = user_id);

-- Create RLS policy: users can delete their own folders
CREATE POLICY "Users can delete their own folders" ON note_folders
    FOR DELETE USING (auth.uid() = user_id);

-- Create user_quotas table for tracking storage and upload limits
CREATE TABLE IF NOT EXISTS user_quotas (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    is_premium BOOLEAN DEFAULT FALSE,
    files_uploaded_today INTEGER DEFAULT 0,
    last_upload_reset_date DATE DEFAULT CURRENT_DATE,
    total_storage_used BIGINT DEFAULT 0,
    total_files INTEGER DEFAULT 0,
    storage_limit BIGINT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(user_id)
);

-- Create index for user_id lookups
CREATE INDEX IF NOT EXISTS idx_user_quotas_user_id ON user_quotas(user_id);

-- Enable RLS
ALTER TABLE user_quotas ENABLE ROW LEVEL SECURITY;

-- Create RLS policy: users can only see their own quota
CREATE POLICY "Users can view their own quota" ON user_quotas
    FOR SELECT USING (auth.uid() = user_id);

-- Create RLS policy: users can update their own quota (for admin operations)
CREATE POLICY "Users can update their own quota" ON user_quotas
    FOR UPDATE USING (auth.uid() = user_id);

-- Create RLS policy: service role can do anything (for backend)
CREATE POLICY "Service role can manage quotas" ON user_quotas
    FOR ALL USING (auth.role() = 'service_role');
