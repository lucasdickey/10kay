-- Fix processing_logs table schema
--
-- The PipelineLogger expects a 'level' column for log severity (debug, info, warning, error, critical)
-- but the original schema only had 'status' for processing status (started, completed, failed).
--
-- This migration adds the 'level' column and keeps 'status' for tracking step completion.

-- Add level column for log severity
ALTER TABLE processing_logs
ADD COLUMN IF NOT EXISTS level VARCHAR(20);

-- Create index for filtering by log level
CREATE INDEX IF NOT EXISTS idx_logs_level ON processing_logs(level);

-- Update existing records to have a default level
UPDATE processing_logs
SET level = 'info'
WHERE level IS NULL;

-- Add comments
COMMENT ON COLUMN processing_logs.level IS 'Log severity: debug, info, warning, error, critical';
COMMENT ON COLUMN processing_logs.status IS 'Step status: started, completed, failed';
