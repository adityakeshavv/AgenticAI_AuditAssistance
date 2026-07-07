import { type FormEvent, useMemo, useState } from 'react';
import { buildGoogleSignInUrl, login, saveAuthSession, signup } from '../services/authApi';
import type { AuthResponse } from '../types/auth';

type AuthMode = 'login' | 'signup';

interface AuthPageProps {
  onAuthenticated: (session: AuthResponse) => void;
}

function NebulaLogo() {
  return (
    <svg viewBox="0 0 160 160" width="88" height="88" aria-hidden="true">
      <defs>
        <linearGradient id="nebula-gradient" x1="0%" y1="15%" x2="100%" y2="85%">
          <stop offset="0%" stopColor="#6b5cff" />
          <stop offset="50%" stopColor="#a86be8" />
          <stop offset="100%" stopColor="#ff7aa6" />
        </linearGradient>
        <linearGradient id="nebula-glow" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="#f7f4eb" />
          <stop offset="100%" stopColor="#ffffff" stopOpacity="0" />
        </linearGradient>
      </defs>
      <rect x="8" y="8" width="144" height="144" rx="30" fill="#fbfaf6" />
      <path
        d="M46 104V56c0-8 6.5-14 14.5-14 5.4 0 10.3 2.9 12.9 7.6L80 60l6.6-10.4C89.2 44.9 94.1 42 99.5 42 107.5 42 114 48 114 56v48c0 8-6.5 14-14.5 14-5.4 0-10.2-2.9-12.8-7.5L80 100l-6.7 10.5c-2.6 4.6-7.4 7.5-12.8 7.5C52.5 118 46 112 46 104Z"
        fill="none"
        stroke="url(#nebula-gradient)"
        strokeWidth="13"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <path
        d="M80 60v40"
        fill="none"
        stroke="url(#nebula-gradient)"
        strokeWidth="13"
        strokeLinecap="round"
      />
      <path d="M22 22h116" stroke="url(#nebula-glow)" strokeWidth="2" opacity="0.35" />
    </svg>
  );
}

export function AuthPage({ onAuthenticated }: AuthPageProps) {
  const [mode, setMode] = useState<AuthMode>('login');
  const [fullName, setFullName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const heading = useMemo(
    () => (mode === 'login' ? 'Welcome back' : 'Create your Nebula9.ai account'),
    [mode],
  );

  const subheading = useMemo(
    () => (mode === 'login'
      ? 'Sign in to continue your audit investigations.'
      : 'Set up your workspace with a secure account.'),
    [mode],
  );

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setLoading(true);
    setErrorMessage(null);
    try {
      const session = mode === 'login'
        ? await login({ email, password })
        : await signup({ full_name: fullName, email, password });
      saveAuthSession(session.access_token, session.user);
      onAuthenticated(session);
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : 'Authentication failed.');
    } finally {
      setLoading(false);
    }
  };

  const handleGoogleSignIn = () => {
    window.location.href = buildGoogleSignInUrl();
  };

  return (
    <div className="auth-page">
      <div className="auth-shell">
        <section className="auth-brand-panel">
          <div className="auth-brand-stack">
            <NebulaLogo />
            <div>
              <p className="auth-kicker">Nebula9.ai</p>
              <h1 className="auth-brand-title">Audit intelligence, presented with clarity.</h1>
              <p className="auth-brand-copy">
                A clean entry point for audit investigations, evidence review, and executive reporting.
              </p>
            </div>
          </div>
          <div className="auth-brand-footer">
            <span className="auth-brand-dot" />
            <span>Secure access for audit teams and reviewers</span>
          </div>
        </section>

        <section className="auth-form-panel">
          <div className="auth-form-card">
            <div className="tab-bar auth-tab-bar">
              <button
                type="button"
                className={`tab-btn auth-tab-btn${mode === 'login' ? ' active' : ''}`}
                onClick={() => setMode('login')}
              >
                Login
              </button>
              <button
                type="button"
                className={`tab-btn auth-tab-btn${mode === 'signup' ? ' active' : ''}`}
                onClick={() => setMode('signup')}
              >
                Sign Up
              </button>
            </div>

            <div className="auth-header-copy">
              <h2>{heading}</h2>
              <p>{subheading}</p>
            </div>

            <form className="stack" onSubmit={handleSubmit}>
              {mode === 'signup' && (
                <div>
                  <label className="label auth-label" htmlFor="full-name">Full Name</label>
                  <input
                    id="full-name"
                    className="input auth-input"
                    value={fullName}
                    onChange={(e) => setFullName(e.target.value)}
                    placeholder="Jane Audit"
                    autoComplete="name"
                    required
                  />
                </div>
              )}

              <div>
                <label className="label auth-label" htmlFor="email">Email</label>
                <input
                  id="email"
                  className="input auth-input"
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="jane@company.com"
                  autoComplete="email"
                  required
                />
              </div>

              <div>
                <label className="label auth-label" htmlFor="password">Password</label>
                <input
                  id="password"
                  className="input auth-input"
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Enter your password"
                  autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
                  required
                />
              </div>

              {errorMessage && (
                <div className="auth-error">
                  <p>{errorMessage}</p>
                </div>
              )}

              <button className="btn auth-primary-btn" type="submit" disabled={loading}>
                {loading ? 'Processing…' : mode === 'login' ? 'Login' : 'Create Account'}
              </button>

              <div style={{ display: 'grid', gap: '0.65rem' }}>
                <button className="btn auth-google-btn" type="button" onClick={handleGoogleSignIn} disabled={loading}>
                  Continue with Google
                </button>
              </div>
            </form>
          </div>
        </section>
      </div>
    </div>
  );
}
