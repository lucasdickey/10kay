/**
 * DEV ONLY: Manually sync current Clerk user to database
 * This simulates what the Phase 3.5 webhook will do automatically
 *
 * DELETE THIS FILE after Phase 3.5 is complete!
 */

import { auth, currentUser } from "@clerk/nextjs/server";
import { NextResponse } from "next/server";
import { createSubscriber, getUserPreferencesByClerkId } from "@/lib/db-preferences";

export async function POST() {
  // Only allow in development
  if (process.env.NODE_ENV === 'production') {
    return NextResponse.json(
      { success: false, error: "This endpoint is only available in development" },
      { status: 403 }
    );
  }

  try {
    const { userId } = await auth();

    if (!userId) {
      return NextResponse.json(
        { success: false, error: "Not authenticated" },
        { status: 401 }
      );
    }

    // Check if user already exists
    const existing = await getUserPreferencesByClerkId(userId);
    if (existing) {
      return NextResponse.json({
        success: true,
        message: "User already exists in database",
        data: existing,
      });
    }

    // Get user email from Clerk
    const user = await currentUser();
    const email = user?.emailAddresses[0]?.emailAddress;

    if (!email) {
      return NextResponse.json(
        { success: false, error: "No email found for user" },
        { status: 400 }
      );
    }

    // Create subscriber record
    const subscriber = await createSubscriber(email, userId);

    return NextResponse.json({
      success: true,
      message: "User successfully synced to database!",
      data: subscriber,
    });
  } catch (error) {
    console.error("Error syncing user:", error);
    return NextResponse.json(
      { success: false, error: "Failed to sync user" },
      { status: 500 }
    );
  }
}
