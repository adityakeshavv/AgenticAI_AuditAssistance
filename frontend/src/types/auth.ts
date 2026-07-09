export interface AuthUser {
  user_id: string;
  full_name: string;
  email: string;
  auth_provider: string;
  role?: 'user' | 'admin';
  is_active: boolean;
  last_login_at: string | null;
}

export interface AuthResponse {
  success: boolean;
  access_token: string;
  token_type: string;
  user: AuthUser;
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface SignupRequest {
  full_name: string;
  email: string;
  password: string;
}
