'use client';

import React, { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@clerk/nextjs';
import Link from 'next/link';
import { UserPreferences, UpdateUserPreferences } from '@/lib/types';
import { CompanySelector } from '@/components/CompanySelector';
import { EmailPreferencesForm } from '@/components/EmailPreferencesForm';

export default function SettingsPage() {
  const { isLoaded, isSignedIn } = useAuth();
  const router = useRouter();

  const [preferences, setPreferences] = useState<UserPreferences | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  const [formData, setFormData] = useState<Partial<UserPreferences>>({});

  useEffect(() => {
    if (isLoaded && !isSignedIn) {
      router.push('/');
    } else if (isSignedIn) {
      fetchPreferences();
    }
  }, [isLoaded, isSignedIn, router]);

  async function fetchPreferences() {
    try {
      const response = await fetch('/api/user/preferences');
      const result = await response.json();

      if (result.success) {
        setPreferences(result.data);
        setFormData({
          email_enabled: result.data.email_enabled,
          email_frequency: result.data.email_frequency,
          content_preference: result.data.content_preference,
          delivery_time: result.data.delivery_time,
          interested_companies: result.data.interested_companies || [],
        });
      } else {
        setMessage({
          type: 'error',
          text: result.error || 'Failed to load preferences. Please ensure your account is synced.',
        });
      }
    } catch (error) {
      console.error('Error fetching preferences:', error);
      setMessage({
        type: 'error',
        text: 'Failed to load preferences',
      });
    } finally {
      setLoading(false);
    }
  }

  async function handleSync() {
    setLoading(true);
    setMessage(null);

    try {
      const response = await fetch('/api/dev/sync-user', {
        method: 'POST',
      });

      const result = await response.json();

      if (result.success) {
        setMessage({
          type: 'success',
          text: 'Account synced successfully! Reloading...',
        });
        // Reload preferences after sync
        setTimeout(() => {
          fetchPreferences();
        }, 1000);
      } else {
        setMessage({
          type: 'error',
          text: result.error || 'Failed to sync account',
        });
      }
    } catch (error) {
      console.error('Error syncing user:', error);
      setMessage({
        type: 'error',
        text: 'Failed to sync account',
      });
    } finally {
      setLoading(false);
    }
  }

  function handleFieldChange(field: string, value: any) {
    const updatedFormData = { ...formData, [field]: value };
    setFormData(updatedFormData);

    // Auto-save after field change
    autoSave(updatedFormData);
  }

  // Debounced auto-save function
  const autoSaveTimeoutRef = React.useRef<NodeJS.Timeout | null>(null);

  async function autoSave(data: Partial<UserPreferences>) {
    // Clear existing timeout
    if (autoSaveTimeoutRef.current) {
      clearTimeout(autoSaveTimeoutRef.current);
    }

    // Set new timeout to save after 500ms of no changes
    autoSaveTimeoutRef.current = setTimeout(async () => {
      if (!preferences) return;

      setSaving(true);
      setMessage(null);

      try {
        const updates: UpdateUserPreferences = {
          email_enabled: data.email_enabled,
          email_frequency: data.email_frequency as 'daily' | 'per_filing' | 'disabled',
          content_preference: data.content_preference as 'tldr' | 'full',
          delivery_time: data.delivery_time,
          interested_companies: data.interested_companies,
        };

        const response = await fetch('/api/user/preferences', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(updates),
        });

        const result = await response.json();

        if (result.success) {
          setPreferences(result.data);
          setMessage({
            type: 'success',
            text: 'Saved!',
          });
          // Clear success message after 2 seconds
          setTimeout(() => setMessage(null), 2000);
        } else {
          setMessage({
            type: 'error',
            text: result.error || 'Failed to save',
          });
        }
      } catch (error) {
        console.error('Error auto-saving preferences:', error);
        setMessage({
          type: 'error',
          text: 'Failed to save',
        });
      } finally {
        setSaving(false);
      }
    }, 500);
  }

  if (!isLoaded || !isSignedIn) {
    return null;
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-gray-600">Loading...</div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white border-b">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-2xl font-bold text-gray-900">Newsletter Settings</h1>
              <p className="text-sm text-gray-600 mt-1">
                Customize your 10KAY email preferences and company selections
              </p>
            </div>
            <Link
              href="/dashboard"
              className="text-sm text-blue-600 hover:text-blue-700 transition-colors"
            >
              ← Back to Dashboard
            </Link>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Alert Messages */}
        {message && (
          <div
            className={`mb-6 p-4 rounded-lg ${
              message.type === 'success'
                ? 'bg-green-50 border border-green-200 text-green-800'
                : 'bg-red-50 border border-red-200 text-red-800'
            }`}
          >
            {message.text}
          </div>
        )}

        {/* No Preferences Warning - DEV ONLY */}
        {!preferences && process.env.NODE_ENV === 'development' && (
          <div className="mb-6 bg-yellow-50 border border-yellow-200 rounded-lg p-4">
            <div className="flex items-start justify-between gap-4">
              <div className="flex-1">
                <p className="text-sm text-yellow-800 font-semibold mb-2">
                  [DEV] Account Not Synced
                </p>
                <p className="text-sm text-yellow-700 mb-3">
                  Your account hasn't been synced to the database yet. In production, this happens
                  automatically via Clerk webhooks.
                </p>
                <p className="text-sm text-yellow-700">
                  For development testing, click the button below to manually sync.
                </p>
              </div>
              <button
                onClick={handleSync}
                disabled={loading}
                className="px-4 py-2 bg-yellow-600 text-white rounded-lg font-medium hover:bg-yellow-700 transition-colors whitespace-nowrap disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {loading ? 'Syncing...' : 'Sync Now'}
              </button>
            </div>
          </div>
        )}

        {/* No Preferences Error - PRODUCTION */}
        {!preferences && process.env.NODE_ENV === 'production' && (
          <div className="mb-6 bg-red-50 border border-red-200 rounded-lg p-4">
            <p className="text-sm text-red-800 font-semibold mb-2">
              Account Sync Error
            </p>
            <p className="text-sm text-red-700">
              Your account could not be loaded. Please try signing out and signing back in.
              If the problem persists, contact support.
            </p>
          </div>
        )}

        <div className="space-y-8">
          {/* Email Preferences Section */}
          <section className="bg-white rounded-lg shadow p-6">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">Email Preferences</h2>
            <EmailPreferencesForm
              preferences={formData as UserPreferences}
              onChange={handleFieldChange}
            />
          </section>

          {/* Company Selection Section */}
          <section className="bg-white rounded-lg shadow p-6">
            <h2 className="text-lg font-semibold text-gray-900 mb-2">Companies to Follow</h2>
            <p className="text-sm text-gray-600 mb-4">
              Select which companies you want to receive analyses for. You're following {formData.interested_companies?.length || 0} of 47 companies.
            </p>
            <CompanySelector
              selectedCompanyIds={formData.interested_companies || []}
              onChange={(ids) => handleFieldChange('interested_companies', ids)}
            />
          </section>

          {/* Auto-save Status */}
          <div className="flex items-center justify-center bg-white rounded-lg shadow p-4">
            <div className="text-sm text-gray-600 flex items-center gap-2">
              {saving ? (
                <>
                  <svg className="animate-spin h-4 w-4 text-blue-600" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                  </svg>
                  <span>Saving...</span>
                </>
              ) : (
                <>
                  <svg className="h-4 w-4 text-green-600" fill="currentColor" viewBox="0 0 20 20">
                    <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                  </svg>
                  <span className="text-green-600">Changes saved automatically</span>
                </>
              )}
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
