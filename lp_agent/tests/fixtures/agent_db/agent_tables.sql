-- Experimental local schema. Run through setup_agent_db.py, not a migration.
CREATE EXTENSION IF NOT EXISTS vector WITH SCHEMA public;

CREATE TABLE public.agent_user (
    user_id text PRIMARY KEY CHECK (btrim(user_id) <> ''),
    recall_enabled boolean,
    recall_limits jsonb NOT NULL DEFAULT '{}' CHECK (jsonb_typeof(recall_limits) = 'object'),
    recall_consent_at timestamptz, deleted_at timestamptz
);
CREATE TABLE public.agent_court (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    slug text NOT NULL UNIQUE, name text NOT NULL, jurisdiction_level text NOT NULL,
    config jsonb NOT NULL DEFAULT '{}', enabled boolean NOT NULL DEFAULT true
);
CREATE TABLE public.agent_topic (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(), slug text NOT NULL UNIQUE,
    title text NOT NULL, description text NOT NULL DEFAULT '',
    enabled boolean NOT NULL DEFAULT true
);
CREATE TABLE public.agent_court_topic (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(), court_id uuid NOT NULL,
    topic_id uuid NOT NULL, config jsonb NOT NULL DEFAULT '{}',
    enabled boolean NOT NULL DEFAULT true,
    UNIQUE (court_id, topic_id), UNIQUE (id, court_id, topic_id)
);
CREATE TABLE public.agent_matter (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(), user_id text NOT NULL,
    court_topic_id uuid NOT NULL, title text NOT NULL, case_reference text,
    state text NOT NULL DEFAULT 'open' CHECK (state IN ('open', 'closed')),
    closed_at timestamptz, deleted_at timestamptz,
    UNIQUE (id, user_id, court_topic_id), UNIQUE (id, user_id),
    CHECK ((state = 'closed') = (closed_at IS NOT NULL))
);
CREATE TABLE public.agent_procedure (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(), court_topic_id uuid NOT NULL,
    slug text NOT NULL, title text NOT NULL, version integer NOT NULL CHECK (version > 0),
    previous_version_id uuid UNIQUE, guidance text NOT NULL,
    state text NOT NULL DEFAULT 'draft' CHECK (state IN ('draft', 'in_review', 'published', 'withdrawn')),
    metadata jsonb NOT NULL DEFAULT '{}', created_by text NOT NULL,
    reviewed_by text, published_by text, published_at timestamptz,
    UNIQUE (court_topic_id, slug, version),
    CHECK ((version = 1) = (previous_version_id IS NULL)),
    CHECK (state <> 'published' OR (published_by IS NOT NULL AND published_at IS NOT NULL))
);
CREATE TABLE public.agent_phase (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(), procedure_id uuid NOT NULL,
    key text NOT NULL, position integer NOT NULL CHECK (position > 0),
    title text NOT NULL, instructions text NOT NULL,
    completion_criteria jsonb NOT NULL DEFAULT '[]',
    UNIQUE (procedure_id, key), UNIQUE (procedure_id, position)
);
CREATE TABLE public.agent_phase_fact (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(), phase_id uuid NOT NULL,
    fact_definition_id uuid NOT NULL, position integer NOT NULL CHECK (position > 0),
    required boolean NOT NULL, condition jsonb,
    UNIQUE (phase_id, fact_definition_id), UNIQUE (phase_id, position)
);
CREATE TABLE public.agent_phase_document (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(), phase_id uuid NOT NULL,
    document_id uuid NOT NULL, purpose text NOT NULL CHECK (purpose IN ('guidance', 'form', 'reference')),
    position integer NOT NULL CHECK (position > 0), condition jsonb,
    UNIQUE (phase_id, document_id, purpose), UNIQUE (phase_id, position)
);
CREATE TABLE public.agent_phase_deadline (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(), phase_id uuid NOT NULL,
    key text NOT NULL, label text NOT NULL, anchor_fact_definition_id uuid NOT NULL,
    rule jsonb NOT NULL, description text NOT NULL DEFAULT '', UNIQUE (phase_id, key)
);
CREATE TABLE public.agent_prompt (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(), key text NOT NULL,
    description text NOT NULL DEFAULT '', metadata jsonb NOT NULL DEFAULT '{}',
    previous_version_id uuid UNIQUE,
    version integer NOT NULL CHECK (version > 0), body text NOT NULL CHECK (btrim(body) <> ''),
    state text NOT NULL DEFAULT 'draft' CHECK (state IN ('draft', 'in_review', 'published', 'withdrawn')),
    created_by text NOT NULL, reviewed_by text, published_by text, published_at timestamptz,
    UNIQUE (key, version), CHECK ((version = 1) = (previous_version_id IS NULL)),
    CHECK (state <> 'published' OR (published_by IS NOT NULL AND published_at IS NOT NULL))
);
CREATE TABLE public.agent_document (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    owner_kind text NOT NULL CHECK (owner_kind IN ('court', 'user')),
    owner_court_id uuid, owner_user_id text, key text NOT NULL, title text NOT NULL,
    category text NOT NULL CHECK (category IN ('source', 'form', 'upload', 'generated')),
    previous_version_id uuid UNIQUE, deleted_at timestamptz,
    CHECK ((owner_kind = 'court' AND owner_court_id IS NOT NULL AND owner_user_id IS NULL)
        OR (owner_kind = 'user' AND owner_user_id IS NOT NULL AND owner_court_id IS NULL)),
    version integer NOT NULL CHECK (version > 0), s3_bucket text NOT NULL, s3_key text NOT NULL,
    s3_object_version text, sha256 text NOT NULL CHECK (sha256 ~ '^[0-9a-f]{64}$'),
    byte_size bigint NOT NULL CHECK (byte_size >= 0), media_type text NOT NULL,
    original_filename text, origin_url text, metadata jsonb NOT NULL DEFAULT '{}',
    state text NOT NULL CHECK (state IN ('draft', 'in_review', 'published', 'private', 'withdrawn')),
    storage_state text NOT NULL DEFAULT 'available' CHECK (storage_state IN ('available', 'deleting', 'deleted')),
    created_by text NOT NULL, reviewed_by text, published_by text, published_at timestamptz,
    UNIQUE NULLS NOT DISTINCT (owner_kind, owner_court_id, owner_user_id, key, version),
    CHECK ((version = 1) = (previous_version_id IS NULL)),
    UNIQUE NULLS NOT DISTINCT (s3_bucket, s3_key, s3_object_version),
    CHECK (state <> 'published' OR (published_by IS NOT NULL AND published_at IS NOT NULL)),
    CHECK ((owner_kind = 'court' AND state <> 'private') OR
        (owner_kind = 'user' AND state IN ('private', 'withdrawn') AND reviewed_by IS NULL AND published_by IS NULL AND published_at IS NULL)),
    index_revision integer NOT NULL DEFAULT 0 CHECK (index_revision >= 0),
    index_state text NOT NULL DEFAULT 'pending' CHECK (index_state IN ('pending', 'ready', 'failed')),
    parser_version text, chunker_version text, index_config jsonb NOT NULL DEFAULT '{}',
    extraction_ref jsonb, embedding_provider text, embedding_model text,
    embedding_dimensions integer CHECK (embedding_dimensions > 0), embedding_config jsonb NOT NULL DEFAULT '{}',
    chunk_count integer NOT NULL DEFAULT 0 CHECK (chunk_count >= 0), indexed_at timestamptz,
    index_error_code text, index_invalidated_at timestamptz,
    CHECK (num_nonnulls(embedding_provider, embedding_model, embedding_dimensions) IN (0, 3)),
    CHECK (index_state <> 'ready' OR (index_revision > 0 AND parser_version IS NOT NULL AND chunker_version IS NOT NULL AND indexed_at IS NOT NULL))
);
CREATE TABLE public.agent_corpus_document (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(), court_topic_id uuid NOT NULL,
    document_id uuid NOT NULL, enabled boolean NOT NULL DEFAULT true,
    UNIQUE (court_topic_id, document_id)
);
CREATE TABLE public.agent_matter_document (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(), matter_id uuid NOT NULL,
    document_id uuid NOT NULL, note text NOT NULL DEFAULT '', UNIQUE (matter_id, document_id)
);
CREATE TABLE public.agent_document_chunk (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(), document_id uuid NOT NULL,
    ordinal integer NOT NULL CHECK (ordinal > 0), body text NOT NULL,
    locator jsonb NOT NULL, text_sha256 text NOT NULL CHECK (text_sha256 ~ '^[0-9a-f]{64}$'),
    embedding public.vector,
    search_vector tsvector GENERATED ALWAYS AS (to_tsvector('english'::regconfig, body)) STORED,
    UNIQUE (document_id, ordinal)
);
CREATE INDEX agent_document_chunk_fts ON public.agent_document_chunk USING gin(search_vector);

