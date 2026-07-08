export interface GridConfig {
  days: number
  start: string
  end: string
  slot_minutes: number
  num_slots: number
}

export type LifecycleStatus = 'collecting' | 'proposed' | 'approved' | 'published' | 'archived'

export interface MatchConfig {
  target_size: number
  min_size: number
  max_size: number
  min_overlap: number
  priority: string[]
  tiebreak_seed: number
  grid: GridConfig
}

export interface ProposalGroup {
  group_id: number
  members: string[]
  meeting_slots: string[]
}

export interface UnplacedEntry {
  student_id: string
  reason: string
}

/** Demographic-free by server guarantee (assert_no_demographics). */
export interface Proposal {
  status: LifecycleStatus
  groups: ProposalGroup[]
  unplaced: UnplacedEntry[]
  warnings: string[]
}

export interface ChatMessage {
  id: number
  sender_id: string
  sender_name: string
  body: string
  created_at: string
}

export interface MessagesResponse {
  messages: ChatMessage[]
}
