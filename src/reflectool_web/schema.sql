CREATE TABLE IF NOT EXISTS instructors (
    id            INTEGER PRIMARY KEY,
    email         TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    name          TEXT NOT NULL DEFAULT '',
    created_at    TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS auth_tokens (
    token         TEXT PRIMARY KEY,
    kind          TEXT NOT NULL CHECK (kind IN ('instructor', 'student')),
    instructor_id INTEGER REFERENCES instructors(id),
    enrollment_id INTEGER REFERENCES enrollments(id),
    created_at    TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS classes (
    id            INTEGER PRIMARY KEY,
    instructor_id INTEGER NOT NULL REFERENCES instructors(id),
    name          TEXT NOT NULL,
    term          TEXT NOT NULL DEFAULT '',
    class_code    TEXT NOT NULL UNIQUE,
    timezone      TEXT NOT NULL DEFAULT 'UTC',
    archived      INTEGER NOT NULL DEFAULT 0,
    created_at    TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS class_roster (
    id             INTEGER PRIMARY KEY,
    class_id       INTEGER NOT NULL REFERENCES classes(id),
    student_ext_id TEXT NOT NULL,
    name           TEXT NOT NULL DEFAULT '',
    UNIQUE (class_id, student_ext_id)
);

CREATE TABLE IF NOT EXISTS enrollments (
    id         INTEGER PRIMARY KEY,
    roster_id  INTEGER NOT NULL UNIQUE REFERENCES class_roster(id),
    claimed_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS cycles (
    id           INTEGER PRIMARY KEY,
    class_id     INTEGER NOT NULL REFERENCES classes(id),
    label        TEXT NOT NULL DEFAULT '',
    deadline     TEXT,
    config_json  TEXT NOT NULL DEFAULT '{}',
    status       TEXT NOT NULL DEFAULT 'collecting'
                 CHECK (status IN ('collecting', 'proposed', 'approved', 'published', 'archived')),
    session_json TEXT,
    proposal_rev INTEGER NOT NULL DEFAULT 0,
    reviewed_rev INTEGER NOT NULL DEFAULT -1,
    approved_at  TEXT,
    published_at TEXT,
    created_at   TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Demographic values (gender/disability) live ONLY here and inside
-- cycles.session_json raw_students. Student-facing queries never select them.
CREATE TABLE IF NOT EXISTS submissions (
    id                INTEGER PRIMARY KEY,
    cycle_id          INTEGER NOT NULL REFERENCES cycles(id),
    enrollment_id     INTEGER NOT NULL REFERENCES enrollments(id),
    availability_json TEXT,
    gender            TEXT,
    disability        TEXT,
    survey_skipped    INTEGER NOT NULL DEFAULT 0,
    submitted_at      TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (cycle_id, enrollment_id)
);

CREATE TABLE IF NOT EXISTS messages (
    id            INTEGER PRIMARY KEY,
    cycle_id      INTEGER NOT NULL REFERENCES cycles(id),
    group_id      INTEGER NOT NULL,
    enrollment_id INTEGER NOT NULL REFERENCES enrollments(id),
    body          TEXT NOT NULL,
    created_at    TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS audit_log (
    id         INTEGER PRIMARY KEY,
    cycle_id   INTEGER NOT NULL REFERENCES cycles(id),
    actor      TEXT NOT NULL,
    action     TEXT NOT NULL,
    detail     TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- In-app notices to individual students (e.g. post-publish reassignment).
-- Bodies are always demographic-free: they pass student_safe() at write time.
CREATE TABLE IF NOT EXISTS notifications (
    id            INTEGER PRIMARY KEY,
    cycle_id      INTEGER NOT NULL REFERENCES cycles(id),
    enrollment_id INTEGER NOT NULL REFERENCES enrollments(id),
    kind          TEXT NOT NULL,           -- 'group-changed' | 'group-updated'
    body          TEXT NOT NULL,
    created_at    TEXT NOT NULL DEFAULT (datetime('now')),
    read_at       TEXT
);

-- Instructor password resets: single-use, 60-minute expiry. Only the sha256
-- of the token is stored — a DB leak grants no resets.
CREATE TABLE IF NOT EXISTS password_resets (
    id            INTEGER PRIMARY KEY,
    instructor_id INTEGER NOT NULL REFERENCES instructors(id),
    token_hash    TEXT NOT NULL UNIQUE,
    expires_at    TEXT NOT NULL,
    used_at       TEXT,
    created_at    TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Email records are composed and stored but never sent (no transport yet);
-- status stays 'disabled' until real sending is activated.
CREATE TABLE IF NOT EXISTS email_outbox (
    id              INTEGER PRIMARY KEY,
    kind            TEXT NOT NULL,          -- 'group-changed' | 'password-reset'
    recipient_email TEXT,                   -- NULL for students (no email on roster)
    enrollment_id   INTEGER REFERENCES enrollments(id),
    instructor_id   INTEGER REFERENCES instructors(id),
    subject         TEXT NOT NULL,
    body            TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'disabled' CHECK (status IN ('disabled', 'sent')),
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    sent_at         TEXT
);
