"""Plain-SQL data access. All functions take an open connection and commit."""

import json
import secrets
import sqlite3
import string

_CODE_ALPHABET = string.ascii_uppercase + string.digits


def _row(cursor_row) -> dict | None:
    return dict(cursor_row) if cursor_row is not None else None


# --- instructors & tokens ---------------------------------------------------

def create_instructor(db: sqlite3.Connection, email: str, password_hash: str, name: str) -> int:
    cur = db.execute(
        "INSERT INTO instructors (email, password_hash, name) VALUES (?, ?, ?)",
        (email.lower().strip(), password_hash, name),
    )
    db.commit()
    return cur.lastrowid


def get_instructor_by_email(db: sqlite3.Connection, email: str) -> dict | None:
    return _row(db.execute(
        "SELECT * FROM instructors WHERE email = ?", (email.lower().strip(),)
    ).fetchone())


def issue_token(
    db: sqlite3.Connection,
    kind: str,
    instructor_id: int | None = None,
    enrollment_id: int | None = None,
) -> str:
    token = secrets.token_urlsafe(32)
    db.execute(
        "INSERT INTO auth_tokens (token, kind, instructor_id, enrollment_id) VALUES (?, ?, ?, ?)",
        (token, kind, instructor_id, enrollment_id),
    )
    db.commit()
    return token


def lookup_token(db: sqlite3.Connection, token: str) -> dict | None:
    return _row(db.execute(
        "SELECT * FROM auth_tokens WHERE token = ?", (token,)
    ).fetchone())


# --- classes & roster -------------------------------------------------------

def create_class(db: sqlite3.Connection, instructor_id: int, name: str, term: str = "",
                 timezone: str = "UTC") -> dict:
    for _ in range(20):
        code = "".join(secrets.choice(_CODE_ALPHABET) for _ in range(6))
        try:
            cur = db.execute(
                "INSERT INTO classes (instructor_id, name, term, class_code, timezone)"
                " VALUES (?, ?, ?, ?, ?)",
                (instructor_id, name, term, code, timezone),
            )
            db.commit()
            return get_class(db, cur.lastrowid)
        except sqlite3.IntegrityError as exc:
            if "class_code" not in str(exc):
                raise
    raise RuntimeError("could not generate a unique class code")


def get_class(db: sqlite3.Connection, class_id: int) -> dict | None:
    return _row(db.execute("SELECT * FROM classes WHERE id = ?", (class_id,)).fetchone())


def get_class_by_code(db: sqlite3.Connection, code: str) -> dict | None:
    return _row(db.execute(
        "SELECT * FROM classes WHERE class_code = ?", (code.upper().strip(),)
    ).fetchone())


def list_classes(db: sqlite3.Connection, instructor_id: int) -> list[dict]:
    return [dict(r) for r in db.execute(
        "SELECT * FROM classes WHERE instructor_id = ? ORDER BY created_at DESC, id DESC",
        (instructor_id,),
    ).fetchall()]


def replace_roster(db: sqlite3.Connection, class_id: int, entries: list[tuple[str, str]]) -> None:
    seen: set[str] = set()
    for ext_id, _name in entries:
        if ext_id in seen:
            raise ValueError(f"duplicate student id in roster: {ext_id}")
        seen.add(ext_id)
    with db:
        db.execute(
            "DELETE FROM class_roster WHERE class_id = ? AND id NOT IN"
            " (SELECT roster_id FROM enrollments)",
            (class_id,),
        )
        for ext_id, name in entries:
            db.execute(
                "INSERT INTO class_roster (class_id, student_ext_id, name) VALUES (?, ?, ?)"
                " ON CONFLICT (class_id, student_ext_id) DO UPDATE SET name = excluded.name",
                (class_id, ext_id, name),
            )


def list_roster(db: sqlite3.Connection, class_id: int) -> list[dict]:
    return [dict(r) for r in db.execute(
        "SELECT r.*, e.id AS enrollment_id FROM class_roster r"
        " LEFT JOIN enrollments e ON e.roster_id = r.id"
        " WHERE r.class_id = ? ORDER BY r.student_ext_id",
        (class_id,),
    ).fetchall()]


