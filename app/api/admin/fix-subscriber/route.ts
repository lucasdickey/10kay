/**
 * Admin endpoint to fix subscriber linking
 * GET: Check subscriber status
 * POST: Fix subscriber link to current user
 */

import { auth, currentUser } from '@clerk/nextjs/server';
import { NextResponse } from 'next/server';
import { query } from '@/lib/db';

export const dynamic = 'force-dynamic';

/**
 * GET: Check subscriber status for current user
 */
export async function GET() {
  try {
    const { userId } = await auth();

    if (!userId) {
      return NextResponse.json(
        { error: 'Unauthorized' },
        { status: 401 }
      );
    }

    const user = await currentUser();
    if (!user) {
      return NextResponse.json(
        { error: 'User not found' },
        { status: 404 }
      );
    }

    const primaryEmail = user.emailAddresses.find(
      e => e.id === user.primaryEmailAddressId
    );

    if (!primaryEmail) {
      return NextResponse.json(
        { error: 'Primary email not found' },
        { status: 400 }
      );
    }

    // Check if subscriber exists by email
    const subscriberByEmail = await query(
      `SELECT id, email, clerk_user_id, subscription_tier, created_at
       FROM subscribers
       WHERE email = $1`,
      [primaryEmail.emailAddress]
    );

    // Check if subscriber exists by clerk_user_id
    const subscriberByClerkId = await query(
      `SELECT id, email, clerk_user_id, subscription_tier, created_at
       FROM subscribers
       WHERE clerk_user_id = $1`,
      [userId]
    );

    return NextResponse.json({
      currentUser: {
        clerkUserId: userId,
        email: primaryEmail.emailAddress,
      },
      subscriberByEmail: subscriberByEmail[0] || null,
      subscriberByClerkId: subscriberByClerkId[0] || null,
      needsFix: subscriberByEmail.length > 0 &&
                subscriberByEmail[0].clerk_user_id !== userId,
    });
  } catch (error) {
    console.error('Error checking subscriber:', error);
    return NextResponse.json(
      { error: 'Internal server error' },
      { status: 500 }
    );
  }
}

/**
 * POST: Fix subscriber link - update subscriber to current user's clerk_user_id
 */
export async function POST() {
  try {
    const { userId } = await auth();

    if (!userId) {
      return NextResponse.json(
        { error: 'Unauthorized' },
        { status: 401 }
      );
    }

    const user = await currentUser();
    if (!user) {
      return NextResponse.json(
        { error: 'User not found' },
        { status: 404 }
      );
    }

    const primaryEmail = user.emailAddresses.find(
      e => e.id === user.primaryEmailAddressId
    );

    if (!primaryEmail) {
      return NextResponse.json(
        { error: 'Primary email not found' },
        { status: 400 }
      );
    }

    // Update subscriber to link to current user
    const result = await query(
      `UPDATE subscribers
       SET clerk_user_id = $1, updated_at = NOW()
       WHERE email = $2
       RETURNING id, email, clerk_user_id, subscription_tier`,
      [userId, primaryEmail.emailAddress]
    );

    if (result.length === 0) {
      return NextResponse.json(
        { error: 'No subscriber found with that email' },
        { status: 404 }
      );
    }

    return NextResponse.json({
      message: 'Subscriber successfully linked to your account',
      subscriber: result[0],
    });
  } catch (error) {
    console.error('Error fixing subscriber:', error);
    return NextResponse.json(
      { error: 'Internal server error' },
      { status: 500 }
    );
  }
}
