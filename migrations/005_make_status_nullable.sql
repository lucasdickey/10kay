-- Make status column nullable in processing_logs
--
-- The 'status' column is meant for tracking step-level status (started, completed, failed)
-- but not all log entries represent step boundaries. Making it nullable allows
-- general logging without requiring a step status.

ALTER TABLE processing_logs
ALTER COLUMN status DROP NOT NULL;

COMMENT ON COLUMN processing_logs.status IS 'Step status (optional): started, completed, failed';