def claim_enrollment(db: sqlite3.Connection, class_id: int, student_ext_id: str) -> dict | None:
    roster_row = db.execute(
        "SELECT * FROM class_roster WHERE class_id = ? AND student_ext_id = ?",
        (class_id, student_ext_id.strip()),
    ).fetchone()
    if roster_row is None:
        return None
    existing = db.execute(
        "SELECT * FROM enrollments WHERE roster_id = ?", (roster_row["id"],)
    ).fetchone()
    if existing is not None:
        return dict(existing)
    cur = db.execute("INSERT INTO enrollments (roster_id) VALUES (?)", (roster_row["id"],))
    db.commit()
    return _row(db.execute("SELECT * FROM enrollments WHERE id = ?", (cur.lastrowid,)).fetchone())


def get_enrollment_context(db: sqlite3.Connection, enrollment_id: int) -> dict | None:
    """Enrollment joined with its roster entry and class."""
    return _row(db.execute(
        "SELECT e.id AS enrollment_id, r.student_ext_id, r.name, r.class_id,"
        "       c.class_code, c.instructor_id, c.timezone"
        " FROM enrollments e"
        " JOIN class_roster r ON r.id = e.roster_id"
        " JOIN classes c ON c.id = r.class_id"
        " WHERE e.id = ?",
        (enrollment_id,),
    ).fetchone())


def reset_claim(db: sqlite3.Connection, class_id: int, student_ext_id: str) -> bool:
    row = db.execute(
        "SELECT e.id FROM enrollments e JOIN class_roster r ON r.id = e.roster_id"
        " WHERE r.class_id = ? AND r.student_ext_id = ?",
        (class_id, student_ext_id),
    ).fetchone()
    if row is None:
        return False
    with db:
        db.execute("DELETE FROM auth_tokens WHERE enrollment_id = ?", (row["id"],))
        db.execute("DELETE FROM messages WHERE enrollment_id = ?", (row["id"],))
        db.execute("DELETE FROM submissions WHERE enrollment_id = ?", (row["id"],))
        db.execute("DELETE FROM notifications WHERE enrollment_id = ?", (row["id"],))
        db.execute("DELETE FROM email_outbox WHERE enrollment_id = ?", (row["id"],))
        db.execute("DELETE FROM enrollments WHERE id = ?", (row["id"],))
    return True


# --- cycles -----------------------------------------------------------------

def create_cycle(db: sqlite3.Connection, class_id: int, label: str, config: dict,
                 deadline: str | None = None) -> dict:
    cur = db.execute(
        "INSERT INTO cycles (class_id, label, deadline, config_json) VALUES (?, ?, ?, ?)",
        (class_id, label, deadline, json.dumps(config)),
    )
    db.commit()
    return get_cycle(db, cur.lastrowid)


def get_cycle(db: sqlite3.Connection, cycle_id: int) -> dict | None:
    row = _row(db.execute("SELECT * FROM cycles WHERE id = ?", (cycle_id,)).fetchone())
    if row is not None:
        row["config"] = json.loads(row.pop("config_json"))
    return row


def list_cycles(db: sqlite3.Connection, class_id: int) -> list[dict]:
    return [
        {**dict(r), "config": json.loads(r["config_json"])}
        for r in db.execute(
            "SELECT * FROM cycles WHERE class_id = ? ORDER BY created_at DESC, id DESC",
            (class_id,),
        ).fetchall()
    ]


def update_cycle(db: sqlite3.Connection, cycle_id: int, **fields) -> None:
    if "config" in fields:
        fields["config_json"] = json.dumps(fields.pop("config"))
    columns = ", ".join(f"{k} = ?" for k in fields)
    db.execute(f"UPDATE cycles SET {columns} WHERE id = ?", (*fields.values(), cycle_id))
    db.commit()


def current_cycle_for_class(db: sqlite3.Connection, class_id: int) -> dict | None:
    row = db.execute(
        "SELECT id FROM cycles WHERE class_id = ? AND status != 'archived'"
        " ORDER BY created_at DESC, id DESC LIMIT 1",
        (class_id,),
    ).fetchone()
    return get_cycle(db, row["id"]) if row else None


# --- submissions ------------------------------------------------------------