CREATE TABLE public.agent_fact_definition (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(), key text NOT NULL,
    version integer NOT NULL CHECK (version > 0), scope text NOT NULL CHECK (scope IN ('user', 'matter')),
    label text NOT NULL, description text NOT NULL DEFAULT '', value_schema jsonb NOT NULL,
    enabled boolean NOT NULL DEFAULT true, UNIQUE (key, version)
);
CREATE TABLE public.agent_fact_assertion (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(), user_id text NOT NULL, matter_id uuid,
    fact_definition_id uuid NOT NULL, value jsonb NOT NULL,
    evidence_kind text NOT NULL CHECK (evidence_kind IN ('user_statement', 'document_extraction', 'model_inference')),
    confirmation_state text NOT NULL DEFAULT 'unconfirmed' CHECK (confirmation_state IN ('unconfirmed', 'confirmed', 'rejected')),
    state text NOT NULL DEFAULT 'active' CHECK (state IN ('active', 'superseded', 'retracted')),
    observed_at timestamptz NOT NULL DEFAULT now(), effective_from timestamptz, effective_to timestamptz,
    supersedes_id uuid, invalidated_at timestamptz,
    CHECK (effective_from IS NULL OR effective_to IS NULL OR effective_from <= effective_to),
    CHECK (supersedes_id IS DISTINCT FROM id)
);
CREATE TABLE public.agent_fact_evidence (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(), fact_assertion_id uuid NOT NULL,
    role text NOT NULL CHECK (role IN ('basis', 'confirmation', 'contradiction')),
    conversation_item_id uuid, document_id uuid, run_step_id uuid,
    locator jsonb NOT NULL DEFAULT '{}', locator_sha256 text NOT NULL CHECK (locator_sha256 ~ '^[0-9a-f]{64}$'),
    CHECK (num_nonnulls(conversation_item_id, document_id, run_step_id) = 1),
    UNIQUE NULLS NOT DISTINCT (fact_assertion_id, role, conversation_item_id, document_id, run_step_id, locator_sha256)
);
CREATE TABLE public.agent_matter_procedure (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(), matter_id uuid NOT NULL, procedure_id uuid NOT NULL,
    state text NOT NULL DEFAULT 'active' CHECK (state IN ('active', 'completed', 'abandoned')),
    started_at timestamptz NOT NULL DEFAULT now(), completed_at timestamptz,
    UNIQUE (matter_id, procedure_id), CHECK ((state = 'completed') = (completed_at IS NOT NULL))
);
CREATE TABLE public.agent_phase_progress (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(), matter_procedure_id uuid NOT NULL,
    phase_id uuid NOT NULL, state text NOT NULL DEFAULT 'not_started'
        CHECK (state IN ('not_started', 'active', 'blocked', 'completed', 'skipped')),
    basis jsonb NOT NULL DEFAULT '{}', last_run_step_id uuid NOT NULL,
    started_at timestamptz, completed_at timestamptz, UNIQUE (matter_procedure_id, phase_id),
    CHECK ((state = 'completed') = (completed_at IS NOT NULL))
);
CREATE TABLE public.agent_memory (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(), user_id text NOT NULL, matter_id uuid,
    kind text NOT NULL CHECK (kind IN ('recall', 'compaction')), body text NOT NULL,
    state text NOT NULL DEFAULT 'active' CHECK (state IN ('active', 'superseded', 'retracted')),
    conversation_id uuid, first_sequence bigint, last_sequence bigint,
    generated_step_id uuid NOT NULL, supersedes_id uuid, invalidated_at timestamptz,
    CHECK (kind <> 'compaction' OR (conversation_id IS NOT NULL
        AND first_sequence IS NOT NULL AND last_sequence IS NOT NULL)),
    CHECK (first_sequence > 0 AND last_sequence >= first_sequence),
    CHECK (supersedes_id IS DISTINCT FROM id)
);
CREATE INDEX agent_memory_fts ON public.agent_memory USING gin(to_tsvector('english'::regconfig, body))
    WHERE state = 'active' AND invalidated_at IS NULL;
