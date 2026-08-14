/** Frontend mirror of the backend strong-password policy. */

export interface PasswordCheck {
  label: string
  ok: boolean
}

export const PASSWORD_CHECKS: { key: string; label: string; test: (pw: string) => boolean }[] = [
  { key: 'length', label: 'At least 8 characters', test: (pw) => pw.length >= 8 },
  { key: 'upper', label: 'One uppercase letter', test: (pw) => /[A-Z]/.test(pw) },
  { key: 'lower', label: 'One lowercase letter', test: (pw) => /[a-z]/.test(pw) },
  { key: 'number', label: 'One number', test: (pw) => /\d/.test(pw) },
  { key: 'special', label: 'One special character', test: (pw) => /[^A-Za-z0-9]/.test(pw) },
]

export function checkPassword(password: string): PasswordCheck[] {
  return PASSWORD_CHECKS.map((c) => ({ label: c.label, ok: c.test(password) }))
}

export function isStrongPassword(password: string): boolean {
  return PASSWORD_CHECKS.every((c) => c.test(password))
}
