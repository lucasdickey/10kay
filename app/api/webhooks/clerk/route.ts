/**
 * Clerk Webhook Handler
 *
 * Handles user lifecycle events from Clerk:
 * - user.created: Create subscriber record when user signs up
 * - user.updated: Update subscriber email if changed
 * - user.deleted: Mark subscriber as deleted (soft delete)
 *
 * Documentation: https://clerk.com/docs/integrations/webhooks/overview
 */

import { NextRequest, NextResponse } from 'next/server';
import { headers } from 'next/headers';
import { Webhook } from 'svix';
import { WebhookEvent } from '@clerk/nextjs/server';
import { createSubscriber, getUserPreferencesByClerkId } from '@/lib/db-preferences';
import { query } from '@/lib/db';

// Disable caching for this route
export const dynamic = 'force-dynamic';
export const runtime = 'nodejs';

export async function POST(request: NextRequest) {
  // Get the Svix headers for verification
  const headerPayload = await headers();
  const svix_id = headerPayload.get('svix-id');
  const svix_timestamp = headerPayload.get('svix-timestamp');
  const svix_signature = headerPayload.get('svix-signature');

  // If there are no Svix headers, error out
  if (!svix_id || !svix_timestamp || !svix_signature) {
    return NextResponse.json(
      { error: 'Missing Svix headers' },
      { status: 400 }
    );
  }

  // Get the webhook secret from environment
  const webhookSecret = process.env.CLERK_WEBHOOK_SECRET;

  if (!webhookSecret) {
    console.error('CLERK_WEBHOOK_SECRET not configured');
    return NextResponse.json(
      { error: 'Webhook secret not configured' },
      { status: 500 }
    );
  }

  // Get the body
  const payload = await request.json();
  const body = JSON.stringify(payload);

  // Create a new Svix instance with your webhook secret
  const wh = new Webhook(webhookSecret);

  let evt: WebhookEvent;

  // Verify the webhook signature
  try {
    evt = wh.verify(body, {
      'svix-id': svix_id,
      'svix-timestamp': svix_timestamp,
      'svix-signature': svix_signature,
    }) as WebhookEvent;
  } catch (err) {
    console.error('Webhook verification failed:', err);
    return NextResponse.json(
      { error: 'Invalid signature' },
      { status: 400 }
    );
  }

  // Handle the webhook event
  const eventType = evt.type;

  console.log(`Received Clerk webhook: ${eventType}`);

  try {
    switch (eventType) {
      case 'user.created': {
        const { id, email_addresses } = evt.data;
        const primaryEmail = email_addresses.find(e => e.id === evt.data.primary_email_address_id);

        if (!primaryEmail?.email_address) {
          console.error('No primary email found for user:', id);
          return NextResponse.json(
            { error: 'No primary email found' },
            { status: 400 }
          );
        }

        console.log(`Creating subscriber for user ${id} (${primaryEmail.email_address})`);

        // Check if subscriber already exists (shouldn't happen, but just in case)
        const existing = await getUserPreferencesByClerkId(id);
        if (existing) {
          console.log('Subscriber already exists, skipping creation');
          return NextResponse.json({
            message: 'Subscriber already exists',
            subscriber_id: existing.id
          });
        }

        // Create new subscriber
        const subscriber = await createSubscriber(primaryEmail.email_address, id);

        console.log(`Successfully created subscriber ${subscriber.id}`);

        return NextResponse.json({
          message: 'Subscriber created',
          subscriber_id: subscriber.id,
        });
      }

      case 'user.updated': {
        const { id, email_addresses } = evt.data;
        const primaryEmail = email_addresses.find(e => e.id === evt.data.primary_email_address_id);

        if (!primaryEmail?.email_address) {
          console.error('No primary email found for user:', id);
          return NextResponse.json(
            { error: 'No primary email found' },
            { status: 400 }
          );
        }

        console.log(`Updating subscriber for user ${id}`);

        // Update email if it changed
        await query(
          `UPDATE subscribers
           SET email = $1, updated_at = NOW()
           WHERE clerk_user_id = $2`,
          [primaryEmail.email_address, id]
        );

        console.log(`Successfully updated subscriber email`);

        return NextResponse.json({
          message: 'Subscriber updated',
        });
      }

      case 'user.deleted': {
        const { id } = evt.data;

        console.log(`Marking subscriber as deleted for user ${id}`);

        // Soft delete - set unsubscribed_at timestamp
        await query(
          `UPDATE subscribers
           SET unsubscribed_at = NOW(), updated_at = NOW()
           WHERE clerk_user_id = $1 AND unsubscribed_at IS NULL`,
          [id]
        );

        console.log(`Successfully marked subscriber as deleted`);

        return NextResponse.json({
          message: 'Subscriber marked as deleted',
        });
      }

      default:
        console.log(`Unhandled event type: ${eventType}`);
        return NextResponse.json({
          message: `Event type ${eventType} not handled`,
        });
    }
  } catch (error) {
    console.error('Error handling webhook:', error);
    return NextResponse.json(
      { error: 'Internal server error' },
      { status: 500 }
    );
  }
}
