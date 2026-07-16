import type { AuthResponse, AuthUser, LoginRequest, SignupRequest } from '../types/auth';
import { readApiError } from './apiErrors';

const AUTH_TOKEN_KEY = 'audit_auth_token';
const AUTH_USER_KEY = 'audit_auth_user';

function getApiBaseUrl(): string {
  const apiBaseUrl = import.meta.env.VITE_API_BASE_URL;
  if (!apiBaseUrl) {
    throw new Error('VITE_API_BASE_URL is not configured.');
  }
  return apiBaseUrl.replace(/\/$/, '');
}

async function parseAuthResponse(response: Response): Promise<AuthResponse> {
  if (!response.ok) {
    throw new Error(await readApiError(response, 'Request failed'));
  }
  const data: unknown = await response.json();
  if (!data || typeof data !== 'object') {
    throw new Error('Invalid authentication response received from backend.');
  }
  const payload = data as Partial<AuthResponse>;
  if (
    typeof payload.success !== 'boolean' ||
    typeof payload.access_token !== 'string' ||
    typeof payload.token_type !== 'string' ||
    !payload.user
  ) {
    throw new Error('Invalid authentication response received from backend.');
  }
  return payload as AuthResponse;
}

export function getStoredAuthToken(): string | null {
  return localStorage.getItem(AUTH_TOKEN_KEY);
}

export function getStoredAuthUser(): AuthUser | null {
  const raw = localStorage.getItem(AUTH_USER_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as AuthUser;
  } catch {
    return null;
  }
}

export function saveAuthSession(token: string, user: AuthUser): void {
  localStorage.setItem(AUTH_TOKEN_KEY, token);
  localStorage.setItem(AUTH_USER_KEY, JSON.stringify(user));
}

export function clearAuthSession(): void {
  localStorage.removeItem(AUTH_TOKEN_KEY);
  localStorage.removeItem(AUTH_USER_KEY);
}

export function buildAuthHeaders(token?: string | null): Record<string, string> {
  const authToken = token ?? getStoredAuthToken();
  return authToken ? { Authorization: `Bearer ${authToken}` } : {};
}

export async function login(payload: LoginRequest): Promise<AuthResponse> {
  const response = await fetch(`${getApiBaseUrl()}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  return parseAuthResponse(response);
}

export async function signup(payload: SignupRequest): Promise<AuthResponse> {
  const response = await fetch(`${getApiBaseUrl()}/auth/signup`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  return parseAuthResponse(response);
}

export async function fetchCurrentUser(token?: string | null): Promise<AuthUser> {
  const response = await fetch(`${getApiBaseUrl()}/auth/me`, {
    headers: buildAuthHeaders(token),
  });
  if (!response.ok) {
    throw new Error(await readApiError(response, 'Request failed'));
  }
  const data: unknown = await response.json();
  if (!data || typeof data !== 'object') {
    throw new Error('Invalid user response received from backend.');
  }
  return data as AuthUser;
}

export function buildGoogleSignInUrl(): string {
  return `${getApiBaseUrl()}/auth/google/start?redirect_uri=${encodeURIComponent(window.location.origin)}`;
}
