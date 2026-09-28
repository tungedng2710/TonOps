export type IamRole = 'admin' | 'user';
export type IamStatus = 'active' | 'disabled';

export interface IamServiceStatus {
  enabled: boolean;
  self_signup_enabled: boolean;
}

export interface IamSignupRequest {
  username: string;
  email: string;
  display_name?: string;
  password: string;
}

export interface IamUser {
  id: string;
  username: string;
  email?: string;
  display_name: string;
  role: IamRole;
  status: IamStatus;
  must_change_password: boolean;
  created_at: string;
  updated_at?: string;
  last_login_at?: string;
  last_login_ip?: string;
  locked_until?: string;
  groups?: string[];
}

export interface PublicProfile {
  id: string;
  username: string;
  display_name: string;
  avatar?: string;
  bio?: string;
  role: IamRole;
  created_at?: string;
}

export interface ProfileProject {
  id: string;
  name: string;
  description?: string;
  visibility: 'public' | 'private';
  created?: string;
  last_update?: string;
}

export interface IamGroup {
  id: string;
  name: string;
  description?: string;
  member_count: number;
  members?: IamUser[];
}

export interface IamAuditEvent {
  id: string;
  timestamp: string;
  actor_username?: string;
  action: string;
  target_type: string;
  target_id?: string;
  source_ip?: string;
}

export interface IamPage<T> {
  total: number;
  page: number;
  page_size: number;
  users?: T[];
  groups?: T[];
  events?: T[];
}