CREATE TABLE public.agent_memory_source (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(), memory_id uuid NOT NULL,
    conversation_item_id uuid, fact_assertion_id uuid, document_id uuid,
    locator jsonb NOT NULL DEFAULT '{}', locator_sha256 text NOT NULL CHECK (locator_sha256 ~ '^[0-9a-f]{64}$'),
    CHECK (num_nonnulls(conversation_item_id, fact_assertion_id, document_id) = 1),
    UNIQUE NULLS NOT DISTINCT (memory_id, conversation_item_id, fact_assertion_id, document_id, locator_sha256)
);
CREATE TABLE public.agent_conversation (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(), user_id text NOT NULL,
    matter_id uuid, court_id uuid, topic_id uuid, court_topic_id uuid,
    title text NOT NULL DEFAULT '', state text NOT NULL DEFAULT 'active' CHECK (state IN ('active', 'closed')),
    next_sequence bigint NOT NULL DEFAULT 1 CHECK (next_sequence > 0), deleted_at timestamptz,
    CHECK ((court_id IS NOT NULL AND topic_id IS NOT NULL) = (court_topic_id IS NOT NULL)),
    CHECK (matter_id IS NULL OR court_topic_id IS NOT NULL), UNIQUE (id, user_id)
);
CREATE TABLE public.agent_conversation_item (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(), conversation_id uuid NOT NULL,
    run_id uuid, run_step_id uuid, sequence bigint NOT NULL CHECK (sequence > 0),
    item_kind text NOT NULL CHECK (item_kind IN ('message', 'function_call', 'function_call_output', 'reasoning', 'context')),
    origin text NOT NULL CHECK (origin IN ('user', 'model', 'tool', 'framework')),
    visibility text NOT NULL CHECK (visibility IN ('user', 'internal')),
    context_state text NOT NULL DEFAULT 'pending' CHECK (context_state IN ('pending', 'accepted', 'superseded')),
    payload jsonb NOT NULL, search_text text, deduplication_key text NOT NULL, redacted_at timestamptz,
    UNIQUE (conversation_id, sequence), UNIQUE (conversation_id, deduplication_key),
    CHECK (run_step_id IS NULL OR run_id IS NOT NULL),
    CHECK (item_kind NOT IN ('reasoning', 'context') OR visibility = 'internal'),
    CHECK (search_text IS NULL OR (visibility = 'user' AND item_kind = 'message' AND origin IN ('user', 'model'))),
    CHECK (redacted_at IS NULL OR search_text IS NULL)
);
CREATE INDEX agent_conversation_item_fts ON public.agent_conversation_item
    USING gin(to_tsvector('english'::regconfig, search_text))
    WHERE context_state = 'accepted' AND redacted_at IS NULL AND visibility = 'user' AND item_kind = 'message';
