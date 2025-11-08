"""
Base publisher class for content distribution

Provides abstract interface for publishing content via email, social media, etc.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, Dict, Any, List
from enum import Enum
from datetime import datetime


class PublishChannel(str, Enum):
    """Distribution channels"""
    EMAIL_NEWSLETTER = 'email_newsletter'
    TWITTER = 'twitter'
    LINKEDIN = 'linkedin'
    WEBSITE = 'website'


class PublishStatus(str, Enum):
    """Publication status"""
    PENDING = 'pending'
    SENDING = 'sending'
    SENT = 'sent'
    FAILED = 'failed'


@dataclass
class PublishResult:
    """
    Result of publishing content to a channel

    This maps to the email_deliveries table for email channel.
    """
    content_id: str
    channel: PublishChannel
    status: PublishStatus

    # Delivery details
    delivered_at: Optional[datetime] = None
    recipient_count: Optional[int] = None

    # Channel-specific IDs
    external_id: Optional[str] = None  # Resend ID, Tweet ID, etc.

    # Engagement metrics (populated later)
    opened_count: Optional[int] = None
    clicked_count: Optional[int] = None

    # Error details if failed
    error_message: Optional[str] = None

    # Metadata
    metadata: Optional[Dict[str, Any]] = None


class BasePublisher(ABC):
    """
    Abstract base class for content publishers

    Implementations should:
    1. Fetch content and formatted output from database
    2. Fetch target audience (subscribers, followers, etc.)
    3. Send content through appropriate channel
    4. Track delivery status
    5. Update database with results

    Example:
        publisher = EmailPublisher(config)
        result = publisher.publish(
            content_id='123',
            channel=PublishChannel.EMAIL_NEWSLETTER,
            audience_filter={'tier': 'paid'}
        )
        publisher.save_delivery_record(result)
    """

    def __init__(self, config, db_connection=None, logger=None):
        """
        Initialize publisher

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
        Fetch content and formatted output from database

        Args:
            content_id: Database ID of content

        Returns:
            Dictionary with content and generated output

        Raises:
            FetchError: If fetching fails
        """
        pass

    @abstractmethod
    def get_audience(
        self,
        channel: PublishChannel,
        filter: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Get target audience for channel

        Args:
            channel: Distribution channel
            filter: Optional audience filters

        Returns:
            List of audience members (subscribers, followers, etc.)

        Example filters:
        - {'tier': 'paid'} - Only paid subscribers
        - {'tier': 'free'} - Only free tier users
        - {'enabled': true} - Only active subscribers
        - {'topics': ['AAPL', 'GOOGL']} - Interested in specific companies

        Raises:
            FetchError: If fetching fails
        """
        pass

    @abstractmethod
    def publish(
        self,
        content_id: str,
        channel: PublishChannel,
        audience_filter: Optional[Dict[str, Any]] = None,
        dry_run: bool = False
    ) -> PublishResult:
        """
        Publish content to channel

        Args:
            content_id: Database ID of content
            channel: Distribution channel
            audience_filter: Optional audience filters
            dry_run: If True, don't actually send, just validate

        Returns:
            PublishResult with delivery status

        Raises:
            PublishError: If publishing fails

        Channel-specific implementations:
        - EMAIL_NEWSLETTER: Send via Resend API
        - TWITTER: Post via Twitter API
        - LINKEDIN: Post via LinkedIn API
        - WEBSITE: Mark as published (no external action)
        """
        pass

    @abstractmethod
    def save_delivery_record(self, result: PublishResult):
        """
        Save delivery record to database

        Args:
            result: PublishResult to save

        Raises:
            DatabaseError: If save fails

        For email channel, this inserts into email_deliveries table.
        For other channels, this may update content metadata.
        """
        pass

    def check_if_published(
        self,
        content_id: str,
        channel: PublishChannel
    ) -> bool:
        """
        Check if content has already been published to channel

        Args:
            content_id: Database ID of content
            channel: Distribution channel

        Returns:
            True if already published, False otherwise
        """
        if not self.db_connection:
            return False

        cursor = self.db_connection.cursor()

        if channel == PublishChannel.EMAIL_NEWSLETTER:
            # Check email_deliveries table
            cursor.execute(
                """
                SELECT 1 FROM email_deliveries
                WHERE content_id = %s AND status = 'sent'
                """,
                (content_id,)
            )
        else:
            # Check content metadata for other channels
            cursor.execute(
                """
                SELECT 1 FROM content
                WHERE id = %s
                AND metadata->>'published_channels' @> %s
                """,
                (content_id, f'["{channel.value}"]')
            )

        exists = cursor.fetchone() is not None
        cursor.close()

        return exists

    def process_publication(
        self,
        content_id: str,
        channels: List[PublishChannel],
        audience_filter: Optional[Dict[str, Any]] = None,
        skip_existing: bool = True,
        dry_run: bool = False
    ) -> Dict[PublishChannel, PublishResult]:
        """
        Publish content to multiple channels

        Args:
            content_id: Database ID of content
            channels: List of channels to publish to
            audience_filter: Optional audience filters
            skip_existing: Skip channels where content is already published
            dry_run: If True, validate but don't actually send

        Returns:
            Dictionary mapping channel to PublishResult

        This is a convenience method for publishing to multiple channels.
        """
        if self.logger:
            self.logger.info(
                f"Publishing content {content_id} to {len(channels)} channels",
                extra={
                    'content_id': content_id,
                    'channels': [c.value for c in channels],
                    'dry_run': dry_run
                }
            )

        results = {}

        for channel in channels:
            # Skip if already published
            if skip_existing and self.check_if_published(content_id, channel):
                if self.logger:
                    self.logger.debug(
                        f"Skipping already published channel {channel.value}",
                        extra={'content_id': content_id}
                    )
                continue

            try:
                # Publish content
                result = self.publish(
                    content_id,
                    channel,
                    audience_filter,
                    dry_run
                )

                # Save delivery record
                if not dry_run:
                    self.save_delivery_record(result)

                results[channel] = result

                if self.logger:
                    self.logger.info(
                        f"Successfully published to {channel.value}",
                        extra={
                            'content_id': content_id,
                            'recipients': result.recipient_count,
                            'status': result.status.value
                        }
                    )

            except Exception as e:
                if self.logger:
                    self.logger.error(
                        f"Failed to publish to {channel.value}",
                        exception=e,
                        extra={'content_id': content_id}
                    )
                # Continue with next channel
                continue

        return results


class PublishError(Exception):
    """Raised when publishing fails"""
    pass


class FetchError(Exception):
    """Raised when fetching content or audience fails"""
    pass


class DatabaseError(Exception):
    """Raised when database operations fail"""
    pass
