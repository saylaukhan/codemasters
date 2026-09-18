import { Skeleton } from 'antd'

/** Loading state (DESIGN.md §3.21): grey blocks instead of the content, never a full-screen spinner. */
export function ContentSkeleton({ rows = 4 }: { rows?: number }) {
  return <Skeleton active title paragraph={{ rows }} />
}