def _ensure_submission(db: sqlite3.Connection, cycle_id: int, enrollment_id: int) -> None:
    db.execute(
        "INSERT INTO submissions (cycle_id, enrollment_id) VALUES (?, ?)"
        " ON CONFLICT (cycle_id, enrollment_id) DO NOTHING",
        (cycle_id, enrollment_id),
    )


def upsert_availability(db: sqlite3.Connection, cycle_id: int, enrollment_id: int,
                        slots: list[bool]) -> None:
    with db:
        _ensure_submission(db, cycle_id, enrollment_id)
        db.execute(
            "UPDATE submissions SET availability_json = ?, submitted_at = datetime('now')"
            " WHERE cycle_id = ? AND enrollment_id = ?",
            (json.dumps([bool(s) for s in slots]), cycle_id, enrollment_id),
        )


def upsert_survey(db: sqlite3.Connection, cycle_id: int, enrollment_id: int,
                  gender: str | None = None, disability: str | None = None,
                  skipped: bool = False) -> None:
    with db:
        _ensure_submission(db, cycle_id, enrollment_id)
        db.execute(
            "UPDATE submissions SET gender = ?, disability = ?, survey_skipped = ?,"
            " submitted_at = datetime('now')"
            " WHERE cycle_id = ? AND enrollment_id = ?",
            (gender, disability, int(skipped), cycle_id, enrollment_id),
        )


def list_submissions(db: sqlite3.Connection, cycle_id: int) -> list[dict]:
    """Instructor-side view: includes demographics. Never serve to students."""
    rows = db.execute(
        "SELECT s.*, r.student_ext_id, r.name FROM submissions s"
        " JOIN enrollments e ON e.id = s.enrollment_id"
        " JOIN class_roster r ON r.id = e.roster_id"
        " WHERE s.cycle_id = ? ORDER BY r.student_ext_id",
        (cycle_id,),
    ).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        raw = d.pop("availability_json")
        d["availability"] = json.loads(raw) if raw else None
        out.append(d)
    return out


def get_submission(db: sqlite3.Connection, cycle_id: int, enrollment_id: int) -> dict | None:
    row = _row(db.execute(
        "SELECT * FROM submissions WHERE cycle_id = ? AND enrollment_id = ?",
        (cycle_id, enrollment_id),
    ).fetchone())
    if row is not None:
        raw = row.pop("availability_json")
        row["availability"] = json.loads(raw) if raw else None
    return row


def count_submissions(db: sqlite3.Connection, cycle_id: int) -> int:
    return db.execute(
        "SELECT COUNT(*) FROM submissions WHERE cycle_id = ? AND availability_json IS NOT NULL",
        (cycle_id,),
    ).fetchone()[0]


# --- messages ---------------------------------------------------------------

def add_message(db: sqlite3.Connection, cycle_id: int, group_id: int, enrollment_id: int,
                body: str) -> dict:
    cur = db.execute(
        "INSERT INTO messages (cycle_id, group_id, enrollment_id, body) VALUES (?, ?, ?, ?)",
        (cycle_id, group_id, enrollment_id, body),
    )
    db.commit()
    return _row(db.execute("SELECT * FROM messages WHERE id = ?", (cur.lastrowid,)).fetchone())


def list_messages(db: sqlite3.Connection, cycle_id: int, group_id: int,
                  since: int = 0) -> list[dict]:
    return [dict(r) for r in db.execute(
        "SELECT m.*, r.name AS sender_name, r.student_ext_id AS sender_id FROM messages m"
        " JOIN enrollments e ON e.id = m.enrollment_id"
        " JOIN class_roster r ON r.id = e.roster_id"
        " WHERE m.cycle_id = ? AND m.group_id = ? AND m.id > ? ORDER BY m.id",
        (cycle_id, group_id, since),
    ).fetchall()]


# --- audit ------------------------------------------------------------------

def add_audit(db: sqlite3.Connection, cycle_id: int, actor: str, action: str,
              detail: str = "") -> None:
    db.execute(
        "INSERT INTO audit_log (cycle_id, actor, action, detail) VALUES (?, ?, ?, ?)",
        (cycle_id, actor, action, detail),
    )
    db.commit()


