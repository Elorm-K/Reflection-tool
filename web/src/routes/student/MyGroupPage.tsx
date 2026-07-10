import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { studentApi } from '../../lib/api/student'
import type { ApiError } from '../../lib/api/client'
import type { StudentGroupView } from '../../lib/api/types/student'
import { Badge, Button, Card, useToast } from '../../components/ui'
import styles from './student.module.css'

function initials(name: string): string {
  const parts = name.trim().split(/\s+/)
  return ((parts[0]?.[0] ?? '') + (parts[1]?.[0] ?? '')).toUpperCase() || '??'
}

function NotificationBanner() {
  const queryClient = useQueryClient()
  const { data } = useQuery({
    queryKey: ['notifications'],
    queryFn: studentApi.notifications,
  })
  const dismiss = useMutation({
    mutationFn: studentApi.markNotificationsRead,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['notifications'] })
      queryClient.invalidateQueries({ queryKey: ['myGroup'] })
    },
  })
  const latestUnread = data?.notifications.find((n) => n.read_at === null)
  if (!latestUnread) return null
  return (
    <div className={styles.noticeCard} role="status">
      <div>
        <div className="mono-label">
          {data!.unread > 1 ? `${data!.unread} updates` : 'Update'} from your instructor
        </div>
        <p className={styles.noticeBody}>{latestUnread.body}</p>
      </div>
      <Button variant="ghost" onClick={() => dismiss.mutate()} disabled={dismiss.isPending}>
        Dismiss
      </Button>
    </div>
  )
}

function Chat() {
  const [draft, setDraft] = useState('')
  const toast = useToast()
  const queryClient = useQueryClient()
  const { data } = useQuery({
    queryKey: ['groupMessages'],
    queryFn: () => studentApi.messages(),
    refetchInterval: 5000,
  })
  const send = useMutation({
    mutationFn: (body: string) => studentApi.sendMessage(body),
    onSuccess: () => {
      setDraft('')
      queryClient.invalidateQueries({ queryKey: ['groupMessages'] })
    },
    onError: (err) => toast((err as unknown as ApiError).detail ?? 'could not send', true),
  })

  return (
    <div className={styles.chat}>
      <h3>Group chat</h3>
      <p className="mono-label">Visible to your group and your instructor</p>
      {(data?.messages ?? []).map((m) => (
        <div key={m.id} className={styles.chatMsg}>
          <div className={styles.chatMeta}>
            {m.sender_name || m.sender_id} · {m.created_at}
          </div>
          {m.body}
        </div>
      ))}
      {data && data.messages.length === 0 && (
        <p style={{ color: 'var(--muted)', fontSize: 14 }}>No messages yet — say hello!</p>
      )}
      <form
        className={styles.chatForm}
        onSubmit={(e) => {
          e.preventDefault()
          if (draft.trim()) send.mutate(draft.trim())
        }}
      >
        <input
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          placeholder="Message your group…"
          maxLength={2000}
        />
        <Button type="submit" disabled={send.isPending || !draft.trim()}>
          Send
        </Button>
      </form>
    </div>
  )
}

export function MyGroupPage() {
  const [chatOpen, setChatOpen] = useState(false)
  const { data, error } = useQuery({
    queryKey: ['myGroup'],
    queryFn: studentApi.myGroup,
    retry: false,
  })
  const { data: me } = useQuery({ queryKey: ['me'], queryFn: studentApi.me })

  if (error) {
    const status = (error as unknown as ApiError).status
    return (
      <>
        <h2 className={styles.pageTitle}>My Group</h2>
        <Card>
          {status === 409
            ? 'Your group is not published yet. You will see it here as soon as your instructor finalizes the matching.'
            : 'Could not load your group right now.'}
        </Card>
      </>
    )
  }
  if (!data) return <p>Loading…</p>

  if (!('group_number' in data)) {
    return (
      <>
        <h2 className={styles.pageTitle}>My Group</h2>
        <NotificationBanner />
        <Card>{(data as { message?: string }).message ?? 'You are not in a group this cycle — your instructor will follow up with you directly.'}</Card>
      </>
    )
  }

  const group = data as StudentGroupView
  return (
    <>
      <NotificationBanner />
      <div className={styles.heroCard}>
        <Badge>Published</Badge>
        <h2>You are in Group {group.group_number}</h2>
        <p style={{ color: 'var(--muted)', margin: 0 }}>
          Your group matching has been finalized by the instructor.
        </p>
      </div>

      <div className={styles.meetingCard}>
        <span aria-hidden>🗓</span>
        <div>
          <div className="mono-label">Meeting time</div>
          <div className={styles.meetingTime}>{group.meeting_slots.join(', ')}</div>
        </div>
      </div>

      <div className="mono-label" style={{ marginBottom: 8 }}>
        Group members ({group.members.length})
      </div>
      {group.members.map((name) => {
        const you = me != null && (name === me.name || name === me.student_id)
        return (
          <div key={name} className={you ? styles.memberCardYou : styles.memberCard}>
            <span className={styles.avatar}>{you ? 'YU' : initials(name)}</span>
            <span className={styles.memberName}>{you ? 'You' : name}</span>
            {you && <span style={{ marginLeft: 'auto' }}>✓</span>}
          </div>
        )
      })}

      <div className={styles.privacyNote}>
        <span aria-hidden>ⓘ</span>
        <span>
          <strong>Note:</strong> No gender or disability information is shown. Privacy filters
          are active to ensure inclusive collaboration.
        </span>
      </div>

      {chatOpen ? (
        <Chat />
      ) : (
        <Button onClick={() => setChatOpen(true)}>🗨 Open group chat</Button>
      )}
    </>
  )
}
