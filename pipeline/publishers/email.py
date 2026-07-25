"""
Email publisher implementation

Publishes content via Resend email API to newsletter subscribers.
"""
import os
from typing import Dict, Any, List, Optional
from datetime import datetime
import requests
import json

from .base import (
    BasePublisher,
    PublishResult,
    PublishChannel,
    PublishStatus,
    PublishError,
    FetchError,
    DatabaseError
)


class EmailPublisher(BasePublisher):
    """
    Concrete implementation of email publisher

    Uses Resend API to send newsletter emails to subscribers.
    Handles free vs paid tier access control.
    """

    def __init__(self, config, db_connection=None, logger=None):
        """Initialize email publisher with Resend API client"""
        super().__init__(config, db_connection, logger)

        # Resend API configuration
        self.resend_api_key = os.getenv('RESEND_API_KEY')
        self.resend_api_url = 'https://api.resend.com/emails'
        self.from_email = os.getenv('FROM_EMAIL', 'newsletter@10kay.com')
        self.from_name = os.getenv('FROM_NAME', '10KAY')

        if not self.resend_api_key:
            if self.logger:
                self.logger.warning("RESEND_API_KEY not set - email sending will fail")

        if self.logger:
            self.logger.info(
                f"Initialized EmailPublisher",
                extra={'from_email': self.from_email}
            )

    def fetch_content(self, content_id: str) -> Dict[str, Any]:
        """
        Fetch content and formatted email HTML from database

        Args:
            content_id: Database ID of content

        Returns:
            Dictionary with content and email HTML

        Raises:
            FetchError: If fetching fails
        """
        if not self.db_connection:
            raise FetchError("No database connection available")

        from ..db import ContentRepository, DatabaseError as DbError, read_cursor

        # Fetched as a dict: the previous version selected six columns and then
        # read row[6], so this method raised IndexError on every call and the
        # publish phase could never load its content.
        try:
            with read_cursor(self.db_connection) as cursor:
                cursor.execute("""
                    SELECT
                        COALESCE(c.key_takeaways->>'headline', c.executive_summary) AS headline,
                        c.email_html,
                        c.slug,
                        co.id   AS company_id,
                        co.ticker,
                        co.name AS company_name,
                        f.filing_type,
                        f.fiscal_year,
                        f.fiscal_quarter
                    FROM content c
                    JOIN filings f    ON c.filing_id = f.id
                    JOIN companies co ON f.company_id = co.id
                    WHERE c.id = %s
                """, (content_id,))
                row = cursor.fetchone()
        except DbError as e:
            raise FetchError(f"Failed to fetch content {content_id}: {e}") from e

        if not row:
            raise FetchError(f"Content {content_id} not found")

        content = dict(row)
        quarter = content.get('fiscal_quarter')
        content['fiscal_period'] = f"Q{quarter}" if quarter else 'FY'

        if not content.get('email_html'):
            raise FetchError(
                f"Content {content_id} ({content.get('ticker')}) has no email_html; "
                "run the generate phase first"
            )

        return content

    def get_audience(
        self,
        channel: PublishChannel,
        filter: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Get the target audience for the email newsletter.

        Supported filters: ``tier`` ('free' / 'paid') and ``company_id``, which
        respects each subscriber's ``interested_companies`` list.

        Raises:
            FetchError: If fetching fails
        """
        if channel != PublishChannel.EMAIL_NEWSLETTER:
            raise FetchError(f"Unsupported channel: {channel}")

        if not self.db_connection:
            raise FetchError("No database connection available")

        from ..db import DatabaseError as DbError, SubscriberRepository

        filter = filter or {}

        try:
            rows = SubscriberRepository(self.db_connection).active(
                tier=filter.get('tier'),
                company_id=filter.get('company_id'),
            )
        except DbError as e:
            raise FetchError(f"Failed to fetch audience: {e}") from e

        subscribers = [
            {
                'id': str(row['id']),
                'email': row['email'],
                # subscribers has no first_name column; derive a greeting from
                # the local part rather than selecting a column that does not exist.
                'first_name': (row['email'] or '').split('@')[0],
                'tier': row.get('subscription_tier') or 'free',
                'content_preference': row.get('content_preference') or 'tldr',
                'topics': row.get('interested_companies') or [],
            }
            for row in rows
        ]

        if self.logger:
            self.logger.info(
                f"Found {len(subscribers)} subscribers",
                extra={'filter': filter},
            )

        return subscribers

    def publish(
        self,
        content_id: str,
        channel: PublishChannel,
        audience_filter: Optional[Dict[str, Any]] = None,
        dry_run: bool = False
    ) -> PublishResult:
        """
        Publish content via email newsletter

        Args:
            content_id: Database ID of content
            channel: Distribution channel (must be EMAIL_NEWSLETTER)
            audience_filter: Optional audience filters
            dry_run: If True, don't actually send

        Returns:
            PublishResult with delivery status

        Raises:
            PublishError: If publishing fails
        """
        if channel != PublishChannel.EMAIL_NEWSLETTER:
            raise PublishError(f"Unsupported channel: {channel}")

        if self.logger:
            self.logger.info(
                f"Publishing content {content_id} via email",
                extra={'content_id': content_id, 'dry_run': dry_run}
            )

        try:
            # Fetch content
            content = self.fetch_content(content_id)

            # Verify email HTML is available
            if not content['email_html']:
                raise PublishError("Email HTML not generated yet")

            # Get audience
            subscribers = self.get_audience(channel, audience_filter)

            if not subscribers:
                if self.logger:
                    self.logger.warning("No subscribers found for filters")
                return PublishResult(
                    content_id=content_id,
                    channel=channel,
                    status=PublishStatus.SENT,
                    delivered_at=datetime.now(),
                    recipient_count=0
                )

            # Build subject line
            subject = f"{content['ticker']}: {content['headline']}"

            if dry_run:
                # Dry run - don't actually send
                if self.logger:
                    self.logger.info(
                        f"DRY RUN: Would send to {len(subscribers)} subscribers",
                        extra={
                            'subject': subject,
                            'recipients': len(subscribers)
                        }
                    )

                return PublishResult(
                    content_id=content_id,
                    channel=channel,
                    status=PublishStatus.SENT,
                    delivered_at=datetime.now(),
                    recipient_count=len(subscribers),
                    metadata={'dry_run': True}
                )

            # Send via Resend API
            # Note: Resend supports batch sending, but for now we'll send individually
            # to track per-subscriber deliveries

            sent_count = 0
            failed_count = 0
            resend_ids = []

            for subscriber in subscribers:
                try:
                    # Personalize email
                    personalized_html = self._personalize_email(
                        content['email_html'],
                        subscriber
                    )

                    # Send email
                    resend_id = self._send_via_resend(
                        to_email=subscriber['email'],
                        to_name=subscriber.get('first_name'),
                        subject=subject,
                        html=personalized_html,
                        subscriber_id=subscriber['id'],
                        content_id=content_id
                    )

                    if resend_id:
                        sent_count += 1
                        resend_ids.append(resend_id)
                    else:
                        failed_count += 1

                except Exception as e:
                    if self.logger:
                        self.logger.error(
                            f"Failed to send to {subscriber['email']}",
                            exception=e,
                            extra={'subscriber_id': subscriber['id']}
                        )
                    failed_count += 1
                    continue

            # Determine overall status
            if sent_count == 0:
                status = PublishStatus.FAILED
            elif failed_count > 0:
                status = PublishStatus.SENT  # Partial success
            else:
                status = PublishStatus.SENT

            if self.logger:
                self.logger.info(
                    f"Email send complete: {sent_count} sent, {failed_count} failed",
                    extra={
                        'content_id': content_id,
                        'sent': sent_count,
                        'failed': failed_count
                    }
                )

            return PublishResult(
                content_id=content_id,
                channel=channel,
                status=status,
                delivered_at=datetime.now(),
                recipient_count=sent_count,
                external_id=resend_ids[0] if resend_ids else None,  # First Resend ID
                metadata={
                    'sent_count': sent_count,
                    'failed_count': failed_count,
                    'resend_ids': resend_ids
                }
            )

        except Exception as e:
            raise PublishError(f"Failed to publish via email: {e}")

    def _personalize_email(
        self,
        html: str,
        subscriber: Dict[str, Any]
    ) -> str:
        """
        Personalize email HTML for subscriber

        Args:
            html: Base email HTML
            subscriber: Subscriber info

        Returns:
            Personalized HTML
        """
        # Replace personalization tokens
        personalized = html

        # Add subscriber name if available
        if subscriber.get('first_name'):
            personalized = personalized.replace(
                '{{first_name}}',
                subscriber['first_name']
            )

        # Add unsubscribe link
        unsubscribe_url = f"https://10kay.com/unsubscribe?id={subscriber['id']}"
        personalized = personalized.replace(
            '{{unsubscribe_url}}',
            unsubscribe_url
        )

        return personalized

    def _send_via_resend(
        self,
        to_email: str,
        to_name: Optional[str],
        subject: str,
        html: str,
        subscriber_id: str,
        content_id: str
    ) -> Optional[str]:
        """
        Send email via Resend API

        Args:
            to_email: Recipient email
            to_name: Recipient name (optional)
            subject: Email subject
            html: Email HTML
            subscriber_id: Database ID of subscriber
            content_id: Database ID of content

        Returns:
            Resend email ID if successful, None otherwise
        """
        if not self.resend_api_key:
            raise PublishError("RESEND_API_KEY not configured")

        headers = {
            'Authorization': f'Bearer {self.resend_api_key}',
            'Content-Type': 'application/json'
        }

        # Build recipient
        to = f"{to_name} <{to_email}>" if to_name else to_email

        payload = {
            'from': f"{self.from_name} <{self.from_email}>",
            'to': [to],
            'subject': subject,
            'html': html,
            'tags': [
                {'name': 'content_id', 'value': content_id},
                {'name': 'subscriber_id', 'value': subscriber_id}
            ]
        }

        try:
            response = requests.post(
                self.resend_api_url,
                headers=headers,
                json=payload,
                timeout=30
            )

            response.raise_for_status()

            result = response.json()
            resend_id = result.get('id')

            if self.logger:
                self.logger.debug(
                    f"Sent email via Resend",
                    extra={
                        'to': to_email,
                        'resend_id': resend_id
                    }
                )

            return resend_id

        except requests.exceptions.RequestException as e:
            if self.logger:
                self.logger.error(
                    f"Resend API error",
                    exception=e,
                    extra={'to': to_email}
                )
            return None

    def save_delivery_record(self, result: PublishResult) -> str:
        """
        Record an email send in ``email_deliveries``.

        This method never worked: it inserted into a ``metadata`` column that
        migration 002 did not create, so every call raised UndefinedColumn and
        no send was ever tracked. Migration 010 adds the column; the write now
        goes through DeliveryRepository, which validates the record first.

        Returns:
            The delivery record's UUID.
        """
        if not self.db_connection:
            raise DatabaseError("No database connection available")

        from ..db import (
            DatabaseError as DbError,
            DeliveryRecord,
            DeliveryRepository,
        )

        record = DeliveryRecord(
            content_id=result.content_id,
            subscriber_id=None,  # batch-level record; per-subscriber rows TBD
            status=result.status.value,
            sent_at=result.delivered_at,
            resend_email_id=result.external_id,
            metadata={
                **(result.metadata or {}),
                'channel': result.channel.value,
                'recipient_count': result.recipient_count,
                'error_message': result.error_message,
            },
        )

        try:
            delivery_id = DeliveryRepository(self.db_connection).record(record)
        except DbError as e:
            raise DatabaseError(f"Failed to save delivery record: {e}") from e

        if self.logger:
            self.logger.info(
                "Saved email delivery record",
                extra={
                    'delivery_id': delivery_id,
                    'content_id': result.content_id,
                    'recipients': result.recipient_count,
                },
            )

        return delivery_id

    def count_ready_content(self) -> int:
        """Count current content with email HTML that has not been published."""
        if not self.db_connection:
            raise DatabaseError("No database connection available")

        from ..db import ContentRepository, DatabaseError as DbError

        try:
            return ContentRepository(self.db_connection).count_ready_to_publish()
        except DbError as e:
            raise DatabaseError(f"Failed to count ready content: {e}") from e

    def get_ready_content(
        self,
        limit: Optional[int] = None,
        tier: str = 'all',
    ) -> List[Dict[str, Any]]:
        """
        Content ready to publish.

        The query also excludes anything with a 'sent' delivery record, so a run
        that crashed after sending but before setting ``published_at`` does not
        mail the same analysis to every subscriber twice. ``tier`` filters the
        audience at send time, not the content selection.
        """
        if not self.db_connection:
            raise DatabaseError("No database connection available")

        from ..db import ContentRepository, DatabaseError as DbError

        try:
            return ContentRepository(self.db_connection).ready_to_publish(limit=limit)
        except DbError as e:
            raise DatabaseError(f"Failed to get ready content: {e}") from e

    def publish_batch(self, limit: Optional[int] = None, tier: str = 'all', dry_run: bool = False, workers: int = 1) -> Dict[str, int]:
        """
        Publish a batch of ready content

        Args:
            limit: Maximum number of items to publish (None = all ready)
            tier: Subscriber tier ('all', 'free', 'paid')
            dry_run: If True, validate without sending
            workers: Number of parallel workers (currently not used, for future parallelization)

        Returns:
            Dictionary with keys 'published' and 'failed'

        Raises:
            DatabaseError: If database connection fails
        """
        if not self.db_connection:
            raise DatabaseError("No database connection available")

        items = self.get_ready_content(limit=limit, tier=tier)
        stats = {'published': 0, 'failed': 0, 'total': len(items)}

        for idx, item in enumerate(items, 1):
            label = f"{item['ticker']} ({item['filing_type']})"
            try:
                audience_filter = {'tier': tier} if tier != 'all' else None

                result = self.publish(
                    item['content_id'],
                    channel=PublishChannel.EMAIL_NEWSLETTER,
                    audience_filter=audience_filter,
                    dry_run=dry_run,
                )

                if not dry_run and result.status == PublishStatus.SENT:
                    # Record the delivery and mark published in one transaction.
                    # These were two independent commits, so a crash between
                    # them left content that had been mailed but still looked
                    # unpublished -- and would be mailed again next run.
                    from ..db import (
                        ContentRepository,
                        DeliveryRecord,
                        DeliveryRepository,
                        transaction,
                    )

                    with transaction(self.db_connection):
                        DeliveryRepository(self.db_connection).record(
                            DeliveryRecord(
                                content_id=item['content_id'],
                                status=result.status.value,
                                sent_at=result.delivered_at,
                                resend_email_id=result.external_id,
                                metadata={
                                    'channel': result.channel.value,
                                    'recipient_count': result.recipient_count,
                                    'tier': tier,
                                },
                            )
                        )
                        ContentRepository(self.db_connection).mark_published(
                            item['content_id']
                        )

                stats['published'] += 1
                state = "validated" if dry_run else "published"
                print(f"  [{idx}/{len(items)}] \u2713 {label} {state} successfully")
            except Exception as e:
                stats['failed'] += 1
                print(f"  [{idx}/{len(items)}] \u2717 {label} - {str(e)[:200]}")
                if self.logger:
                    self.logger.error(
                        f"Failed to publish {label}",
                        exception=e,
                        extra={'content_id': item['content_id']},
                    )

        return stats