CREATE TABLE public.agent_message_attachment (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(), conversation_item_id uuid NOT NULL,
    document_id uuid NOT NULL, position integer NOT NULL CHECK (position > 0),
    UNIQUE (conversation_item_id, document_id), UNIQUE (conversation_item_id, position)
);
CREATE TABLE public.agent_run (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(), conversation_id uuid NOT NULL,
    request jsonb NOT NULL, configuration jsonb NOT NULL,
    state text NOT NULL DEFAULT 'queued' CHECK (state IN ('queued', 'running', 'waiting_for_input', 'completed', 'failed', 'cancelled')),
    attempt integer NOT NULL DEFAULT 1 CHECK (attempt > 0), lock_version bigint NOT NULL DEFAULT 0 CHECK (lock_version >= 0),
    pending_question jsonb, outcome jsonb, request_key text NOT NULL,
    cancel_requested_at timestamptz, started_at timestamptz, finished_at timestamptz,
    context_court_topic_id uuid, context_format_version integer CHECK (context_format_version = 2),
    context_selected_at timestamptz, resolved_config jsonb, manifest jsonb,
    recall_policy_snapshot jsonb, manifest_sha256 text CHECK (manifest_sha256 ~ '^[0-9a-f]{64}$'),
    checkpoint_sequence bigint NOT NULL DEFAULT 0 CHECK (checkpoint_sequence >= 0),
    checkpoint_format_version integer CHECK (checkpoint_format_version > 0),
    checkpoint_attempt integer CHECK (checkpoint_attempt > 0), checkpoint_step_id uuid,
    checkpoint_conversation_sequence bigint CHECK (checkpoint_conversation_sequence >= 0),
    checkpoint_data jsonb, checkpoint_redacted_at timestamptz,
    CHECK (num_nonnulls(context_court_topic_id, context_format_version, context_selected_at, resolved_config, manifest, recall_policy_snapshot, manifest_sha256) IN (0, 7)),
    CHECK ((checkpoint_sequence = 0 AND num_nonnulls(checkpoint_format_version, checkpoint_attempt, checkpoint_step_id, checkpoint_conversation_sequence, checkpoint_data, checkpoint_redacted_at) = 0)
        OR (checkpoint_sequence > 0 AND checkpoint_format_version IS NOT NULL AND checkpoint_attempt IS NOT NULL AND checkpoint_conversation_sequence IS NOT NULL AND checkpoint_data IS NOT NULL)),
    UNIQUE (conversation_id, request_key), UNIQUE (id, conversation_id),
    CHECK ((state = 'waiting_for_input') = (pending_question IS NOT NULL)),
    CHECK (state NOT IN ('completed', 'failed', 'cancelled') OR (finished_at IS NOT NULL AND outcome IS NOT NULL))
);
CREATE UNIQUE INDEX agent_run_active ON public.agent_run(conversation_id)
    WHERE state IN ('running', 'waiting_for_input');
