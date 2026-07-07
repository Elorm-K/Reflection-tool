"""Per-student notification views (spec section 4.6 step 5).

A student only ever receives their own group's data: group number, member
names, meeting slots. Nothing is available before status is 'published'.
"""

from __future__ import annotations

from .output_format import assert_no_demographics
from .review_workflow import Session, WorkflowError


class PreApprovalLeak(WorkflowError):
    pass


def student_view(session: Session, student_id: str) -> dict:
    if session.proposal["status"] != "published":
        raise PreApprovalLeak(
            f"notifications are only available once the grouping is published "
            f"(current status: {session.proposal['status']!r})"
        )
    student = session.student(student_id)  # KeyError for unknown ids
    for g in session.proposal["groups"]:
        if student.student_id in g["members"]:
            view = {
                "group_number": g["group_id"],
                "members": [session.student(sid).name or sid for sid in g["members"]],
                "meeting_slots": g["meeting_slots"],
            }
            assert_no_demographics(view)
            return view
    return {
        "message": "You have not been assigned to a group yet — "
        "your instructor will follow up with you directly."
    }


def all_notifications(session: Session) -> dict[str, dict]:
    return {s.student_id: student_view(session, s.student_id) for s in session.roster}
