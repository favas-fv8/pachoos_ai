import type { Role } from '@/types'

/** Roles with access to the /admin dashboard. */
export const ADMIN_ROLES: Role[] = ['super_admin', 'store_manager']

export const isAdminRole = (role?: string | null): boolean =>
  Boolean(role && (ADMIN_ROLES as string[]).includes(role))