def list_audit(db: sqlite3.Connection, cycle_id: int) -> list[dict]:
    return [dict(r) for r in db.execute(
        "SELECT * FROM audit_log WHERE cycle_id = ? ORDER BY id",
        (cycle_id,),
    ).fetchall()]


# --- notifications ------------------------------------------------------------

def add_notification(db: sqlite3.Connection, cycle_id: int, enrollment_id: int,
                     kind: str, body: str) -> int:
    cur = db.execute(
        "INSERT INTO notifications (cycle_id, enrollment_id, kind, body) VALUES (?, ?, ?, ?)",
        (cycle_id, enrollment_id, kind, body),
    )
    db.commit()
    return cur.lastrowid


def list_notifications(db: sqlite3.Connection, enrollment_id: int) -> list[dict]:
    return [dict(r) for r in db.execute(
        "SELECT * FROM notifications WHERE enrollment_id = ? ORDER BY id DESC",
        (enrollment_id,),
    ).fetchall()]


def count_unread_notifications(db: sqlite3.Connection, enrollment_id: int) -> int:
    return db.execute(
        "SELECT COUNT(*) FROM notifications WHERE enrollment_id = ? AND read_at IS NULL",
        (enrollment_id,),
    ).fetchone()[0]


def mark_notifications_read(db: sqlite3.Connection, enrollment_id: int) -> int:
    cur = db.execute(
        "UPDATE notifications SET read_at = datetime('now')"
        " WHERE enrollment_id = ? AND read_at IS NULL",
        (enrollment_id,),
    )
    db.commit()
    return cur.rowcount


def add_outbox_email(db: sqlite3.Connection, kind: str, subject: str, body: str, *,
                     recipient_email: str | None = None,
                     enrollment_id: int | None = None,
                     instructor_id: int | None = None) -> int:
    cur = db.execute(
        "INSERT INTO email_outbox (kind, recipient_email, enrollment_id, instructor_id,"
        " subject, body) VALUES (?, ?, ?, ?, ?, ?)",
        (kind, recipient_email, enrollment_id, instructor_id, subject, body),
    )
    db.commit()
    return cur.lastrowid


def get_enrollment_for_student(db: sqlite3.Connection, class_id: int,
                               student_ext_id: str) -> dict | None:
    return _row(db.execute(
        "SELECT e.* FROM enrollments e JOIN class_roster r ON r.id = e.roster_id"
        " WHERE r.class_id = ? AND r.student_ext_id = ?",
        (class_id, student_ext_id),
    ).fetchone())


# --- password resets ----------------------------------------------------------

def create_password_reset(db: sqlite3.Connection, instructor_id: int,
                          token_hash: str, ttl_minutes: int = 60) -> int:
    cur = db.execute(
        "INSERT INTO password_resets (instructor_id, token_hash, expires_at)"
        " VALUES (?, ?, datetime('now', ?))",
        (instructor_id, token_hash, f"+{int(ttl_minutes)} minutes"),
    )
    db.commit()
    return cur.lastrowid


def get_valid_password_reset(db: sqlite3.Connection, token_hash: str) -> dict | None:
    return _row(db.execute(
        "SELECT * FROM password_resets WHERE token_hash = ?"
        " AND used_at IS NULL AND expires_at > datetime('now')",
        (token_hash,),
    ).fetchone())


def mark_reset_used(db: sqlite3.Connection, reset_id: int, instructor_id: int) -> None:
    with db:
        db.execute(
            "UPDATE password_resets SET used_at = datetime('now') WHERE id = ?",
            (reset_id,),
        )
        # revoke the instructor's other outstanding reset links
        db.execute(
            "DELETE FROM password_resets WHERE instructor_id = ? AND id != ?"
            " AND used_at IS NULL",
            (instructor_id, reset_id),
        )


def update_instructor_password(db: sqlite3.Connection, instructor_id: int,
                               password_hash: str) -> None:
    db.execute(
        "UPDATE instructors SET password_hash = ? WHERE id = ?",
        (password_hash, instructor_id),
    )
    db.commit()


def delete_instructor_tokens(db: sqlite3.Connection, instructor_id: int) -> None:
    db.execute("DELETE FROM auth_tokens WHERE instructor_id = ?", (instructor_id,))
    db.commit()
