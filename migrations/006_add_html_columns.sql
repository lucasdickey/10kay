-- Add HTML output columns to content table
-- These store the generated blog post and email HTML

ALTER TABLE content
ADD COLUMN blog_html TEXT,
ADD COLUMN email_html TEXT;

-- Add index on published_at for efficient querying
CREATE INDEX idx_content_published_at ON content(published_at) WHERE published_at IS NOT NULL;

-- Add comment
COMMENT ON COLUMN content.blog_html IS 'Generated HTML for blog post display';
COMMENT ON COLUMN content.email_html IS 'Generated HTML for email newsletter';
