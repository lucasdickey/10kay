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

        try:
            cursor = self.db_connection.cursor()

            cursor.execute("""
                SELECT
                    COALESCE(c.key_takeaways->>'headline', c.executive_summary),
                    c.email_html,
                    co.ticker,
                    co.name as company_name,
                    f.filing_type,
                    f.fiscal_year
                FROM content c
                JOIN filings f ON c.filing_id = f.id
                JOIN companies co ON f.company_id = co.id
                WHERE c.id = %s
            """, (content_id,))

            row = cursor.fetchone()
            cursor.close()

            if not row:
                raise FetchError(f"Content {content_id} not found")

            return {
                'headline': row[0],
                'email_html': row[1],
                'ticker': row[2],
                'company_name': row[3],
                'filing_type': row[4],
                'fiscal_period': row[5],
                'fiscal_year': row[6]
            }

        except Exception as e:
            raise FetchError(f"Failed to fetch content: {e}")

    def get_audience(
        self,
        channel: PublishChannel,
        filter: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Get target audience for email newsletter

        Args:
            channel: Distribution channel (must be EMAIL_NEWSLETTER)
            filter: Optional audience filters (tier, enabled, topics)

        Returns:
            List of subscriber dictionaries

        Raises:
            FetchError: If fetching fails
        """
        if channel != PublishChannel.EMAIL_NEWSLETTER:
            raise FetchError(f"Unsupported channel: {channel}")

        if not self.db_connection:
            raise FetchError("No database connection available")

        filter = filter or {}

        try:
            cursor = self.db_connection.cursor()

            # Build query with filters
            query = """
                SELECT
                    id,
                    email,
                    first_name,
                    subscription_tier,
                    topics_subscribed
                FROM subscribers
                WHERE enabled = true
            """
            params = []

            # Filter by tier
            if 'tier' in filter:
                query += " AND subscription_tier = %s"
                params.append(filter['tier'])

            # Filter by topics (interested in specific companies)
            if 'topics' in filter:
                query += " AND topics_subscribed @> %s::jsonb"
                params.append(json.dumps(filter['topics']))

            cursor.execute(query, params)

            subscribers = []
            for row in cursor.fetchall():
                subscribers.append({
                    'id': row[0],
                    'email': row[1],
                    'first_name': row[2],
                    'tier': row[3],
                    'topics': row[4] or []
                })

            cursor.close()

            if self.logger:
                self.logger.info(
                    f"Found {len(subscribers)} subscribers",
                    extra={'filter': filter}
                )

            return subscribers

        except Exception as e:
            raise FetchError(f"Failed to fetch audience: {e}")

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

    def save_delivery_record(self, result: PublishResult):
        """
        Save email delivery records to database

        Args:
            result: PublishResult to save

        Raises:
            DatabaseError: If save fails
        """
        if not self.db_connection:
            raise DatabaseError("No database connection available")

        try:
            cursor = self.db_connection.cursor()

            # Insert email delivery record for batch
            # In a real implementation, we'd insert individual records per subscriber
            # For now, we'll create a single batch record

            cursor.execute("""
                INSERT INTO email_deliveries (
                    content_id,
                    subscriber_id,
                    status,
                    sent_at,
                    resend_email_id,
                    metadata
                )
                VALUES (%s, NULL, %s, %s, %s, %s)
                RETURNING id
            """, (
                result.content_id,
                result.status.value,
                result.delivered_at,
                result.external_id,
                json.dumps(result.metadata) if result.metadata else None
            ))

            delivery_id = cursor.fetchone()[0]
            self.db_connection.commit()
            cursor.close()

            if self.logger:
                self.logger.info(
                    f"Saved email delivery record",
                    extra={
                        'delivery_id': delivery_id,
                        'content_id': result.content_id,
                        'recipients': result.recipient_count
                    }
                )

        except Exception as e:
            self.db_connection.rollback()
            raise DatabaseError(f"Failed to save delivery record: {e}")

    def count_ready_content(self) -> int:
        """
        Count the number of content items ready for publishing

        Returns:
            Number of content records with status='generated'

        Raises:
            DatabaseError: If database query fails
        """
        if not self.db_connection:
            raise DatabaseError("No database connection available")

        try:
            cursor = self.db_connection.cursor()
            cursor.execute("SELECT COUNT(*) FROM content WHERE status = 'generated'")
            count = cursor.fetchone()[0]
            cursor.close()
            return count
        except Exception as e:
            raise DatabaseError(f"Failed to count ready content: {e}")

    def get_ready_content(self, limit: Optional[int] = None, tier: str = 'all') -> List[Dict[str, Any]]:
        """
        Get content ready for publishing from database

        Args:
            limit: Maximum number of items to return (None = all)
            tier: Subscriber tier to filter by ('all', 'free', 'paid')

        Returns:
            List of content dictionaries with keys: content_id, filing_id, ticker, filing_type

        Raises:
            DatabaseError: If database query fails
        """
        if not self.db_connection:
            raise DatabaseError("No database connection available")

        try:
            cursor = self.db_connection.cursor()

            query = """
                SELECT c.id as content_id, f.id as filing_id, co.ticker, f.filing_type
                FROM content c
                JOIN filings f ON c.filing_id = f.id
                JOIN companies co ON f.company_id = co.id
                WHERE c.status = 'generated'
                ORDER BY c.created_at DESC
            """

            if limit:
                query += f" LIMIT {limit}"

            cursor.execute(query)
            columns = ['content_id', 'filing_id', 'ticker', 'filing_type']
            items = [dict(zip(columns, row)) for row in cursor.fetchall()]
            cursor.close()

            return items
        except Exception as e:
            raise DatabaseError(f"Failed to get ready content: {e}")

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
        published_count = 0
        failed_count = 0

        for idx, item in enumerate(items, 1):
            try:
                self.publish(item['content_id'], tier=tier, dry_run=dry_run)
                published_count += 1
                status = "validated" if dry_run else "published"
                print(f"  [{idx}/{len(items)}] ✓ {item['ticker']} ({item['filing_type']}) {status} successfully")
            except Exception as e:
                failed_count += 1
                error_msg = str(e)[:200]  # Truncate long errors
                print(f"  [{idx}/{len(items)}] ✗ {item['ticker']} ({item['filing_type']}) - {error_msg}")
                if self.logger:
                    self.logger.error(f"Failed to publish {item['ticker']}: {e}")

        return {'published': published_count, 'failed': failed_count}
