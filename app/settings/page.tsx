'use client';

import { useEffect, useState } from 'react';
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
          interested_companies: result.data.interested_companies,
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

  async function handleSave() {
    setSaving(true);
    setMessage(null);

    try {
      const updates: UpdateUserPreferences = {
        email_enabled: formData.email_enabled,
        email_frequency: formData.email_frequency as 'daily' | 'per_filing' | 'disabled',
        content_preference: formData.content_preference as 'tldr' | 'full',
        delivery_time: formData.delivery_time,
        interested_companies: formData.interested_companies,
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
          text: 'Preferences saved successfully!',
        });
        // Clear message after 3 seconds
        setTimeout(() => setMessage(null), 3000);
      } else {
        setMessage({
          type: 'error',
          text: result.error || 'Failed to save preferences',
        });
      }
    } catch (error) {
      console.error('Error saving preferences:', error);
      setMessage({
        type: 'error',
        text: 'Failed to save preferences',
      });
    } finally {
      setSaving(false);
    }
  }

  function handleFieldChange(field: string, value: any) {
    setFormData((prev) => ({ ...prev, [field]: value }));
  }

  const hasChanges = JSON.stringify(formData) !== JSON.stringify({
    email_enabled: preferences?.email_enabled,
    email_frequency: preferences?.email_frequency,
    content_preference: preferences?.content_preference,
    delivery_time: preferences?.delivery_time,
    interested_companies: preferences?.interested_companies,
  });

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

        {/* No Preferences Warning */}
        {!preferences && (
          <div className="mb-6 bg-yellow-50 border border-yellow-200 rounded-lg p-4">
            <p className="text-sm text-yellow-800">
              <strong>Account Not Synced:</strong> Your account hasn't been synced to the database yet.
              This will be automatic once Phase 3.5 (Webhook Integration) is complete.
              In the meantime, you can sign out and sign back in, or contact support.
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

          {/* Save Button */}
          <div className="flex items-center justify-between bg-white rounded-lg shadow p-6">
            <div className="text-sm text-gray-600">
              {hasChanges ? (
                <span className="text-yellow-600">● You have unsaved changes</span>
              ) : (
                <span className="text-green-600">✓ All changes saved</span>
              )}
            </div>
            <button
              onClick={handleSave}
              disabled={!hasChanges || saving || !preferences}
              className={`px-6 py-2 rounded-lg font-medium transition-colors ${
                !hasChanges || saving || !preferences
                  ? 'bg-gray-300 text-gray-500 cursor-not-allowed'
                  : 'bg-blue-600 text-white hover:bg-blue-700'
              }`}
            >
              {saving ? 'Saving...' : 'Save Preferences'}
            </button>
          </div>
        </div>
      </main>
    </div>
  );
}
