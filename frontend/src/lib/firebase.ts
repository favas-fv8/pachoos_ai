import { initializeApp, type FirebaseApp } from 'firebase/app'
import { getAnalytics, isSupported as analyticsSupported, type Analytics } from 'firebase/analytics'
import { getAuth, getIdToken, GoogleAuthProvider, type Auth, signInWithPopup } from 'firebase/auth'

/**
 * Firebase client configuration — read entirely from environment variables.
 * Used only for Google sign-in (customer primary auth).
 */
export const FIREBASE_CONFIG = {
  apiKey: import.meta.env.VITE_FIREBASE_API_KEY as string | undefined,
  authDomain: import.meta.env.VITE_FIREBASE_AUTH_DOMAIN as string | undefined,
  projectId: import.meta.env.VITE_FIREBASE_PROJECT_ID as string | undefined,
  appId: import.meta.env.VITE_FIREBASE_APP_ID as string | undefined,
  messagingSenderId: import.meta.env.VITE_FIREBASE_MESSAGING_SENDER_ID as string | undefined,
  storageBucket: import.meta.env.VITE_FIREBASE_STORAGE_BUCKET as string | undefined,
  measurementId: import.meta.env.VITE_FIREBASE_MEASUREMENT_ID as string | undefined,
}

let app: FirebaseApp | null = null
let auth: Auth | null = null
let analytics: Analytics | null = null

function getFirebaseAuth(): Auth {
  if (!app) app = initializeApp(FIREBASE_CONFIG)
  if (!auth) auth = getAuth(app)
  return auth
}

function initAnalytics(): void {
  if (analytics) return
  if (typeof window === 'undefined') return
  analyticsSupported().then((supported) => {
    if (supported && app) analytics = getAnalytics(app)
  })
}

/** Map Firebase auth error codes to user-facing messages. */
export function firebaseAuthErrorMessage(err: unknown): string {
  const code = (err as { code?: string })?.code ?? ''
  switch (code) {
    case 'auth/popup-blocked':
      return 'The sign-in popup was blocked. Allow popups and try again.'
    case 'auth/popup-closed-by-user':
    case 'auth/cancelled-popup-request':
    case 'auth/user-cancelled':
      return 'Sign-in was cancelled. No changes were made to your account.'
    case 'auth/timeout':
      return 'Sign-in timed out. Please try again.'
    case 'auth/network-request-failed':
      return 'Network error. Check your connection and try again.'
    case 'auth/email-already-in-use':
      return 'An account already exists with this email. Sign in instead.'
    case 'auth/account-exists-with-different-credential':
      return 'An account already exists with this email using a different sign-in method.'
    case 'auth/unauthorized-domain':
      return 'This sign-in domain is not authorised yet. Contact support.'
    case 'auth/web-storage-unsupported':
      return 'Private browsing may block sign-in. Allow site data and try again.'
    default:
      return err instanceof Error ? err.message : 'Something went wrong. Please try again.'
  }
}

export interface GoogleIdentity {
  idToken: string
  email: string
  fullName: string
}

/**
 * Complete Google sign-in via the Firebase popup and return a fresh ID token.
 * Throws an `Error` with a user-friendly message on failure — it never returns
 * partially verified identity data.
 */
export async function signInWithGoogle(): Promise<GoogleIdentity> {
  const auth = getFirebaseAuth()
  const provider = new GoogleAuthProvider()
  provider.setCustomParameters({ prompt: 'select_account' })
  try {
    const result = await signInWithPopup(auth, provider)
    return {
      idToken: await getIdToken(result.user),
      email: result.user.email ?? '',
      fullName: result.user.displayName ?? '',
    }
  } catch (err) {
    throw new Error(firebaseAuthErrorMessage(err))
  }
}

/**
 * Sign out of Firebase. Call this whenever PACHOOS clears the local session so
 * the next "Continue with Google" starts a genuinely fresh Google account
 * chooser instead of reusing a lingering Firebase session and its cached
 * (possibly stale) ID token.
 */
export async function signOutFirebase(): Promise<void> {
  if (typeof window === 'undefined') return
  try {
    const current = getFirebaseAuth()
    if (current.currentUser) await current.signOut()
  } catch {
    // Best-effort — the app session is cleared regardless.
  }
}

initAnalytics()
