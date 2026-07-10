/* Advisory drag prechecks for the review board; the server verdict is
 * authoritative. Below-min overlap is overridable (like oversize), so it
 * surfaces as needsLowOverlap rather than a hard block. */

import type { ReviewBoard as Board } from '../../lib/api/types/review'
import { mutualOverlap } from '../../lib/grid'

export interface Precheck {
  ok: boolean
  needsOversize: boolean
  needsLowOverlap: boolean
  /** Mutually free slots the group would share after the move. */
  overlap: number
  reason: string | null
}

const blocked = (reason: string): Precheck => ({
  ok: false,
  needsOversize: false,
  needsLowOverlap: false,
  overlap: 0,
  reason,
})

export function precheckMove(board: Board, studentId: string, toGroup: number): Precheck {
  const { config, students } = board
  const target = board.proposal.groups.find((g) => g.group_id === toGroup)
  if (!target) return blocked('no such group')
  if (target.members.includes(studentId)) return blocked('already in this group')

  const source = board.proposal.groups.find((g) => g.members.includes(studentId))
  if (source && source.members.length - 1 < config.min_size)
    return blocked(`Group ${source.group_id} would drop below ${config.min_size} members.`)

  const newMembers = [...target.members, studentId]
  if (newMembers.length > config.max_size + 1)
    return blocked(`Max is ${config.max_size} (+1 with override).`)

  const overlap = mutualOverlap(newMembers.map((sid) => students[sid].availability))
  return {
    ok: true,
    needsOversize: newMembers.length > config.max_size,
    needsLowOverlap: overlap < config.min_overlap,
    overlap,
    reason: null,
  }
}
