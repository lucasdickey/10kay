/**
 * TypeScript types for 10KAY application
 */

// User preferences and subscription management
export interface UserPreferences {
  id: string;
  email: string;
  clerk_user_id: string | null;
  subscription_tier: 'free' | 'paid';
  stripe_customer_id: string | null;
  stripe_subscription_id: string | null;
  subscription_status: string | null;
  email_frequency: 'daily' | 'per_filing' | 'disabled';
  interested_companies: string[]; // Array of company UUIDs
  email_enabled: boolean;
  content_preference: 'tldr' | 'full';
  delivery_time: string; // HH:MM:SS format
  subscribed_at: string;
  unsubscribed_at: string | null;
  last_email_sent_at: string | null;
  created_at: string;
  updated_at: string;
}

// Partial update for user preferences
export interface UpdateUserPreferences {
  email_frequency?: 'daily' | 'per_filing' | 'disabled';
  interested_companies?: string[];
  email_enabled?: boolean;
  content_preference?: 'tldr' | 'full';
  delivery_time?: string;
}

// Company information for selection UI
export interface CompanyInfo {
  id: string;
  ticker: string;
  name: string;
  sector: string | null;
  enabled: boolean;
  metadata?: {
    domain?: string;
    logo_url?: string;
    category?: string;
  } | null;
}

// API response types
export interface ApiResponse<T = any> {
  success: boolean;
  data?: T;
  error?: string;
}

export interface UserPreferencesResponse extends ApiResponse<UserPreferences> {}

export interface CompaniesResponse extends ApiResponse<CompanyInfo[]> {}
