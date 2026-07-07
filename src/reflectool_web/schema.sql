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
