/* Review-board API — the only client module that fetches per-student
 * demographics. Import restricted to features/reviewBoard/ (ESLint boundary). */

import { api } from './client'
import type { Proposal } from './types/common'
import type { CompositionView, ReviewBoard } from './types/review'

export interface EditRequest {
  action: 'move' | 'assign'
  student_id: string
  to_group: number
  allow_oversize?: boolean
}

export const reviewApi = {
  board: (cycleId: number) => api<ReviewBoard>('GET', `/api/cycles/${cycleId}/review-board`),

  composition: (cycleId: number) =>
    api<CompositionView>('GET', `/api/cycles/${cycleId}/composition`),

  edit: (cycleId: number, edit: EditRequest) =>
    api<Proposal>('POST', `/api/cycles/${cycleId}/edits`, edit),
}
