CREATE TABLE workspaces (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE users (
    id TEXT PRIMARY KEY,
    username TEXT NOT NULL UNIQUE,
    email TEXT UNIQUE,
    password_hash TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',
    global_role TEXT NOT NULL DEFAULT 'user',
    created_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE workspace_memberships (
    workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (workspace_id, user_id)
);

CREATE TABLE sessions (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    workspace_id TEXT REFERENCES workspaces(id) ON DELETE SET NULL,
    token_hash TEXT NOT NULL UNIQUE,
    created_at TIMESTAMPTZ NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    revoked_at TIMESTAMPTZ
);

CREATE TABLE question_banks (
    id BIGSERIAL PRIMARY KEY,
    workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    subject TEXT NOT NULL DEFAULT '',
    version INTEGER NOT NULL DEFAULT 1,
    source TEXT,
    created_at TIMESTAMPTZ NOT NULL,
    UNIQUE (workspace_id, name)
);

CREATE TABLE questions (
    id TEXT PRIMARY KEY,
    bank_id BIGINT NOT NULL REFERENCES question_banks(id) ON DELETE CASCADE,
    version INTEGER NOT NULL,
    type TEXT NOT NULL,
    stem TEXT NOT NULL,
    normalized_stem TEXT NOT NULL,
    answer_kind TEXT NOT NULL,
    explanation TEXT,
    status TEXT NOT NULL,
    difficulty DOUBLE PRECISION,
    source_json TEXT NOT NULL,
    tags_json TEXT NOT NULL,
    answer_aliases_json TEXT NOT NULL DEFAULT '[]'
);

CREATE TABLE options (
    id BIGSERIAL PRIMARY KEY,
    question_id TEXT NOT NULL REFERENCES questions(id) ON DELETE CASCADE,
    option_key TEXT NOT NULL,
    text TEXT NOT NULL,
    normalized_text TEXT NOT NULL,
    is_correct INTEGER NOT NULL,
    UNIQUE (question_id, option_key)
);

CREATE TABLE tags (
    id BIGSERIAL PRIMARY KEY,
    name TEXT NOT NULL UNIQUE
);

CREATE TABLE question_tags (
    question_id TEXT NOT NULL REFERENCES questions(id) ON DELETE CASCADE,
    tag_id BIGINT NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
    PRIMARY KEY (question_id, tag_id)
);

CREATE TABLE practice_sessions (
    id TEXT PRIMARY KEY,
    mode TEXT NOT NULL,
    started_at TIMESTAMPTZ NOT NULL,
    ended_at TIMESTAMPTZ,
    filter_json TEXT NOT NULL,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE
);

CREATE TABLE answer_events (
    id BIGSERIAL PRIMARY KEY,
    session_id TEXT REFERENCES practice_sessions(id) ON DELETE SET NULL,
    question_id TEXT NOT NULL REFERENCES questions(id) ON DELETE CASCADE,
    question_version INTEGER NOT NULL,
    user_answer TEXT NOT NULL,
    is_correct INTEGER NOT NULL,
    match_method TEXT,
    confidence DOUBLE PRECISION,
    elapsed_ms INTEGER,
    created_at TIMESTAMPTZ NOT NULL,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE
);

CREATE TABLE review_state (
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    question_id TEXT NOT NULL REFERENCES questions(id) ON DELETE CASCADE,
    due_at TIMESTAMPTZ,
    interval_days DOUBLE PRECISION NOT NULL,
    ease DOUBLE PRECISION NOT NULL,
    repetitions INTEGER NOT NULL,
    lapses INTEGER NOT NULL,
    scheduler TEXT NOT NULL,
    PRIMARY KEY (user_id, question_id)
);

CREATE TABLE ai_audits (
    id BIGSERIAL PRIMARY KEY,
    workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    question_text_hash TEXT NOT NULL,
    provider TEXT NOT NULL,
    model TEXT,
    request_json TEXT,
    response_json TEXT,
    parsed_json TEXT,
    validation_status TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL
);

CREATE INDEX idx_questions_bank_status ON questions(bank_id, status);
CREATE INDEX idx_question_banks_workspace ON question_banks(workspace_id, name);
CREATE INDEX idx_practice_sessions_user ON practice_sessions(user_id, started_at);
CREATE INDEX idx_answer_events_user_question ON answer_events(user_id, question_id, created_at);
CREATE INDEX idx_review_user_due ON review_state(user_id, due_at);
CREATE INDEX idx_sessions_token ON sessions(token_hash);