CREATE TABLE public.agent_run_step (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(), run_id uuid NOT NULL,
    attempt integer NOT NULL CHECK (attempt > 0), sequence integer NOT NULL CHECK (sequence > 0),
    kind text NOT NULL CHECK (kind IN ('context', 'model', 'tool', 'check', 'judge', 'fact_update', 'progress_update')),
    state text NOT NULL DEFAULT 'pending' CHECK (state IN ('pending', 'running', 'completed', 'failed', 'cancelled')),
    operation_key text NOT NULL, input jsonb NOT NULL, output jsonb,
    model_identifier text, tool_name text, tool_call_id text,
    instruction_format text, instruction_canonical_json text,
    instruction_sha256 text CHECK (instruction_sha256 ~ '^[0-9a-f]{64}$'),
    usage jsonb NOT NULL DEFAULT '{}', started_at timestamptz, finished_at timestamptz,
    error_code text, redacted_at timestamptz, UNIQUE (run_id, attempt, sequence),
    UNIQUE (run_id, attempt, operation_key), UNIQUE (id, run_id),
    CHECK (num_nonnulls(instruction_format, instruction_canonical_json, instruction_sha256) IN (0, 3))
);
CREATE UNIQUE INDEX agent_run_step_completed ON public.agent_run_step(run_id, operation_key) WHERE state = 'completed';

-- Common timestamps are separate from the domain columns for readability.
DO $timestamps$
DECLARE t record;
BEGIN
    FOR t IN SELECT tablename FROM pg_tables WHERE schemaname = 'public'
        AND tablename LIKE 'agent\_%' ESCAPE '\'
    LOOP
        EXECUTE format('ALTER TABLE public.%I ADD COLUMN created_at timestamptz NOT NULL DEFAULT now(), ADD COLUMN updated_at timestamptz NOT NULL DEFAULT now()', t.tablename);
    END LOOP;
END
$timestamps$;
