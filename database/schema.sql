-- AgriShield PostgreSQL schema (v1).
-- The API creates these tables automatically via SQLAlchemy; this file is the
-- reviewable source of truth for DBAs and for `psql -f database/schema.sql`.
--
--   createdb agrishield
--   psql -d agrishield -f database/schema.sql

BEGIN;

CREATE TABLE IF NOT EXISTS users (
    id              SERIAL PRIMARY KEY,
    phone           VARCHAR(20)  NOT NULL UNIQUE,
    name            VARCHAR(120) NOT NULL,
    password_hash   VARCHAR(255) NOT NULL,          -- bcrypt, cost 12
    language        VARCHAR(5)   NOT NULL DEFAULT 'te',
    village         VARCHAR(120),
    state           VARCHAR(120),
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ  NOT NULL DEFAULT now(),
    CONSTRAINT users_language_check CHECK (language IN ('te','hi','en','ta','kn'))
);

CREATE INDEX IF NOT EXISTS idx_users_phone ON users (phone);

CREATE TABLE IF NOT EXISTS detections (
    id                  SERIAL PRIMARY KEY,
    user_id             INTEGER NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    crop_key            VARCHAR(40) NOT NULL,
    disease_key         VARCHAR(80) NOT NULL,
    confidence          DOUBLE PRECISION NOT NULL,
    level               VARCHAR(10) NOT NULL CHECK (level IN ('green','yellow','red')),
    status              VARCHAR(20) NOT NULL CHECK (status IN ('diagnosed','unclear')),
    language            VARCHAR(5)  NOT NULL DEFAULT 'te',
    top3                JSONB       NOT NULL DEFAULT '[]'::jsonb,
    advisory_snapshot   JSONB       NOT NULL DEFAULT '{}'::jsonb,
    image_path          TEXT,
    gradcam_path        TEXT,
    model_version       VARCHAR(60) NOT NULL DEFAULT 'unknown',
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_detections_user_created
    ON detections (user_id, created_at DESC);

COMMIT;

-- Operational notes
-- * Images live on disk under UPLOAD_DIR/<user_id>/, with EXIF/GPS stripped on
--   upload. Only the relative path is stored here.
-- * No email, address, Aadhaar or precise coordinates are stored. Latitude and
--   longitude for weather are used per request and never persisted.
-- * Back up `users` and `detections` together; deleting a user cascades their
--   diagnoses.
