import type { AuthUser } from './auth';
import type { DatabaseConnectionRecord } from './databaseConnections';
import type { WorkspaceRecord } from './workspace';

export interface AdminDashboardData {
  users: AuthUser[];
  workspaces: WorkspaceRecord[];
  connections: DatabaseConnectionRecord[];
}
