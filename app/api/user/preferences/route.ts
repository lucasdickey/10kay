import { auth, currentUser } from '@clerk/nextjs/server';
import { NextResponse } from 'next/server';
import {
  getUserPreferencesByClerkId,
  getUserPreferencesByEmail,
  updateUserPreferences,
  createSubscriber,
} from '@/lib/db-preferences';
import { UpdateUserPreferences } from '@/lib/types';
import { query } from '@/lib/db';

/**
 * GET /api/user/preferences
 * Fetch current user's preferences
 */
export async function GET() {
  try {
    const { userId } = await auth();

    if (!userId) {
      return NextResponse.json(
        { success: false, error: 'Unauthorized' },
        { status: 401 }
      );
    }

    let preferences = await getUserPreferencesByClerkId(userId);

    // If user preferences don't exist, create them on the fly
    // This handles cases where the webhook might be delayed
    if (!preferences) {
      const user = await currentUser();
      if (!user) {
        return NextResponse.json(
          { success: false, error: 'User not found' },
          { status: 404 }
        );
      }

      const primaryEmail = user.emailAddresses.find(
        e => e.id === user.primaryEmailAddressId
      );

      if (!primaryEmail) {
        return NextResponse.json(
          { success: false, error: 'Primary email not found for user' },
          { status: 400 }
        );
      }

      console.log(
        `User preferences not found for ${userId}, creating new subscriber record.`
      );
      try {
        preferences = await createSubscriber(primaryEmail.emailAddress, userId);
      } catch (error) {
        // Creation failed - could be duplicate email or race condition
        console.log('Failed to create subscriber, checking if email already exists...');

        // Check if subscriber exists by email
        const existingByEmail = await getUserPreferencesByEmail(primaryEmail.emailAddress);

        if (existingByEmail && !existingByEmail.clerk_user_id) {
          // Link existing subscriber to this Clerk user
          console.log(`Linking existing subscriber ${existingByEmail.id} to Clerk user ${userId}`);
          await query(
            `UPDATE subscribers SET clerk_user_id = $1, updated_at = NOW() WHERE id = $2`,
            [userId, existingByEmail.id]
          );
          preferences = await getUserPreferencesByClerkId(userId);
        } else if (existingByEmail && existingByEmail.clerk_user_id) {
          // Webhook or another process just created it with the clerk_user_id
          console.log('Subscriber was created by concurrent process, refetching...');
          preferences = await getUserPreferencesByClerkId(userId);
        }

        if (!preferences) {
          // If we still don't have preferences, something is very wrong
          console.error('Failed to create or link subscriber:', error);
          return NextResponse.json(
            { success: false, error: 'Failed to create or find user account.' },
            { status: 500 }
          );
        }
      }
    }

    return NextResponse.json({
      success: true,
      data: preferences,
    });
  } catch (error) {
    console.error('Error fetching user preferences:', error);
    return NextResponse.json(
      { success: false, error: 'Internal server error' },
      { status: 500 }
    );
  }
}

/**
 * POST /api/user/preferences
 * Update current user's preferences
 */
export async function POST(request: Request) {
  try {
    const { userId } = await auth();

    if (!userId) {
      return NextResponse.json(
        { success: false, error: "Unauthorized" },
        { status: 401 }
      );
    }

    const updates: UpdateUserPreferences = await request.json();

    // Validate updates
    if (updates.email_frequency && !['daily', 'per_filing', 'disabled'].includes(updates.email_frequency)) {
      return NextResponse.json(
        { success: false, error: "Invalid email frequency" },
        { status: 400 }
      );
    }

    if (updates.content_preference && !['tldr', 'full'].includes(updates.content_preference)) {
      return NextResponse.json(
        { success: false, error: "Invalid content preference" },
        { status: 400 }
      );
    }

    // Check if user exists
    let preferences = await getUserPreferencesByClerkId(userId);

    if (!preferences) {
      return NextResponse.json(
        {
          success: false,
          error: "User not found in database. Webhook sync required.",
        },
        { status: 404 }
      );
    }

    // Update preferences
    const updatedPreferences = await updateUserPreferences(userId, updates);

    return NextResponse.json({
      success: true,
      data: updatedPreferences,
    });
  } catch (error) {
    console.error("Error updating user preferences:", error);
    return NextResponse.json(
      { success: false, error: "Internal server error" },
      { status: 500 }
    );
  }
}
