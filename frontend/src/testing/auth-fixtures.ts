import { AuthResult, Me } from '../app/core/auth/auth.models';

/** Usuario y respuestas de autenticacion compartidos por las pruebas. */
export const ME: Me = {
  id: 'u1',
  email: 'laura@unipamplona.edu.co',
  full_name: 'Laura Prueba',
  sex: 'female',
  program: null,
  role: 'passenger',
  status: 'active',
  payment_note: null,
  preferred_language: 'es',
  theme_preference: 'system',
  last_login_at: null,
  document: null,
  license: null,
  can_publish: false,
  publish_blockers: [],
  pending_legal: [],
};

export function authenticated(user: Partial<Me> = {}): AuthResult {
  return {
    result: 'authenticated',
    access_token: 'token-1',
    expires_in: 900,
    user: { ...ME, ...user },
    challenge_id: null,
    email_hint: null,
    resend_after_seconds: null,
  };
}
