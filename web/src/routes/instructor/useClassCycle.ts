import { useQuery } from '@tanstack/react-query'
import { useParams } from 'react-router-dom'
import { instructorApi } from '../../lib/api/instructor'

/** Class + its current (latest non-archived) cycle, shared by all class pages. */
export function useClassCycle() {
  const { classId } = useParams()
  const id = Number(classId)

  const cls = useQuery({
    queryKey: ['class', id],
    queryFn: () => instructorApi.getClass(id),
    enabled: Number.isFinite(id),
  })
  const cycles = useQuery({
    queryKey: ['cycles', id],
    queryFn: () => instructorApi.cycles(id),
    enabled: Number.isFinite(id),
  })

  const current = cycles.data?.find((c) => c.status !== 'archived') ?? null
  return { classId: id, cls: cls.data, cycles: cycles.data, cycle: current }
}
