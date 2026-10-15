export type UserRole = 'passenger' | 'driver' | 'admin' | 'superadmin';
export type UserStatus = 'pending_email' | 'pending_approval' | 'active' | 'suspended' | 'blocked';
export type ReviewStatus = 'pending' | 'approved' | 'rejected' | 'expired';
export type DocKind = 'student_card' | 'institutional_proof' | 'identity_document';
export type LegalKind = 'terms' | 'data_policy';
export type ThemeValue = 'system' | 'light' | 'dark';
export type LanguageValue = 'es' | 'en' | 'pt' | 'fr';

export interface DocumentSummary {
  id: string;
  kind: DocKind;
  status: ReviewStatus;
  rejection_reason: string | null;
  created_at: string;
  reviewed_at: string | null;
}

export interface LicenseSummary {
  id: string;
  status: ReviewStatus;
  expires_on: string;
  rejection_reason: string | null;
  created_at: string;
  reviewed_at: string | null;
}

export type PublishBlocker =
  | 'not_driver'
  | 'account_not_active'
  | 'license_missing'
  | 'license_pending'
  | 'license_rejected'
  | 'license_expired'
  | 'no_active_vehicle';

export interface PendingLegal {
  id: string;
  kind: LegalKind;
  version: string;
  language: LanguageValue;
}

export interface Me {
  id: string;
  email: string;
  full_name: string;
  sex: 'female' | 'male';
  program: string | null;
  role: UserRole;
  status: UserStatus;
  payment_note: string | null;
  preferred_language: LanguageValue;
  theme_preference: ThemeValue;
  last_login_at: string | null;
  document: DocumentSummary | null;
  license: LicenseSummary | null;
  can_publish: boolean;
  publish_blockers: PublishBlocker[];
  pending_legal: PendingLegal[];
}

export type AuthResultKind =
  | 'authenticated'
  | 'email_verification_required'
  | 'two_factor_required'
  | 'password_reset_code_sent';

export interface AuthResult {
  result: AuthResultKind;
  access_token: string | null;
  expires_in: number | null;
  user: Me | null;
  challenge_id: string | null;
  email_hint: string | null;
  resend_after_seconds: number | null;
}

export type ChallengePurpose = 'email_verification' | 'two_factor' | 'password_reset';

/** Desafio en curso: se envio un codigo al correo y falta escribirlo. */
export interface PendingChallenge {
  id: string;
  purpose: ChallengePurpose;
  emailHint: string;
  resendAt: number; // epoch ms a partir del cual se puede reenviar
}

export interface SessionInfo {
  id: string;
  device_label: string;
  ip: string | null;
  created_at: string;
  last_seen_at: string;
  current: boolean;
}

export interface LegalDocument {
  id: string;
  kind: LegalKind;
  version: string;
  language: LanguageValue;
  body_markdown: string;
  published_at: string;
  is_current: boolean;
}

export const PURPOSE_BY_RESULT: Partial<Record<AuthResultKind, ChallengePurpose>> = {
  email_verification_required: 'email_verification',
  two_factor_required: 'two_factor',
  password_reset_code_sent: 'password_reset',
};
