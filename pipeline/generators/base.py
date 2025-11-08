"""
Base generator class for multi-format content generation

Provides abstract interface for generating blog posts, emails, tweets, etc.
from analyzed content.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, Dict, Any, List
from enum import Enum


class ContentFormat(str, Enum):
    """Output formats we generate"""
    BLOG_POST_HTML = 'blog_post_html'
    EMAIL_HTML = 'email_html'
    TWITTER_THREAD = 'twitter_thread'
    LINKEDIN_POST = 'linkedin_post'
    PODCAST_SCRIPT = 'podcast_script'


@dataclass
class GeneratedContent:
    """
    Generated content in a specific format

    Each format has different requirements and constraints.
    """
    content_id: str
    format: ContentFormat
    output: str

    # Format-specific metadata
    metadata: Optional[Dict[str, Any]] = None

    # Example metadata by format:
    # BLOG_POST_HTML: {'word_count': 1200, 'reading_time_minutes': 5}
    # EMAIL_HTML: {'subject_line': '...', 'preview_text': '...'}
    # TWITTER_THREAD: {'tweet_count': 8, 'character_counts': [280, 275, ...]}
    # LINKEDIN_POST: {'character_count': 1500, 'has_image': true}
    # PODCAST_SCRIPT: {'word_count': 800, 'estimated_duration_minutes': 5}


class BaseGenerator(ABC):
    """
    Abstract base class for content generators

    Implementations should:
    1. Fetch analyzed content from database
    2. Transform content for specific format
    3. Apply formatting and styling
    4. Validate output meets format constraints
    5. Update database with generated content

    Example:
        generator = BlogPostGenerator(config)
        blog_html = generator.generate(
            content_id='123',
            format=ContentFormat.BLOG_POST_HTML
        )
        generator.save_to_database(content_id, blog_html)
    """

    def __init__(self, config, db_connection=None, logger=None):
        """
        Initialize generator

        Args:
            config: PipelineConfig instance
            db_connection: Database connection (psycopg2)
            logger: PipelineLogger instance
        """
        self.config = config
        self.db_connection = db_connection
        self.logger = logger

    @abstractmethod
    def fetch_content(self, content_id: str) -> Dict[str, Any]:
        """
        Fetch analyzed content from database

        Args:
            content_id: Database ID of content

        Returns:
            Dictionary with content fields (tldr_*, deep_*)

        Raises:
            FetchError: If fetching fails
        """
        pass

    @abstractmethod
    def generate(
        self,
        content_id: str,
        format: ContentFormat,
        options: Optional[Dict[str, Any]] = None
    ) -> GeneratedContent:
        """
        Generate content in specified format

        Args:
            content_id: Database ID of content
            format: Output format to generate
            options: Format-specific options

        Returns:
            GeneratedContent with formatted output

        Raises:
            GenerationError: If generation fails

        Format-specific options:
        - BLOG_POST_HTML: {'include_toc': true, 'style': 'default'}
        - EMAIL_HTML: {'template': 'newsletter', 'include_unsubscribe': true}
        - TWITTER_THREAD: {'max_tweets': 10, 'include_hashtags': true}
        - LINKEDIN_POST: {'max_length': 3000, 'professional_tone': true}
        - PODCAST_SCRIPT: {'target_duration_minutes': 5, 'conversational_tone': true}
        """
        pass

    @abstractmethod
    def save_to_database(
        self,
        content_id: str,
        generated: GeneratedContent
    ):
        """
        Update content record with generated output

        Args:
            content_id: Database ID of content
            generated: GeneratedContent to save

        Raises:
            DatabaseError: If save fails

        This updates the appropriate column in the content table:
        - BLOG_POST_HTML → blog_html
        - EMAIL_HTML → email_html
        - TWITTER_THREAD → tweet_thread
        - LINKEDIN_POST → linkedin_post
        - PODCAST_SCRIPT → podcast_script
        """
        pass

    def validate_format(
        self,
        generated: GeneratedContent
    ) -> bool:
        """
        Validate generated content meets format requirements

        Args:
            generated: GeneratedContent to validate

        Returns:
            True if valid, False otherwise

        Override this method to add format-specific validation rules.
        """
        # Basic validation - ensure output is not empty
        return bool(generated.output and generated.output.strip())

    def process_content(
        self,
        content_id: str,
        formats: List[ContentFormat],
        options: Optional[Dict[str, Any]] = None
    ) -> Dict[ContentFormat, GeneratedContent]:
        """
        Generate content in multiple formats

        Args:
            content_id: Database ID of content
            formats: List of formats to generate
            options: Format-specific options

        Returns:
            Dictionary mapping format to GeneratedContent

        This is a convenience method for generating multiple formats at once.
        """
        if self.logger:
            self.logger.info(
                f"Generating {len(formats)} formats for content {content_id}",
                extra={'content_id': content_id, 'formats': [f.value for f in formats]}
            )

        results = {}

        for format in formats:
            try:
                # Generate content
                generated = self.generate(content_id, format, options)

                # Validate
                if not self.validate_format(generated):
                    if self.logger:
                        self.logger.warning(
                            f"Generated content failed validation for {format.value}",
                            extra={'content_id': content_id}
                        )
                    continue

                # Save to database
                self.save_to_database(content_id, generated)

                results[format] = generated

                if self.logger:
                    self.logger.info(
                        f"Successfully generated {format.value}",
                        extra={'content_id': content_id}
                    )

            except Exception as e:
                if self.logger:
                    self.logger.error(
                        f"Failed to generate {format.value}",
                        exception=e,
                        extra={'content_id': content_id}
                    )
                # Continue with next format
                continue

        return results


class GenerationError(Exception):
    """Raised when content generation fails"""
    pass


class FetchError(Exception):
    """Raised when fetching content fails"""
    pass


class DatabaseError(Exception):
    """Raised when database operations fail"""
    pass
