'use client';

import { UserPreferences } from '@/lib/types';

interface EmailPreferencesFormProps {
  preferences: UserPreferences | null;
  onChange: (field: string, value: any) => void;
}

export function EmailPreferencesForm({ preferences, onChange }: EmailPreferencesFormProps) {
  if (!preferences) {
    return (
      <div className="text-gray-500">Loading preferences...</div>
    );
  }

  const isPaidTier = preferences.subscription_tier === 'paid';

  return (
    <div className="space-y-6">
      {/* Email Notifications Toggle */}
      <div className="flex items-start gap-3">
        <div className="flex items-center h-6">
          <input
            type="checkbox"
            id="email_enabled"
            checked={preferences.email_enabled}
            onChange={(e) => onChange('email_enabled', e.target.checked)}
            className="w-5 h-5 text-blue-600 rounded focus:ring-blue-500"
          />
        </div>
        <div className="flex-1">
          <label htmlFor="email_enabled" className="font-medium text-gray-900 cursor-pointer">
            Enable Email Notifications
          </label>
          <p className="text-sm text-gray-600 mt-1">
            Receive email updates for the companies you're following
          </p>
        </div>
      </div>

      {/* Email Frequency */}
      <div>
        <label className="block font-medium text-gray-900 mb-2">
          Email Frequency
        </label>
        <div className="space-y-2">
          <label className="flex items-start gap-3 p-3 border rounded-lg hover:bg-gray-50 cursor-pointer transition-colors">
            <input
              type="radio"
              name="email_frequency"
              value="daily"
              checked={preferences.email_frequency === 'daily'}
              onChange={(e) => onChange('email_frequency', e.target.value)}
              className="mt-1 w-4 h-4 text-blue-600 focus:ring-blue-500"
            />
            <div className="flex-1">
              <div className="font-medium text-gray-900">Daily Digest</div>
              <p className="text-sm text-gray-600">
                Receive a single email each day with all new analyses
              </p>
            </div>
          </label>

          <label className="flex items-start gap-3 p-3 border rounded-lg hover:bg-gray-50 cursor-pointer transition-colors">
            <input
              type="radio"
              name="email_frequency"
              value="per_filing"
              checked={preferences.email_frequency === 'per_filing'}
              onChange={(e) => onChange('email_frequency', e.target.value)}
              className="mt-1 w-4 h-4 text-blue-600 focus:ring-blue-500"
            />
            <div className="flex-1">
              <div className="font-medium text-gray-900">Per Filing</div>
              <p className="text-sm text-gray-600">
                Receive an email immediately when each new filing is analyzed
              </p>
            </div>
          </label>

          <label className="flex items-start gap-3 p-3 border rounded-lg hover:bg-gray-50 cursor-pointer transition-colors">
            <input
              type="radio"
              name="email_frequency"
              value="disabled"
              checked={preferences.email_frequency === 'disabled'}
              onChange={(e) => onChange('email_frequency', e.target.value)}
              className="mt-1 w-4 h-4 text-blue-600 focus:ring-blue-500"
            />
            <div className="flex-1">
              <div className="font-medium text-gray-900">Disabled</div>
              <p className="text-sm text-gray-600">
                Don't send any automated emails (you can still access content on the website)
              </p>
            </div>
          </label>
        </div>
      </div>

      {/* Content Preference */}
      <div>
        <label className="block font-medium text-gray-900 mb-2">
          Email Content
        </label>
        <div className="space-y-2">
          <label className="flex items-start gap-3 p-3 border rounded-lg hover:bg-gray-50 cursor-pointer transition-colors">
            <input
              type="radio"
              name="content_preference"
              value="tldr"
              checked={preferences.content_preference === 'tldr'}
              onChange={(e) => onChange('content_preference', e.target.value)}
              className="mt-1 w-4 h-4 text-blue-600 focus:ring-blue-500"
            />
            <div className="flex-1">
              <div className="font-medium text-gray-900">TLDR Only (Free)</div>
              <p className="text-sm text-gray-600">
                Executive summary and key takeaways
              </p>
            </div>
          </label>

          <label className={`flex items-start gap-3 p-3 border rounded-lg transition-colors ${
            isPaidTier ? 'hover:bg-gray-50 cursor-pointer' : 'opacity-60 cursor-not-allowed bg-gray-50'
          }`}>
            <input
              type="radio"
              name="content_preference"
              value="full"
              checked={preferences.content_preference === 'full'}
              onChange={(e) => isPaidTier && onChange('content_preference', e.target.value)}
              disabled={!isPaidTier}
              className="mt-1 w-4 h-4 text-blue-600 focus:ring-blue-500 disabled:opacity-50"
            />
            <div className="flex-1">
              <div className="font-medium text-gray-900 flex items-center gap-2">
                Full Analysis (Premium)
                {!isPaidTier && (
                  <span className="text-xs px-2 py-0.5 bg-yellow-100 text-yellow-800 rounded">
                    Upgrade Required
                  </span>
                )}
              </div>
              <p className="text-sm text-gray-600">
                Complete deep dive with opportunities, risks, and strategic analysis
              </p>
            </div>
          </label>
        </div>
      </div>

      {/* Delivery Time (for daily digest) */}
      {preferences.email_frequency === 'daily' && (
        <div>
          <label htmlFor="delivery_time" className="block font-medium text-gray-900 mb-2">
            Preferred Delivery Time
          </label>
          <select
            id="delivery_time"
            value={preferences.delivery_time}
            onChange={(e) => onChange('delivery_time', e.target.value)}
            className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="06:00:00">6:00 AM EST</option>
            <option value="07:00:00">7:00 AM EST</option>
            <option value="08:00:00">8:00 AM EST (Default)</option>
            <option value="09:00:00">9:00 AM EST</option>
            <option value="10:00:00">10:00 AM EST</option>
            <option value="12:00:00">12:00 PM EST</option>
            <option value="15:00:00">3:00 PM EST</option>
            <option value="18:00:00">6:00 PM EST</option>
          </select>
          <p className="text-sm text-gray-500 mt-1">
            Your daily digest will be sent at approximately this time (Eastern Time)
          </p>
        </div>
      )}

      {/* Info Banner */}
      <div className="bg-gray-50 border border-gray-200 rounded-lg p-4">
        <p className="text-sm text-gray-700">
          💡 <strong>Tip:</strong> You can always update these preferences later or unsubscribe from any email.
        </p>
      </div>
    </div>
  );
}
