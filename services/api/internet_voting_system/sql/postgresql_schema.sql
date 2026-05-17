-- PostgreSQL schema for the InternetVotingSystem API.
--
-- This file is the canonical schema for the production-grade backend. It is
-- intentionally kept in lock-step with `sqlite_repository.py` (which uses the
-- SQLite dialect of the same logical model) so that:
--
--   1. A PostgreSQL repository implementation can be written from this file
--      without inventing a fresh schema.
--   2. Schema drift between the SQLite reference impl and the production
--      Postgres impl can be reviewed by diffing the two files.
--
-- Design notes:
--   * `voter_status` lives in the *identity zone* (red zone). It carries
--     voter_hash and audit fields only — never any vote content.
--   * `ballot` lives in the *anonymous voting zone* (blue zone). It carries
--     ciphertexts and tokens only — never any voter_hash.
--   * `audit_log` is hash-chained (`prev_hash` -> `log_hash`) so any
--     tampering can be detected by replaying canonical_json + SHA-256.
--   * The schema is namespaced to a `voting` schema so it can coexist with
--     other tenants in the same cluster without colliding with `public`.
--
-- Operational guidance:
--   * Run with `psql -v ON_ERROR_STOP=1 -f postgresql_schema.sql`.
--   * The token-issuance critical section MUST use `SELECT ... FOR UPDATE`
--     (PostgreSQL equivalent of SQLite's `BEGIN IMMEDIATE`). The Python
--     repository will issue this lock at the start of `mark_token_issued()`.
--   * For multi-million-voter elections add table partitioning on
--     `ballot.election_id` and `voter_status.election_id`. Partition pruning
--     keeps the FOR UPDATE lock scope small.

CREATE SCHEMA IF NOT EXISTS voting;

SET search_path TO voting;

-- ---------------------------------------------------------------------------
-- Elections (and their candidates)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS elections (
    election_id    TEXT        PRIMARY KEY,
    title          TEXT        NOT NULL,
    starts_at      TIMESTAMPTZ NOT NULL,
    ends_at        TIMESTAMPTZ NOT NULL,
    voter_salt     TEXT        NOT NULL,
    status         TEXT        NOT NULL DEFAULT 'open'
        CHECK (status IN ('open', 'closed')),
    CHECK (starts_at < ends_at)
);

CREATE TABLE IF NOT EXISTS candidates (
    election_id   TEXT NOT NULL REFERENCES elections(election_id) ON DELETE CASCADE,
    candidate_id  TEXT NOT NULL,
    display_name  TEXT NOT NULL,
    party         TEXT NOT NULL DEFAULT '',
    PRIMARY KEY (election_id, candidate_id)
);

-- ---------------------------------------------------------------------------
-- Identity zone: voter_status
--
-- This table never receives candidate_id, ballot_id, or encrypted_vote
-- columns. The CHECK constraint exists so that a careless ALTER TABLE in a
-- future migration would have to explicitly remove it before it could leak
-- vote content here.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS voter_status (
    voter_hash             TEXT        NOT NULL,
    election_id            TEXT        NOT NULL REFERENCES elections(election_id),
    token_issued           BOOLEAN     NOT NULL DEFAULT FALSE,
    token_issued_at        TIMESTAMPTZ,
    revote_count           INTEGER     NOT NULL DEFAULT 0
        CHECK (revote_count >= 0),
    last_issued_token_hash TEXT,
    PRIMARY KEY (election_id, voter_hash)
);

CREATE INDEX IF NOT EXISTS idx_voter_status_election
    ON voter_status (election_id, token_issued);

-- ---------------------------------------------------------------------------
-- Anonymous voting zone: ballot
--
-- voter_hash MUST NOT appear here. blind_token_hash is the only link back to
-- the identity zone, and that link is broken by the mathematics of the blind
-- signature (the unblinding factor lives client-side only).
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS ballot (
    ballot_id             UUID        PRIMARY KEY,
    election_id           TEXT        NOT NULL REFERENCES elections(election_id),
    blind_token_hash      TEXT        NOT NULL,
    encrypted_vote        JSONB       NOT NULL,
    zk_proof              TEXT        NOT NULL,
    received_at_bucket    TIMESTAMPTZ NOT NULL,
    sequence_in_bucket    INTEGER     NOT NULL CHECK (sequence_in_bucket >= 1),
    revote_serial         INTEGER     NOT NULL CHECK (revote_serial >= 1),
    receipt_hash          TEXT        NOT NULL,
    accepted_candidate_id TEXT        NOT NULL,
    UNIQUE (blind_token_hash, revote_serial)
);

CREATE INDEX IF NOT EXISTS idx_ballot_election
    ON ballot (election_id);
CREATE INDEX IF NOT EXISTS idx_ballot_receipt
    ON ballot (election_id, receipt_hash);

-- ---------------------------------------------------------------------------
-- Audit log (hash-chained, append-only)
--
-- Production deployments SHOULD also enable logical replication and stream
-- this table to an immutable WORM store (e.g. AWS S3 Object Lock) so the
-- chain is provable even if the primary database is compromised.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS audit_log (
    log_id      BIGSERIAL   PRIMARY KEY,
    prev_hash   TEXT        NOT NULL,
    log_hash    TEXT        NOT NULL,
    component   TEXT        NOT NULL,
    event_type  TEXT        NOT NULL,
    payload     JSONB       NOT NULL,
    occurred_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_audit_log_component
    ON audit_log (component, occurred_at);

-- ---------------------------------------------------------------------------
-- Recommended roles (least-privilege deployment)
--
-- These are advisory — uncomment and tailor passwords to your environment.
-- ---------------------------------------------------------------------------
-- CREATE ROLE voting_jpki_gateway   LOGIN PASSWORD '...';
-- CREATE ROLE voting_blind_signer   LOGIN PASSWORD '...';
-- CREATE ROLE voting_ballot_box     LOGIN PASSWORD '...';
-- CREATE ROLE voting_tally          LOGIN PASSWORD '...';
-- GRANT  USAGE ON SCHEMA voting     TO voting_jpki_gateway, voting_blind_signer, voting_ballot_box, voting_tally;
-- GRANT  SELECT, INSERT, UPDATE ON voter_status TO voting_blind_signer;
-- GRANT  SELECT                 ON elections, candidates TO voting_jpki_gateway, voting_blind_signer, voting_ballot_box, voting_tally;
-- GRANT  SELECT, INSERT         ON ballot     TO voting_ballot_box;
-- GRANT  SELECT                 ON ballot     TO voting_tally;
-- GRANT  INSERT                 ON audit_log  TO voting_jpki_gateway, voting_blind_signer, voting_ballot_box, voting_tally;
-- GRANT  SELECT                 ON audit_log  TO voting_tally;
-- REVOKE ALL ON ballot          FROM voting_jpki_gateway, voting_blind_signer;
-- REVOKE ALL ON voter_status    FROM voting_ballot_box, voting_tally;
