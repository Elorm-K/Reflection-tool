/**
 * Shared FAQ content, rendered on both the public landing page and the
 * instructor help center. The first entries are objection-style (aimed at
 * instructors deciding whether to try reflection groups); the rest are
 * operational.
 */
export const FAQ: [string, string][] = [
  [
    'Isn’t this a lot of work to set up?',
    'No — that’s the point of the tool. You collect availability and a short optional survey, click Run match, review the proposed groups, and publish. The matching, size and overlap checks, and student notifications are all handled for you; setting up a round takes minutes, not an afternoon.',
  ],
  [
    'Will students be singled out by their demographics?',
    'No. Students never see any demographic data — theirs or anyone else’s — and they’re never told which criteria formed their group. Survey answers are visible only to you, only during review. Matching also actively avoids leaving a student isolated as the only one of their kind in a group.',
  ],
  [
    'How does matching work?',
    'A deterministic matcher forms groups of 3–5 that share at least the configured number of mutually free slots, then optimizes for schedule overlap and identity comfort in your configured priority order. The same roster and settings always produce the same groups.',
  ],
  [
    'What do students see?',
    'Only their own group: group number, member names, and meeting slots — after you publish. Never demographic data, theirs or anyone else’s.',
  ],
  [
    'Who can see survey answers?',
    'Only you, only on the review board and composition views, only while reviewing. They are never written into the proposal, notifications, or exports.',
  ],
  [
    'Why is a student unplaced?',
    'Usually not enough schedule overlap with any viable group. Unplaced students are always listed on the review board with a reason — resolve by dragging them into a group (validated live) or following up directly.',
  ],
  [
    'Can I edit groups by hand?',
    'Yes — drag students between groups on the review board while the proposal is in the Proposed state. Every move is re-validated against size and overlap constraints; invalid moves are blocked with the specific reason.',
  ],
  [
    'What does approve actually do?',
    'Approval is a hard gate: nothing reaches students until you approve, and approving requires having viewed the current version of the proposal. Publishing is a separate, final step.',
  ],
]
