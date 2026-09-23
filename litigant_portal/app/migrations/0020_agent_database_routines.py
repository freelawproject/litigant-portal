"""
Version the specialized PostgreSQL schema with the application.

Vector/search columns are SQL-managed; ordinary fields live in model state.
Server roles are provisioned separately, before migrating an agent installation.
"""

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [("app", "0019_shared_agent_schema")]
    operations = [migrations.RunSQL(
        sql=r"""
CREATE EXTENSION IF NOT EXISTS vector WITH SCHEMA public;

ALTER TABLE public.app_document_chunk
    ADD COLUMN embedding public.vector,
    ADD COLUMN search_vector tsvector GENERATED ALWAYS AS (to_tsvector('english'::regconfig, body)) STORED;

ALTER TABLE public.app_useridentity ADD CONSTRAINT app_useridentity_check_2 CHECK (jsonb_typeof(recall_limits) = 'object');

ALTER TABLE public.app_matter ADD CONSTRAINT app_matter_check_5 CHECK (state IN ('open', 'closed'));

ALTER TABLE public.app_matter ADD CONSTRAINT app_matter_check_10 CHECK ((state = 'closed') = (closed_at IS NOT NULL));

ALTER TABLE public.app_topicflow ADD CONSTRAINT app_topicflow_check_4 CHECK (version > 0);

ALTER TABLE public.app_topicflow ADD CONSTRAINT app_topicflow_check_7 CHECK (state IN ('draft', 'in_review', 'published', 'withdrawn'));

ALTER TABLE public.app_topicflow ADD CONSTRAINT app_topicflow_check_14 CHECK ((version = 1) = (previous_version_id IS NULL));

ALTER TABLE public.app_topicflow ADD CONSTRAINT app_topicflow_check_15 CHECK (state <> 'published' OR ((published_by IS NOT NULL OR import_audit_id IS NOT NULL) AND published_at IS NOT NULL));

ALTER TABLE public.app_topicflowinterviewpage ADD CONSTRAINT app_topicflowinterviewpage_check_3 CHECK ("order" >= 0);

ALTER TABLE public.app_topicflowinterviewvariable ADD CONSTRAINT app_topicflowinterviewvariable_check_3 CHECK ("order" >= 0);

ALTER TABLE public.app_phase_document ADD CONSTRAINT app_phase_document_check_3 CHECK (purpose IN ('guidance', 'form', 'reference'));

ALTER TABLE public.app_phase_document ADD CONSTRAINT app_phase_document_check_4 CHECK (position > 0);

ALTER TABLE public.agent_prompt ADD CONSTRAINT agent_prompt_check_5 CHECK (version > 0);

ALTER TABLE public.agent_prompt ADD CONSTRAINT agent_prompt_check_6 CHECK (btrim(body) <> '');

ALTER TABLE public.agent_prompt ADD CONSTRAINT agent_prompt_check_7 CHECK (state IN ('draft', 'in_review', 'published', 'withdrawn'));

ALTER TABLE public.agent_prompt ADD CONSTRAINT agent_prompt_check_13 CHECK ((version = 1) = (previous_version_id IS NULL));

ALTER TABLE public.agent_prompt ADD CONSTRAINT agent_prompt_check_14 CHECK (state <> 'published' OR ((published_by IS NOT NULL OR import_audit_id IS NOT NULL) AND published_at IS NOT NULL));

ALTER TABLE public.app_document ADD CONSTRAINT app_document_check_1 CHECK (owner_kind IN ('court', 'user'));

ALTER TABLE public.app_document ADD CONSTRAINT app_document_check_6 CHECK (category IN ('source', 'form', 'upload', 'generated'));

ALTER TABLE public.app_document ADD CONSTRAINT app_document_check_9 CHECK ((owner_kind = 'court' AND owner_court_id IS NOT NULL AND owner_user_id IS NULL)
        OR (owner_kind = 'user' AND owner_user_id IS NOT NULL AND owner_court_id IS NULL));

ALTER TABLE public.app_document ADD CONSTRAINT app_document_check_10 CHECK (version > 0);

ALTER TABLE public.app_document ADD CONSTRAINT app_document_check_14 CHECK (sha256 ~ '^[0-9a-f]{64}$');

ALTER TABLE public.app_document ADD CONSTRAINT app_document_check_15 CHECK (byte_size >= 0);

ALTER TABLE public.app_document ADD CONSTRAINT app_document_check_20 CHECK (state IN ('draft', 'in_review', 'published', 'private', 'withdrawn'));

ALTER TABLE public.app_document ADD CONSTRAINT app_document_check_21 CHECK (storage_state IN ('available', 'deleting', 'deleted'));

ALTER TABLE public.app_document ADD CONSTRAINT app_document_check_27 CHECK ((version = 1) = (previous_version_id IS NULL));

ALTER TABLE public.app_document ADD CONSTRAINT app_document_check_29 CHECK (state <> 'published' OR ((published_by IS NOT NULL OR import_audit_id IS NOT NULL) AND published_at IS NOT NULL));

ALTER TABLE public.app_document ADD CONSTRAINT app_document_check_30 CHECK ((owner_kind = 'court' AND state <> 'private') OR
        (owner_kind = 'user' AND state IN ('private', 'withdrawn') AND reviewed_by IS NULL AND published_by IS NULL AND published_at IS NULL));

ALTER TABLE public.app_document ADD CONSTRAINT app_document_check_31 CHECK (index_revision >= 0);

ALTER TABLE public.app_document ADD CONSTRAINT app_document_check_32 CHECK (index_state IN ('pending', 'ready', 'failed'));

ALTER TABLE public.app_document ADD CONSTRAINT app_document_check_39 CHECK (embedding_dimensions > 0);

ALTER TABLE public.app_document ADD CONSTRAINT app_document_check_41 CHECK (chunk_count >= 0);

ALTER TABLE public.app_document ADD CONSTRAINT app_document_check_45 CHECK (num_nonnulls(embedding_provider, embedding_model, embedding_dimensions) IN (0, 3));

ALTER TABLE public.app_document ADD CONSTRAINT app_document_check_46 CHECK (index_state <> 'ready' OR (index_revision > 0 AND parser_version IS NOT NULL AND chunker_version IS NOT NULL AND indexed_at IS NOT NULL));

ALTER TABLE public.app_document_chunk ADD CONSTRAINT app_document_chunk_check_2 CHECK (ordinal > 0);

ALTER TABLE public.app_document_chunk ADD CONSTRAINT app_document_chunk_check_5 CHECK (text_sha256 ~ '^[0-9a-f]{64}$');

ALTER TABLE public.app_variable ADD CONSTRAINT app_variable_check_2 CHECK (version > 0);

ALTER TABLE public.app_variable ADD CONSTRAINT app_variable_check_3 CHECK (true);

ALTER TABLE public.app_variableanswer ADD CONSTRAINT app_variableanswer_check_5 CHECK (evidence_kind IN ('user_statement', 'document_extraction', 'model_inference'));

ALTER TABLE public.app_variableanswer ADD CONSTRAINT app_variableanswer_check_6 CHECK (confirmation_state IN ('unconfirmed', 'confirmed', 'rejected'));

ALTER TABLE public.app_variableanswer ADD CONSTRAINT app_variableanswer_check_7 CHECK (state IN ('active', 'superseded', 'retracted'));

ALTER TABLE public.app_variableanswer ADD CONSTRAINT app_variableanswer_check_13 CHECK (effective_from IS NULL OR effective_to IS NULL OR effective_from <= effective_to);

ALTER TABLE public.app_variableanswer ADD CONSTRAINT app_variableanswer_check_14 CHECK (supersedes_id IS DISTINCT FROM id);

ALTER TABLE public.app_fact_evidence ADD CONSTRAINT app_fact_evidence_check_2 CHECK (role IN ('basis', 'confirmation', 'contradiction'));

ALTER TABLE public.app_fact_evidence ADD CONSTRAINT app_fact_evidence_check_7 CHECK (locator_sha256 ~ '^[0-9a-f]{64}$');

ALTER TABLE public.app_fact_evidence ADD CONSTRAINT app_fact_evidence_check_8 CHECK (num_nonnulls(message_id, document_id, run_step_id, submitted_by_id) = 1);

ALTER TABLE public.app_matter_procedure ADD CONSTRAINT app_matter_procedure_check_3 CHECK (state IN ('active', 'completed', 'abandoned'));

ALTER TABLE public.app_matter_procedure ADD CONSTRAINT app_matter_procedure_check_7 CHECK ((state = 'completed') = (completed_at IS NOT NULL));

ALTER TABLE public.app_phase_progress ADD CONSTRAINT app_phase_progress_check_3 CHECK (state IN ('not_started', 'active', 'blocked', 'completed', 'skipped'));

ALTER TABLE public.app_phase_progress ADD CONSTRAINT app_phase_progress_check_9 CHECK ((state = 'completed') = (completed_at IS NOT NULL));

ALTER TABLE public.agent_memory ADD CONSTRAINT agent_memory_check_3 CHECK (kind IN ('recall', 'compaction'));

ALTER TABLE public.agent_memory ADD CONSTRAINT agent_memory_check_5 CHECK (state IN ('active', 'superseded', 'retracted'));

ALTER TABLE public.agent_memory ADD CONSTRAINT agent_memory_check_12 CHECK (kind <> 'compaction' OR (thread_id IS NOT NULL
        AND first_sequence IS NOT NULL AND last_sequence IS NOT NULL));

ALTER TABLE public.agent_memory ADD CONSTRAINT agent_memory_check_13 CHECK (first_sequence > 0 AND last_sequence >= first_sequence);

ALTER TABLE public.agent_memory ADD CONSTRAINT agent_memory_check_14 CHECK (supersedes_id IS DISTINCT FROM id);

ALTER TABLE public.agent_memory_source ADD CONSTRAINT agent_memory_source_check_6 CHECK (locator_sha256 ~ '^[0-9a-f]{64}$');

ALTER TABLE public.agent_memory_source ADD CONSTRAINT agent_memory_source_check_7 CHECK (num_nonnulls(message_id, answer_id, document_id) = 1);

ALTER TABLE public.app_chatthread ADD CONSTRAINT app_chatthread_check_7 CHECK (status IN ('active', 'closed'));

ALTER TABLE public.app_chatthread ADD CONSTRAINT app_chatthread_check_8 CHECK (next_sequence > 0);

ALTER TABLE public.app_chatthread ADD CONSTRAINT app_chatthread_check_10 CHECK ((court_id IS NOT NULL AND topic_id IS NOT NULL) = (court_topic_id IS NOT NULL));

ALTER TABLE public.app_chatthread ADD CONSTRAINT app_chatthread_check_11 CHECK (matter_id IS NULL OR court_topic_id IS NOT NULL);

ALTER TABLE public.app_chatmessage ADD CONSTRAINT app_chatmessage_check_4 CHECK (sequence > 0);

ALTER TABLE public.app_chatmessage ADD CONSTRAINT app_chatmessage_check_5 CHECK (item_kind IN ('message', 'function_call', 'function_call_output', 'reasoning', 'context'));

ALTER TABLE public.app_chatmessage ADD CONSTRAINT app_chatmessage_check_6 CHECK (origin IN ('user', 'model', 'tool', 'framework'));

ALTER TABLE public.app_chatmessage ADD CONSTRAINT app_chatmessage_check_7 CHECK (true);

ALTER TABLE public.app_chatmessage ADD CONSTRAINT app_chatmessage_check_8 CHECK (context_state IN ('pending', 'accepted', 'superseded'));

ALTER TABLE public.app_chatmessage ADD CONSTRAINT app_chatmessage_check_15 CHECK (run_step_id IS NULL OR run_id IS NOT NULL);

ALTER TABLE public.app_chatmessage ADD CONSTRAINT app_chatmessage_check_16 CHECK (item_kind NOT IN ('reasoning', 'context') OR (hidden OR meta));

ALTER TABLE public.app_chatmessage ADD CONSTRAINT app_chatmessage_check_17 CHECK (search_text IS NULL OR ((NOT hidden AND NOT meta) AND item_kind = 'message' AND origin IN ('user', 'model')));

ALTER TABLE public.app_chatmessage ADD CONSTRAINT app_chatmessage_check_18 CHECK (redacted_at IS NULL OR search_text IS NULL);

ALTER TABLE public.app_message_attachment ADD CONSTRAINT app_message_attachment_check_3 CHECK (position > 0);

ALTER TABLE public.agent_run ADD CONSTRAINT agent_run_check_4 CHECK (state IN ('queued', 'running', 'waiting_for_input', 'completed', 'failed', 'cancelled'));

ALTER TABLE public.agent_run ADD CONSTRAINT agent_run_check_5 CHECK (attempt > 0);

ALTER TABLE public.agent_run ADD CONSTRAINT agent_run_check_6 CHECK (lock_version >= 0);

ALTER TABLE public.agent_run ADD CONSTRAINT agent_run_check_14 CHECK (context_format_version = 2);

ALTER TABLE public.agent_run ADD CONSTRAINT agent_run_check_19 CHECK (manifest_sha256 ~ '^[0-9a-f]{64}$');

ALTER TABLE public.agent_run ADD CONSTRAINT agent_run_check_20 CHECK (checkpoint_sequence >= 0);

ALTER TABLE public.agent_run ADD CONSTRAINT agent_run_check_21 CHECK (checkpoint_format_version > 0);

ALTER TABLE public.agent_run ADD CONSTRAINT agent_run_check_22 CHECK (checkpoint_attempt > 0);

ALTER TABLE public.agent_run ADD CONSTRAINT agent_run_check_24 CHECK (checkpoint_conversation_sequence >= 0);

ALTER TABLE public.agent_run ADD CONSTRAINT agent_run_check_27 CHECK (num_nonnulls(context_court_topic_id, context_format_version, context_selected_at, resolved_config, manifest, recall_policy_snapshot, manifest_sha256) IN (0, 7));

ALTER TABLE public.agent_run ADD CONSTRAINT agent_run_check_28 CHECK ((checkpoint_sequence = 0 AND num_nonnulls(checkpoint_format_version, checkpoint_attempt, checkpoint_step_id, checkpoint_conversation_sequence, checkpoint_data, checkpoint_redacted_at) = 0)
        OR (checkpoint_sequence > 0 AND checkpoint_format_version IS NOT NULL AND checkpoint_attempt IS NOT NULL AND checkpoint_conversation_sequence IS NOT NULL AND checkpoint_data IS NOT NULL));

ALTER TABLE public.agent_run ADD CONSTRAINT agent_run_check_31 CHECK ((state = 'waiting_for_input') = (pending_question IS NOT NULL));

ALTER TABLE public.agent_run ADD CONSTRAINT agent_run_check_32 CHECK (state NOT IN ('completed', 'failed', 'cancelled') OR (finished_at IS NOT NULL AND outcome IS NOT NULL));

ALTER TABLE public.agent_run_step ADD CONSTRAINT agent_run_step_check_2 CHECK (attempt > 0);

ALTER TABLE public.agent_run_step ADD CONSTRAINT agent_run_step_check_3 CHECK (sequence > 0);

ALTER TABLE public.agent_run_step ADD CONSTRAINT agent_run_step_check_4 CHECK (kind IN ('context', 'model', 'tool', 'check', 'judge', 'fact_update', 'progress_update'));

ALTER TABLE public.agent_run_step ADD CONSTRAINT agent_run_step_check_5 CHECK (state IN ('pending', 'running', 'completed', 'failed', 'cancelled'));

ALTER TABLE public.app_chatthread ADD CONSTRAINT app_chatthread_id_identity_id_unique UNIQUE (id, identity_id);

ALTER TABLE public.app_chatmessage ADD CONSTRAINT app_chatmessage_thread_id_sequence_unique UNIQUE (thread_id, sequence);

ALTER TABLE public.app_chatmessage ADD CONSTRAINT app_chatmessage_thread_id_deduplication_key_unique UNIQUE (thread_id, deduplication_key);

ALTER TABLE public.app_document ADD CONSTRAINT app_document_attribution CHECK (created_by IS NOT NULL OR import_audit_id IS NOT NULL);

ALTER TABLE public.agent_prompt ADD CONSTRAINT agent_prompt_attribution CHECK (created_by IS NOT NULL OR import_audit_id IS NOT NULL);

ALTER TABLE public.app_topicflow ADD CONSTRAINT app_topicflow_attribution CHECK (created_by IS NOT NULL OR import_audit_id IS NOT NULL OR (court_topic_id IS NULL AND state = 'draft'));

ALTER TABLE public.app_chatthread ALTER COLUMN "created_at" SET DEFAULT now();

ALTER TABLE public.app_chatthread ALTER COLUMN "updated_at" SET DEFAULT now();

ALTER TABLE public.app_chatthread ALTER COLUMN "id" SET DEFAULT gen_random_uuid();

ALTER TABLE public.app_chatthread ALTER COLUMN "thread_type" SET DEFAULT 'user_chat';

ALTER TABLE public.app_chatthread ALTER COLUMN "state" SET DEFAULT '{}'::jsonb;

ALTER TABLE public.app_chatthread ALTER COLUMN "description" SET DEFAULT '';

ALTER TABLE public.app_chatthread ALTER COLUMN "status" SET DEFAULT 'active';

ALTER TABLE public.app_chatthread ALTER COLUMN "next_sequence" SET DEFAULT 1;

ALTER TABLE public.app_chatmessage ALTER COLUMN "created_at" SET DEFAULT now();

ALTER TABLE public.app_chatmessage ALTER COLUMN "updated_at" SET DEFAULT now();

ALTER TABLE public.app_chatmessage ALTER COLUMN "id" SET DEFAULT gen_random_uuid();

ALTER TABLE public.app_chatmessage ALTER COLUMN "data" SET DEFAULT '{"role": "system", "content": ""}'::jsonb;

ALTER TABLE public.app_chatmessage ALTER COLUMN "hidden" SET DEFAULT false;

ALTER TABLE public.app_chatmessage ALTER COLUMN "meta" SET DEFAULT false;

ALTER TABLE public.app_chatmessage ALTER COLUMN "num_tokens" SET DEFAULT 0;

ALTER TABLE public.app_chatmessage ALTER COLUMN "cost" SET DEFAULT 0.0;

ALTER TABLE public.app_chatmessage ALTER COLUMN "git_sha" SET DEFAULT '';

ALTER TABLE public.app_chatmessage ALTER COLUMN "item_kind" SET DEFAULT 'message';

ALTER TABLE public.app_chatmessage ALTER COLUMN "origin" SET DEFAULT 'framework';

ALTER TABLE public.app_chatmessage ALTER COLUMN "context_state" SET DEFAULT 'pending';

ALTER TABLE public.app_court ALTER COLUMN "slug" SET DEFAULT '';

ALTER TABLE public.app_court ALTER COLUMN "name" SET DEFAULT '';

ALTER TABLE public.app_matter ALTER COLUMN "title" SET DEFAULT '';

ALTER TABLE public.app_phase_document ALTER COLUMN "purpose" SET DEFAULT '';

ALTER TABLE public.app_document ALTER COLUMN "owner_kind" SET DEFAULT '';

ALTER TABLE public.app_document ALTER COLUMN "key" SET DEFAULT '';

ALTER TABLE public.app_document ALTER COLUMN "title" SET DEFAULT '';

ALTER TABLE public.app_document ALTER COLUMN "category" SET DEFAULT '';

ALTER TABLE public.app_document ALTER COLUMN "s3_bucket" SET DEFAULT '';

ALTER TABLE public.app_document ALTER COLUMN "s3_key" SET DEFAULT '';

ALTER TABLE public.app_document ALTER COLUMN "sha256" SET DEFAULT '';

ALTER TABLE public.app_document ALTER COLUMN "media_type" SET DEFAULT '';

ALTER TABLE public.app_document ALTER COLUMN "state" SET DEFAULT '';

ALTER TABLE public.app_document_chunk ALTER COLUMN "body" SET DEFAULT '';

ALTER TABLE public.app_document_chunk ALTER COLUMN "text_sha256" SET DEFAULT '';

ALTER TABLE public.app_fact_evidence ALTER COLUMN "role" SET DEFAULT '';

ALTER TABLE public.app_fact_evidence ALTER COLUMN "locator_sha256" SET DEFAULT '';

ALTER TABLE public.app_topic ALTER COLUMN "created_at" SET DEFAULT now();

ALTER TABLE public.app_topic ALTER COLUMN "updated_at" SET DEFAULT now();

ALTER TABLE public.app_topic ALTER COLUMN "id" SET DEFAULT gen_random_uuid();

ALTER TABLE public.app_topic ALTER COLUMN "slug" SET DEFAULT '';

ALTER TABLE public.app_topic ALTER COLUMN "title" SET DEFAULT '';

ALTER TABLE public.app_topic ALTER COLUMN "subtitle" SET DEFAULT '';

ALTER TABLE public.app_topic ALTER COLUMN "description" SET DEFAULT '';

ALTER TABLE public.app_topic ALTER COLUMN "icon" SET DEFAULT '';

ALTER TABLE public.app_topic ALTER COLUMN "meta_description" SET DEFAULT '';

ALTER TABLE public.app_topic ALTER COLUMN "prompts" SET DEFAULT '[]'::jsonb;

ALTER TABLE public.app_topic ALTER COLUMN "order" SET DEFAULT 0;

ALTER TABLE public.app_topic ALTER COLUMN "enabled" SET DEFAULT true;

ALTER TABLE public.app_topicflow ALTER COLUMN "created_at" SET DEFAULT now();

ALTER TABLE public.app_topicflow ALTER COLUMN "updated_at" SET DEFAULT now();

ALTER TABLE public.app_topicflow ALTER COLUMN "id" SET DEFAULT gen_random_uuid();

ALTER TABLE public.app_topicflow ALTER COLUMN "slug" SET DEFAULT '';

ALTER TABLE public.app_topicflow ALTER COLUMN "name" SET DEFAULT '';

ALTER TABLE public.app_topicflow ALTER COLUMN "enabled" SET DEFAULT false;

ALTER TABLE public.app_topicflow ALTER COLUMN "order" SET DEFAULT 0;

ALTER TABLE public.app_topicflow ALTER COLUMN "version" SET DEFAULT 1;

ALTER TABLE public.app_topicflow ALTER COLUMN "guidance" SET DEFAULT '';

ALTER TABLE public.app_topicflow ALTER COLUMN "metadata" SET DEFAULT '{}'::jsonb;

ALTER TABLE public.app_topicflow ALTER COLUMN "state" SET DEFAULT 'draft';

ALTER TABLE public.app_variable ALTER COLUMN "created_at" SET DEFAULT now();

ALTER TABLE public.app_variable ALTER COLUMN "updated_at" SET DEFAULT now();

ALTER TABLE public.app_variable ALTER COLUMN "id" SET DEFAULT gen_random_uuid();

ALTER TABLE public.app_variable ALTER COLUMN "name" SET DEFAULT '';

ALTER TABLE public.app_variable ALTER COLUMN "label" SET DEFAULT '';

ALTER TABLE public.app_variable ALTER COLUMN "question" SET DEFAULT '';

ALTER TABLE public.app_variable ALTER COLUMN "help_text" SET DEFAULT '';

ALTER TABLE public.app_variable ALTER COLUMN "required" SET DEFAULT false;

ALTER TABLE public.app_variable ALTER COLUMN "data_type" SET DEFAULT 'text';

ALTER TABLE public.app_variable ALTER COLUMN "choices" SET DEFAULT '[]'::jsonb;

ALTER TABLE public.app_variable ALTER COLUMN "is_global" SET DEFAULT false;

ALTER TABLE public.app_variable ALTER COLUMN "in_schema" SET DEFAULT true;

ALTER TABLE public.app_variable ALTER COLUMN "version" SET DEFAULT 1;

ALTER TABLE public.app_variable ALTER COLUMN "value_schema" SET DEFAULT '{}'::jsonb;

ALTER TABLE public.app_variableanswer ALTER COLUMN "created_at" SET DEFAULT now();

ALTER TABLE public.app_variableanswer ALTER COLUMN "updated_at" SET DEFAULT now();

ALTER TABLE public.app_variableanswer ALTER COLUMN "id" SET DEFAULT gen_random_uuid();

ALTER TABLE public.app_variableanswer ALTER COLUMN "reviewed" SET DEFAULT false;

ALTER TABLE public.app_variableanswer ALTER COLUMN "evidence_kind" SET DEFAULT 'user_statement';

ALTER TABLE public.app_variableanswer ALTER COLUMN "confirmation_state" SET DEFAULT 'unconfirmed';

ALTER TABLE public.app_variableanswer ALTER COLUMN "state" SET DEFAULT 'active';

ALTER TABLE public.app_topicflowinterviewpage ALTER COLUMN "created_at" SET DEFAULT now();

ALTER TABLE public.app_topicflowinterviewpage ALTER COLUMN "updated_at" SET DEFAULT now();

ALTER TABLE public.app_topicflowinterviewpage ALTER COLUMN "id" SET DEFAULT gen_random_uuid();

ALTER TABLE public.app_topicflowinterviewpage ALTER COLUMN "title" SET DEFAULT '';

ALTER TABLE public.app_topicflowinterviewpage ALTER COLUMN "description" SET DEFAULT '';

ALTER TABLE public.app_topicflowinterviewpage ALTER COLUMN "order" SET DEFAULT 0;

ALTER TABLE public.app_topicflowinterviewpage ALTER COLUMN "key" SET DEFAULT '';

ALTER TABLE public.app_topicflowinterviewpage ALTER COLUMN "instructions" SET DEFAULT '';

ALTER TABLE public.app_topicflowinterviewpage ALTER COLUMN "completion_criteria" SET DEFAULT '[]'::jsonb;

ALTER TABLE public.app_topicflowinterviewvariable ALTER COLUMN "created_at" SET DEFAULT now();

ALTER TABLE public.app_topicflowinterviewvariable ALTER COLUMN "updated_at" SET DEFAULT now();

ALTER TABLE public.app_topicflowinterviewvariable ALTER COLUMN "id" SET DEFAULT gen_random_uuid();

ALTER TABLE public.app_topicflowinterviewvariable ALTER COLUMN "order" SET DEFAULT 0;

ALTER TABLE public.app_topicflowinterviewvariable ALTER COLUMN "required" SET DEFAULT false;

ALTER TABLE public.app_topicflowdeadline ALTER COLUMN "created_at" SET DEFAULT now();

ALTER TABLE public.app_topicflowdeadline ALTER COLUMN "updated_at" SET DEFAULT now();

ALTER TABLE public.app_topicflowdeadline ALTER COLUMN "id" SET DEFAULT gen_random_uuid();

ALTER TABLE public.app_topicflowdeadline ALTER COLUMN "label" SET DEFAULT '';

ALTER TABLE public.app_topicflowdeadline ALTER COLUMN "description" SET DEFAULT '';

ALTER TABLE public.app_topicflowdeadline ALTER COLUMN "offset_days" SET DEFAULT 0;

ALTER TABLE public.app_topicflowdeadline ALTER COLUMN "order" SET DEFAULT 0;

ALTER TABLE public.app_useridentity ALTER COLUMN "created_at" SET DEFAULT now();

ALTER TABLE public.app_useridentity ALTER COLUMN "updated_at" SET DEFAULT now();

ALTER TABLE public.app_useridentity ALTER COLUMN "session_key" SET DEFAULT '';

ALTER TABLE public.app_useridentity ALTER COLUMN "recall_limits" SET DEFAULT '{}'::jsonb;

ALTER TABLE public.agent_prompt ALTER COLUMN "key" SET DEFAULT '';

ALTER TABLE public.agent_prompt ALTER COLUMN "body" SET DEFAULT '';

ALTER TABLE public.agent_memory ALTER COLUMN "kind" SET DEFAULT '';

ALTER TABLE public.agent_memory ALTER COLUMN "body" SET DEFAULT '';

ALTER TABLE public.agent_memory_source ALTER COLUMN "locator_sha256" SET DEFAULT '';

ALTER TABLE public.agent_run ALTER COLUMN "request_key" SET DEFAULT '';

ALTER TABLE public.agent_run_step ALTER COLUMN "kind" SET DEFAULT '';

ALTER TABLE public.agent_run_step ALTER COLUMN "operation_key" SET DEFAULT '';

CREATE INDEX agent_document_chunk_fts ON public.app_document_chunk USING gin(search_vector);

CREATE INDEX agent_memory_fts ON public.agent_memory USING gin(to_tsvector('english'::regconfig, body))
    WHERE state = 'active' AND invalidated_at IS NULL;

CREATE INDEX agent_conversation_item_fts ON public.app_chatmessage
    USING gin(to_tsvector('english'::regconfig, search_text))
    WHERE context_state = 'accepted' AND redacted_at IS NULL AND (NOT hidden AND NOT meta) AND item_kind = 'message';

CREATE UNIQUE INDEX agent_run_active ON public.agent_run(thread_id)
    WHERE state IN ('running', 'waiting_for_input');

CREATE UNIQUE INDEX agent_run_step_completed ON public.agent_run_step(run_id, operation_key) WHERE state = 'completed';

ALTER TABLE public.app_chatthread ADD CONSTRAINT shared_scope_fk_1 FOREIGN KEY (matter_id, identity_id, court_topic_id)
    REFERENCES public.app_matter(id, identity_id, court_topic_id);
ALTER TABLE public.app_chatthread ADD CONSTRAINT shared_scope_fk_2 FOREIGN KEY (court_topic_id, court_id, topic_id)
    REFERENCES public.app_court_topic(id, court_id, topic_id);
ALTER TABLE public.app_variableanswer ADD CONSTRAINT shared_scope_fk_3 FOREIGN KEY (matter_id, identity_id)
    REFERENCES public.app_matter(id, identity_id);
ALTER TABLE public.agent_memory ADD CONSTRAINT shared_scope_fk_4 FOREIGN KEY (matter_id, identity_id)
    REFERENCES public.app_matter(id, identity_id);
ALTER TABLE public.agent_memory ADD CONSTRAINT shared_scope_fk_5 FOREIGN KEY (thread_id, identity_id)
    REFERENCES public.app_chatthread(id, identity_id);
ALTER TABLE public.app_chatmessage ADD CONSTRAINT shared_scope_fk_6 FOREIGN KEY (run_id, thread_id)
    REFERENCES public.agent_run(id, thread_id);
ALTER TABLE public.app_chatmessage ADD CONSTRAINT shared_scope_fk_7 FOREIGN KEY (run_step_id, run_id)
    REFERENCES public.agent_run_step(id, run_id);
ALTER TABLE public.agent_run ADD CONSTRAINT shared_scope_fk_8 FOREIGN KEY (checkpoint_step_id, id)
    REFERENCES public.agent_run_step(id, run_id);

CREATE INDEX agent_matter_recent ON public.app_matter(identity_id, updated_at DESC);
CREATE INDEX agent_conversation_recent ON public.app_chatthread(identity_id, updated_at DESC);
CREATE INDEX agent_run_state ON public.agent_run(state, updated_at);
CREATE INDEX agent_fact_active ON public.app_variableanswer(identity_id, variable_id, matter_id, observed_at DESC)
    WHERE state = 'active' AND invalidated_at IS NULL;
CREATE INDEX agent_document_work ON public.app_document(storage_state, index_state);

-- Trigger helpers are internal routines, not model-callable tools.
CREATE FUNCTION public.agent_touch_updated_at() RETURNS trigger
LANGUAGE plpgsql SET search_path = pg_catalog, public, pg_temp AS $$
BEGIN
    IF TG_TABLE_NAME = 'app_chatthread' AND
        (to_jsonb(OLD) - 'next_sequence') = (to_jsonb(NEW) - 'next_sequence') THEN
        RETURN NEW;
    END IF;
    NEW.updated_at := clock_timestamp();
    RETURN NEW;
END
$$;

CREATE FUNCTION public.agent_guard_immutable() RETURNS trigger
LANGUAGE plpgsql SET search_path = pg_catalog, public, pg_temp AS $$
DECLARE old_data jsonb := to_jsonb(OLD); new_data jsonb := to_jsonb(NEW);
    frozen boolean := false; allowed text[] := ARRAY['updated_at']; parent_state text; field text;
BEGIN
    IF TG_OP = 'UPDATE' AND old_data->'id' IS DISTINCT FROM new_data->'id' THEN
        RAISE EXCEPTION 'Agent primary keys are immutable' USING ERRCODE = '23514';
    END IF;
    IF TG_TABLE_NAME IN ('app_chatthread', 'app_variableanswer')
        AND old_data->>'matter_id' IS NULL AND new_data->>'matter_id' IS NULL
        AND old_data->>'identity_id' IS DISTINCT FROM new_data->>'identity_id'
        AND current_user = pg_get_userbyid((SELECT relowner FROM pg_class WHERE oid = 'public.app_useridentity'::regclass))
        AND EXISTS (SELECT FROM public.app_useridentity WHERE id = (old_data->>'identity_id')::bigint AND user_id IS NULL)
        AND EXISTS (SELECT FROM public.app_useridentity WHERE id = (new_data->>'identity_id')::bigint AND user_id IS NOT NULL) THEN
        old_data := jsonb_set(old_data, '{identity_id}', new_data->'identity_id');
        OLD.identity_id := NEW.identity_id;
    END IF;
    CASE TG_TABLE_NAME
    WHEN 'app_useridentity' THEN
        IF OLD.id IS DISTINCT FROM NEW.id THEN
            RAISE EXCEPTION 'Agent user identity is immutable' USING ERRCODE = '23514';
        END IF;
    WHEN 'app_matter' THEN
        IF (OLD.identity_id, OLD.court_topic_id) IS DISTINCT FROM (NEW.identity_id, NEW.court_topic_id) THEN
            RAISE EXCEPTION 'Matter ownership and scope are immutable' USING ERRCODE = '23514';
        END IF;
    WHEN 'app_chatthread' THEN
        IF OLD.identity_id IS DISTINCT FROM NEW.identity_id
            OR (OLD.matter_id IS NOT NULL AND OLD.matter_id IS DISTINCT FROM NEW.matter_id)
            OR (OLD.court_id IS NOT NULL AND OLD.court_id IS DISTINCT FROM NEW.court_id)
            OR (OLD.topic_id IS NOT NULL AND OLD.topic_id IS DISTINCT FROM NEW.topic_id) THEN
            RAISE EXCEPTION 'Bound conversation ownership and scope are immutable' USING ERRCODE = '23514';
        END IF;
    WHEN 'app_court_topic' THEN
        frozen := true; allowed := allowed || ARRAY['config', 'enabled'];
    WHEN 'app_topicflow', 'agent_prompt', 'app_document' THEN
        FOREACH field IN ARRAY ARRAY['key','slug','court_topic_id','owner_kind','owner_court_id','owner_user_id','version','previous_version_id'] LOOP
            IF old_data->field IS DISTINCT FROM new_data->field THEN
                RAISE EXCEPTION 'Revision identity and lineage are immutable' USING ERRCODE = '23514';
            END IF;
        END LOOP;
        frozen := OLD.state IN ('published','private','withdrawn');
        allowed := allowed || ARRAY['state'];
        IF TG_TABLE_NAME = 'app_document' THEN
            allowed := allowed || ARRAY['storage_state','deleted_at','index_revision','index_state','parser_version',
                'chunker_version','index_config','extraction_ref','embedding_provider','embedding_model','embedding_dimensions',
                'embedding_config','chunk_count','indexed_at','index_error_code','index_invalidated_at'];
            IF NEW.index_revision < OLD.index_revision THEN RAISE EXCEPTION 'Index revision cannot decrease' USING ERRCODE = '23514'; END IF;
            IF OLD.index_state = 'ready' AND NEW.index_state <> 'ready' AND NEW.index_invalidated_at IS NULL THEN
                RAISE EXCEPTION 'A failed rebuild must preserve the usable index' USING ERRCODE = '23514';
            END IF;
            FOREACH field IN ARRAY ARRAY['parser_version','chunker_version','index_config','extraction_ref','embedding_provider',
                'embedding_model','embedding_dimensions','embedding_config','chunk_count','indexed_at'] LOOP
                IF OLD.index_state = 'ready' AND old_data->field IS DISTINCT FROM new_data->field AND NEW.index_revision <= OLD.index_revision THEN
                    RAISE EXCEPTION 'Replacing index settings requires a newer index revision' USING ERRCODE = '23514';
                END IF;
            END LOOP;
        END IF;
        IF frozen AND OLD.state IS DISTINCT FROM NEW.state AND NOT (OLD.state IN ('published','private') AND NEW.state = 'withdrawn') THEN
            RAISE EXCEPTION 'Published/private revisions may only be withdrawn' USING ERRCODE = '23514';
        END IF;
    WHEN 'app_topicflowinterviewpage', 'app_topicflowinterviewvariable', 'app_phase_document', 'app_topicflowdeadline' THEN
        IF TG_TABLE_NAME = 'app_topicflowinterviewpage' THEN
            SELECT state INTO parent_state FROM public.app_topicflow
                WHERE id = (old_data->>'flow_id')::uuid;
        ELSE
            SELECT v.state INTO parent_state FROM public.app_topicflowinterviewpage p
                JOIN public.app_topicflow v ON v.id = p.flow_id
                WHERE p.id = (old_data->>'page_id')::uuid;
        END IF;
        frozen := parent_state IN ('published', 'withdrawn');
    WHEN 'app_variable' THEN
        frozen := EXISTS (SELECT FROM public.app_variableanswer WHERE variable_id = OLD.id) OR EXISTS (SELECT FROM public.app_topicflowinterviewvariable v JOIN public.app_topicflowinterviewpage p ON p.id = v.page_id JOIN public.app_topicflow f ON f.id = p.flow_id WHERE v.variable_id = OLD.id AND f.state IN ('published', 'withdrawn')); allowed := allowed || ARRAY['in_schema'];
    WHEN 'agent_run' THEN
        IF OLD.thread_id IS DISTINCT FROM NEW.thread_id THEN
            RAISE EXCEPTION 'Run conversation is immutable' USING ERRCODE = '23514';
        END IF;
        IF OLD.context_selected_at IS NOT NULL THEN
            FOREACH field IN ARRAY ARRAY['context_court_topic_id','context_format_version','context_selected_at',
                'resolved_config','manifest','recall_policy_snapshot','manifest_sha256'] LOOP
                IF old_data->field IS DISTINCT FROM new_data->field THEN RAISE EXCEPTION 'Selected run context is immutable' USING ERRCODE = '23514'; END IF;
            END LOOP;
        END IF;
        IF NEW.checkpoint_sequence < OLD.checkpoint_sequence THEN RAISE EXCEPTION 'Checkpoint sequence cannot decrease' USING ERRCODE = '23514'; END IF;
        FOREACH field IN ARRAY ARRAY['checkpoint_format_version','checkpoint_attempt','checkpoint_step_id','checkpoint_conversation_sequence','checkpoint_data'] LOOP
            IF old_data->field IS DISTINCT FROM new_data->field AND NEW.checkpoint_sequence <= OLD.checkpoint_sequence
                AND NOT (field = 'checkpoint_data' AND NEW.checkpoint_redacted_at IS NOT NULL AND NEW.checkpoint_data = '{}'::jsonb) THEN
                RAISE EXCEPTION 'Replacing recovery state requires a newer checkpoint' USING ERRCODE = '23514';
            END IF;
        END LOOP;
    WHEN 'agent_run_step' THEN
        IF (OLD.run_id, OLD.attempt, OLD.sequence, OLD.operation_key)
            IS DISTINCT FROM (NEW.run_id, NEW.attempt, NEW.sequence, NEW.operation_key) THEN
            RAISE EXCEPTION 'Step identity is immutable' USING ERRCODE = '23514';
        END IF;
        IF OLD.state = 'completed' AND NEW.redacted_at IS NULL THEN frozen := true; END IF;
    WHEN 'app_chatmessage' THEN
        IF (OLD.thread_id, OLD.run_id, OLD.run_step_id, OLD.sequence, OLD.deduplication_key, OLD.origin, OLD.item_kind, OLD.hidden)
            IS DISTINCT FROM (NEW.thread_id, NEW.run_id, NEW.run_step_id, NEW.sequence, NEW.deduplication_key, NEW.origin, NEW.item_kind, NEW.hidden) THEN
            RAISE EXCEPTION 'Conversation item lineage is immutable' USING ERRCODE = '23514';
        END IF;
    WHEN 'app_document_chunk' THEN
        IF OLD.document_id IS DISTINCT FROM NEW.document_id THEN
            RAISE EXCEPTION 'Chunk source is immutable' USING ERRCODE = '23514';
        END IF;
    WHEN 'app_fact_evidence', 'agent_memory_source' THEN frozen := true;
    WHEN 'app_variableanswer' THEN
        frozen := true; allowed := allowed || ARRAY['state', 'confirmation_state', 'reviewed', 'invalidated_at', 'value'];
        IF OLD.value IS DISTINCT FROM NEW.value AND NOT (NEW.invalidated_at IS NOT NULL AND NEW.value = 'null'::jsonb) THEN
            RAISE EXCEPTION 'Correct a fact with a new assertion; only redaction clears its value' USING ERRCODE = '23514';
        END IF;
    WHEN 'agent_memory' THEN
        frozen := true; allowed := allowed || ARRAY['state', 'invalidated_at', 'body'];
        IF OLD.body IS DISTINCT FROM NEW.body AND NOT (NEW.invalidated_at IS NOT NULL AND NEW.body = '') THEN
            RAISE EXCEPTION 'Replace a memory with a new record; only redaction clears its body' USING ERRCODE = '23514';
        END IF;
    ELSE NULL;
    END CASE;
    IF frozen AND (TG_OP = 'DELETE' OR (old_data - allowed) IS DISTINCT FROM (new_data - allowed)) THEN
        RAISE EXCEPTION 'Agent revision or lineage is immutable' USING ERRCODE = '23514';
    END IF;
    RETURN CASE WHEN TG_OP = 'DELETE' THEN OLD ELSE NEW END;
END
$$;

CREATE FUNCTION public.agent_validate_record() RETURNS trigger
LANGUAGE plpgsql SET search_path = pg_catalog, public, pg_temp AS $$
DECLARE owner_id bigint; source_owner bigint; scope_id uuid; other_scope uuid;
    parent_state text; parent_kind text; actual_count integer; bad_count integer; fact_scope text; fact_key text;
    j jsonb := to_jsonb(NEW); previous jsonb; field text; doc public.app_document%ROWTYPE; source_id uuid;
    entry record; anchor jsonb; selected jsonb; target_table text; highest integer;
BEGIN
    -- Check the final chunk set at commit, allowing an atomic delete/insert replacement.
    IF TG_NARGS = 1 AND TG_ARGV[0] = 'index' THEN
        IF TG_TABLE_NAME = 'app_document' THEN source_id := coalesce(NEW.id, OLD.id);
        ELSE source_id := coalesce(NEW.document_id, OLD.document_id); END IF;
        SELECT * INTO doc FROM public.app_document WHERE id = source_id;
        IF NOT FOUND THEN RETURN NULL; END IF;
        SELECT count(*), count(*) FILTER (WHERE
            (doc.embedding_dimensions IS NULL AND embedding IS NOT NULL) OR
            (doc.embedding_dimensions IS NOT NULL AND (embedding IS NULL OR public.vector_dims(embedding) <> doc.embedding_dimensions)) OR
            length(body) > coalesce((doc.index_config->>'max_characters')::integer, 65536))
            INTO actual_count, bad_count FROM public.app_document_chunk WHERE document_id = source_id;
        IF doc.index_invalidated_at IS NULL AND (bad_count > 0 OR
            (doc.index_state = 'ready' AND actual_count <> doc.chunk_count) OR
            (doc.index_state <> 'ready' AND actual_count > 0)) THEN
            RAISE EXCEPTION 'Active index must contain its declared bounded chunks and matching embeddings' USING ERRCODE = '23514';
        END IF;
        RETURN NULL;
    END IF;
    CASE TG_TABLE_NAME
    WHEN 'app_topicflow', 'agent_prompt', 'app_document' THEN
        IF NEW.previous_version_id IS NOT NULL THEN
            EXECUTE format('SELECT to_jsonb(p) FROM public.%I p WHERE id = $1',TG_TABLE_NAME) INTO previous USING NEW.previous_version_id;
            IF previous IS NULL OR NEW.version <> (previous->>'version')::integer + 1 THEN
                RAISE EXCEPTION 'Revision must follow its immediate predecessor' USING ERRCODE = '23514';
            END IF;
            FOREACH field IN ARRAY ARRAY['key','slug','court_topic_id','owner_kind','owner_court_id','owner_user_id'] LOOP
                IF previous->field IS DISTINCT FROM j->field THEN
                    RAISE EXCEPTION 'Predecessor belongs to a different revision family' USING ERRCODE = '23514';
                END IF;
            END LOOP;
        END IF;
        IF TG_TABLE_NAME = 'app_topicflow' AND j->>'state' = 'published' AND EXISTS (
            SELECT FROM public.app_topicflowinterviewpage ph JOIN public.app_phase_document pd ON pd.page_id = ph.id
            WHERE ph.flow_id = NEW.id AND NOT EXISTS (SELECT FROM public.app_corpus_document cd
                WHERE cd.court_topic_id = (j->>'court_topic_id')::uuid AND cd.document_id = pd.document_id AND cd.enabled)
        ) THEN RAISE EXCEPTION 'Procedure references a document outside its corpus' USING ERRCODE = '23514'; END IF;
    WHEN 'app_corpus_document' THEN
        SELECT ct.court_id, d.owner_court_id INTO scope_id, other_scope
            FROM public.app_court_topic ct, public.app_document d
            WHERE ct.id = NEW.court_topic_id AND d.id = NEW.document_id AND d.version = 1;
        IF scope_id IS DISTINCT FROM other_scope OR scope_id IS NULL THEN
            RAISE EXCEPTION 'Corpus document must belong to the same court' USING ERRCODE = '23514';
        END IF;
    WHEN 'app_matter_document' THEN
        SELECT m.identity_id, d.owner_user_id INTO owner_id, source_owner
            FROM public.app_matter m, public.app_document d WHERE m.id = NEW.matter_id AND d.id = NEW.document_id AND d.version = 1;
        IF owner_id IS DISTINCT FROM source_owner OR owner_id IS NULL THEN
            RAISE EXCEPTION 'Matter document owner mismatch' USING ERRCODE = '23514';
        END IF;
    WHEN 'app_topicflowinterviewpage', 'app_topicflowinterviewvariable', 'app_phase_document', 'app_topicflowdeadline' THEN
        IF TG_TABLE_NAME = 'app_topicflowinterviewpage' THEN
            SELECT state INTO parent_state FROM public.app_topicflow WHERE id = NEW.flow_id;
        ELSE
            SELECT p.state, p.court_topic_id INTO parent_state, scope_id
                FROM public.app_topicflowinterviewpage ph JOIN public.app_topicflow p ON p.id = ph.flow_id WHERE ph.id = (j->>'page_id')::uuid;
        END IF;
        IF parent_state IN ('published', 'withdrawn') THEN
            RAISE EXCEPTION 'Edit phases only within a draft revision' USING ERRCODE = '23514';
        END IF;
        IF TG_TABLE_NAME = 'app_phase_document' AND NOT EXISTS (
            SELECT FROM public.app_corpus_document WHERE court_topic_id = scope_id AND document_id = (j->>'document_id')::uuid AND enabled
        ) THEN
            RAISE EXCEPTION 'Phase document must belong to its court/topic corpus' USING ERRCODE = '23514';
        END IF;
    WHEN 'app_document_chunk' THEN
        IF NEW.text_sha256 <> encode(sha256(convert_to(NEW.body,'UTF8')),'hex') THEN
            RAISE EXCEPTION 'Chunk text digest mismatch' USING ERRCODE = '23514';
        END IF;
        PERFORM id FROM public.app_document WHERE id = NEW.document_id FOR UPDATE;
    WHEN 'app_variableanswer' THEN
        IF NEW.reviewed AND NEW.state = 'active' AND NEW.invalidated_at IS NULL THEN
            PERFORM pg_advisory_xact_lock(hashtextextended(NEW.identity_id::text || ':' || coalesce(NEW.matter_id::text, '') || ':' || (SELECT name FROM public.app_variable WHERE id = NEW.variable_id), 0));
            IF EXISTS (SELECT FROM public.app_variableanswer a JOIN public.app_variable v ON v.id = a.variable_id JOIN public.app_variable current ON current.id = NEW.variable_id AND current.name = v.name
                WHERE a.id <> NEW.id AND a.identity_id = NEW.identity_id AND a.matter_id IS NOT DISTINCT FROM NEW.matter_id AND a.reviewed AND a.state = 'active' AND a.invalidated_at IS NULL) THEN
                RAISE EXCEPTION 'Only one current reviewed answer per identity, matter, and fact' USING ERRCODE = '23514';
            END IF;
        END IF;
        SELECT CASE WHEN is_global THEN 'user' ELSE 'matter' END, name INTO fact_scope, fact_key FROM public.app_variable WHERE id = NEW.variable_id;
        IF fact_scope = 'user' AND NEW.matter_id IS NOT NULL THEN
            RAISE EXCEPTION 'Fact scope mismatch' USING ERRCODE = '23514';
        END IF;
        IF NEW.supersedes_id IS NOT NULL AND NOT EXISTS (
            SELECT FROM public.app_variableanswer a JOIN public.app_variable d ON d.id = a.variable_id
            WHERE a.id = NEW.supersedes_id AND a.identity_id = NEW.identity_id
                AND a.matter_id IS NOT DISTINCT FROM NEW.matter_id AND d.name = fact_key AND (CASE WHEN d.is_global THEN 'user' ELSE 'matter' END) = fact_scope
        ) THEN RAISE EXCEPTION 'Fact supersession owner/key/scope mismatch' USING ERRCODE = '23514'; END IF;
    WHEN 'app_variable' THEN
        IF EXISTS (SELECT FROM public.app_variable WHERE name = NEW.name AND is_global <> NEW.is_global) THEN
            RAISE EXCEPTION 'A semantic fact key cannot change scope between versions' USING ERRCODE = '23514';
        END IF;
    WHEN 'app_matter_procedure' THEN
        SELECT m.court_topic_id, p.court_topic_id INTO scope_id, other_scope
            FROM public.app_matter m, public.app_topicflow p WHERE m.id = NEW.matter_id AND p.id = NEW.flow_id AND p.version = 1;
        IF scope_id IS DISTINCT FROM other_scope OR scope_id IS NULL THEN RAISE EXCEPTION 'Matter procedure scope mismatch' USING ERRCODE = '23514'; END IF;
    WHEN 'app_phase_progress' THEN
        IF NEW.last_run_step_id IS NULL THEN
            IF NOT EXISTS (SELECT FROM public.app_matter_procedure mp JOIN public.app_topicflow base ON base.id = mp.flow_id JOIN public.app_topicflowinterviewpage ph ON ph.id = NEW.page_id JOIN public.app_topicflow p ON p.id = ph.flow_id AND p.slug = base.slug AND p.court_topic_id = base.court_topic_id WHERE mp.id = NEW.matter_procedure_id) THEN
                RAISE EXCEPTION 'Guided progress phase does not belong to the matter procedure' USING ERRCODE = '23514';
            END IF;
            RETURN NEW;
        END IF;
        IF NOT EXISTS (SELECT FROM public.app_matter_procedure mp JOIN public.app_topicflow base ON base.id = mp.flow_id
            JOIN public.app_topicflowinterviewpage ph ON ph.id = NEW.page_id JOIN public.app_topicflow p ON p.id = ph.flow_id
                AND p.slug = base.slug AND p.court_topic_id = base.court_topic_id
            JOIN public.agent_run_step s ON s.id = NEW.last_run_step_id JOIN public.agent_run r ON r.id = s.run_id
            JOIN public.app_chatthread c ON c.id = r.thread_id AND c.matter_id = mp.matter_id
            WHERE mp.id = NEW.matter_procedure_id AND r.manifest->'procedures'->>base.id::text = p.id::text) THEN
            RAISE EXCEPTION 'Progress must use this matter and its pinned phase revision' USING ERRCODE = '23514';
        END IF;
    WHEN 'agent_memory' THEN
        SELECT c.identity_id INTO source_owner FROM public.agent_run_step s JOIN public.agent_run r ON r.id = s.run_id
            JOIN public.app_chatthread c ON c.id = r.thread_id WHERE s.id = NEW.generated_step_id;
        IF NEW.identity_id IS DISTINCT FROM source_owner THEN RAISE EXCEPTION 'Memory generation owner mismatch' USING ERRCODE = '23514'; END IF;
        IF NEW.supersedes_id IS NOT NULL AND NOT EXISTS (SELECT FROM public.agent_memory WHERE id = NEW.supersedes_id AND identity_id = NEW.identity_id) THEN
            RAISE EXCEPTION 'Memory supersession owner mismatch' USING ERRCODE = '23514';
        END IF;
    WHEN 'app_fact_evidence', 'agent_memory_source' THEN
        IF TG_TABLE_NAME = 'app_fact_evidence' THEN
            SELECT identity_id INTO owner_id FROM public.app_variableanswer WHERE id = NEW.answer_id;
        ELSE SELECT identity_id INTO owner_id FROM public.agent_memory WHERE id = NEW.memory_id;
        END IF;
        IF j->>'submitted_by_id' IS NOT NULL THEN
            source_owner := (j->>'submitted_by_id')::bigint;
        ELSIF j->>'message_id' IS NOT NULL THEN
            SELECT c.identity_id INTO source_owner FROM public.app_chatmessage i
                JOIN public.app_chatthread c ON c.id = i.thread_id WHERE i.id = (j->>'message_id')::uuid;
        ELSIF j->>'document_id' IS NOT NULL THEN
            SELECT owner_user_id, owner_kind INTO source_owner, parent_kind
                FROM public.app_document WHERE id = (j->>'document_id')::uuid;
            IF parent_kind = 'court' THEN source_owner := owner_id; END IF;
        ELSIF j->>'run_step_id' IS NOT NULL THEN
            SELECT c.identity_id INTO source_owner FROM public.agent_run_step s JOIN public.agent_run r ON r.id = s.run_id
                JOIN public.app_chatthread c ON c.id = r.thread_id WHERE s.id = (j->>'run_step_id')::uuid;
        ELSE SELECT identity_id INTO source_owner FROM public.app_variableanswer WHERE id = (j->>'answer_id')::uuid;
        END IF;
        IF owner_id IS DISTINCT FROM source_owner OR source_owner IS NULL THEN
            RAISE EXCEPTION 'Private evidence/source owner mismatch' USING ERRCODE = '23514';
        END IF;
    WHEN 'app_message_attachment' THEN
        SELECT c.identity_id INTO owner_id FROM public.app_chatmessage i JOIN public.app_chatthread c ON c.id = i.thread_id
            WHERE i.id = NEW.message_id AND i.item_kind = 'message' AND (NOT i.hidden AND NOT i.meta);
        SELECT owner_user_id INTO source_owner FROM public.app_document WHERE id = NEW.document_id;
        IF owner_id IS DISTINCT FROM source_owner OR owner_id IS NULL THEN
            RAISE EXCEPTION 'Attachment must match the message owner' USING ERRCODE = '23514';
        END IF;
    WHEN 'agent_run' THEN
        IF NEW.checkpoint_sequence > 0 AND NEW.checkpoint_conversation_sequence > 0 AND NOT EXISTS (
            SELECT FROM public.app_chatmessage WHERE thread_id = NEW.thread_id AND sequence = NEW.checkpoint_conversation_sequence
        ) THEN RAISE EXCEPTION 'Checkpoint cursor must belong to this conversation' USING ERRCODE = '23514'; END IF;
        IF NEW.context_selected_at IS NOT NULL AND (TG_OP = 'INSERT' OR OLD.context_selected_at IS NULL) THEN
            SELECT court_topic_id INTO scope_id FROM public.app_chatthread WHERE id = NEW.thread_id;
            IF scope_id IS DISTINCT FROM NEW.context_court_topic_id THEN RAISE EXCEPTION 'Run context scope mismatch' USING ERRCODE = '23514'; END IF;
            IF NEW.manifest_sha256 <> encode(sha256(convert_to(NEW.manifest::text,'UTF8')),'hex') THEN RAISE EXCEPTION 'Manifest digest mismatch' USING ERRCODE = '23514'; END IF;
            FOREACH field IN ARRAY ARRAY['documents','procedures','prompts'] LOOP
                IF jsonb_typeof(NEW.manifest->field) IS DISTINCT FROM 'object' THEN RAISE EXCEPTION 'Manifest requires revision maps' USING ERRCODE = '23514'; END IF;
                target_table := CASE field WHEN 'documents' THEN 'app_document' WHEN 'procedures' THEN 'app_topicflow' ELSE 'agent_prompt' END;
                FOR entry IN SELECT * FROM jsonb_each_text(NEW.manifest->field) LOOP
                    EXECUTE format('SELECT to_jsonb(p) FROM public.%I p WHERE id::text = $1 AND version = 1',target_table) INTO anchor USING entry.key;
                    EXECUTE format('SELECT to_jsonb(p) FROM public.%I p WHERE id::text = $1 AND state = ''published''',target_table) INTO selected USING entry.value;
                    IF anchor IS NULL OR selected IS NULL THEN RAISE EXCEPTION 'Manifest references unknown/unpublished revisions' USING ERRCODE = '23514'; END IF;
                    IF field = 'documents' THEN
                        IF anchor->>'owner_kind' <> 'court' OR anchor->'owner_court_id' IS DISTINCT FROM selected->'owner_court_id'
                            OR anchor->'key' IS DISTINCT FROM selected->'key' OR selected->>'storage_state' <> 'available' OR selected->>'deleted_at' IS NOT NULL
                            OR NOT EXISTS (SELECT FROM public.app_corpus_document WHERE document_id::text = entry.key AND court_topic_id = scope_id AND enabled) THEN
                            RAISE EXCEPTION 'Manifest document scope/family mismatch' USING ERRCODE = '23514';
                        END IF;
                        SELECT max(version) INTO highest FROM public.app_document WHERE owner_court_id::text = anchor->>'owner_court_id'
                            AND key = anchor->>'key' AND state = 'published' AND storage_state = 'available' AND deleted_at IS NULL;
                    ELSIF field = 'procedures' THEN
                        IF anchor->>'court_topic_id' IS DISTINCT FROM scope_id::text OR anchor->'court_topic_id' IS DISTINCT FROM selected->'court_topic_id'
                            OR anchor->'slug' IS DISTINCT FROM selected->'slug' THEN RAISE EXCEPTION 'Manifest procedure scope/family mismatch' USING ERRCODE = '23514'; END IF;
                        SELECT max(version) INTO highest FROM public.app_topicflow WHERE court_topic_id = scope_id AND slug = anchor->>'slug' AND state = 'published';
                    ELSE
                        IF anchor->'key' IS DISTINCT FROM selected->'key' THEN RAISE EXCEPTION 'Manifest fragment family mismatch' USING ERRCODE = '23514'; END IF;
                        SELECT max(version) INTO highest FROM public.agent_prompt WHERE key = anchor->>'key' AND state = 'published';
                    END IF;
                    IF (selected->>'version')::integer IS DISTINCT FROM highest THEN
                        RAISE EXCEPTION 'Select the latest published revision when preparing a run' USING ERRCODE = '23514';
                    END IF;
                END LOOP;
            END LOOP;
        END IF;
    ELSE NULL;
    END CASE;
    RETURN NEW;
END
$$;

DO $triggers$
DECLARE t record;
BEGIN
    FOR t IN SELECT tablename FROM pg_tables WHERE schemaname = 'public'
        AND tablename IN ('app_useridentity', 'app_topic', 'app_court', 'app_court_topic', 'app_matter', 'app_topicflow', 'app_topicflowinterviewpage', 'app_topicflowinterviewvariable', 'app_topicflowdeadline', 'app_variable', 'app_variableanswer', 'app_chatthread', 'app_chatmessage', 'app_phase_document', 'agent_prompt', 'app_document', 'app_corpus_document', 'app_matter_document', 'app_document_chunk', 'app_fact_evidence', 'app_matter_procedure', 'app_phase_progress', 'agent_memory', 'agent_memory_source', 'app_message_attachment', 'agent_run', 'agent_run_step')
    LOOP
        EXECUTE format('CREATE TRIGGER agent_01_immutable BEFORE UPDATE ON public.%I FOR EACH ROW EXECUTE FUNCTION public.agent_guard_immutable()', t.tablename);
        EXECUTE format('CREATE TRIGGER agent_02_validate BEFORE INSERT OR UPDATE ON public.%I FOR EACH ROW EXECUTE FUNCTION public.agent_validate_record()', t.tablename);
        EXECUTE format('CREATE TRIGGER agent_03_timestamp BEFORE UPDATE ON public.%I FOR EACH ROW EXECUTE FUNCTION public.agent_touch_updated_at()', t.tablename);
    END LOOP;
END
$triggers$;

CREATE CONSTRAINT TRIGGER agent_document_index_complete AFTER INSERT OR UPDATE ON public.app_document
    DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION public.agent_validate_record('index');
CREATE CONSTRAINT TRIGGER agent_chunk_index_complete AFTER INSERT OR UPDATE OR DELETE ON public.app_document_chunk
    DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION public.agent_validate_record('index');


-- Local development defaults: optional recall is on, always within one user.
-- The host supplies authenticated user/run IDs and host policy; they are not model arguments.
-- These row-returning routines are PostgreSQL functions, not CALL procedures.
-- https://www.postgresql.org/docs/17/sql-createfunction.html#SQL-CREATEFUNCTION-SECURITY

CREATE FUNCTION public.agent_scope_allowed(
    policies jsonb, court uuid, topic uuid, matter uuid, global_fact boolean DEFAULT false
) RETURNS boolean LANGUAGE plpgsql IMMUTABLE
SET search_path = pg_catalog, public, pg_temp AS $$
DECLARE policy jsonb; dimension text; candidate text;
BEGIN
    IF jsonb_typeof(policies) IS DISTINCT FROM 'array' THEN RETURN false; END IF;
    FOR policy IN SELECT value FROM jsonb_array_elements(policies) LOOP
        IF jsonb_typeof(policy) IS DISTINCT FROM 'object' THEN RETURN false; END IF;
        IF policy ? 'enabled' AND policy->'enabled' IS DISTINCT FROM 'true'::jsonb THEN RETURN false; END IF;
        IF global_fact THEN
            IF policy ? 'include_user_facts' AND policy->'include_user_facts' IS DISTINCT FROM 'true'::jsonb THEN RETURN false; END IF;
        ELSE
            FOREACH dimension IN ARRAY ARRAY['court_ids', 'topic_ids', 'matter_ids'] LOOP
                IF policy ? dimension THEN
                    candidate := CASE dimension WHEN 'court_ids' THEN court::text WHEN 'topic_ids' THEN topic::text ELSE matter::text END;
                    IF jsonb_typeof(policy->dimension) IS DISTINCT FROM 'array'
                        OR candidate IS NULL OR NOT (policy->dimension ? candidate) THEN RETURN false; END IF;
                END IF;
            END LOOP;
        END IF;
    END LOOP;
    RETURN true;
END
$$;

CREATE FUNCTION public.agent_lookup_context(p_user_id bigint, p_run_id uuid, p_host_policy jsonb)
RETURNS jsonb LANGUAGE sql STABLE SET search_path = pg_catalog, public, pg_temp AS $$
    SELECT jsonb_build_object('court_topic_id', r.context_court_topic_id, 'court_id', ct.court_id,
        'topic_id', ct.topic_id, 'matter_id', c.matter_id, 'manifest', r.manifest,
        'policies', jsonb_build_array(u.recall_limits || jsonb_build_object('enabled', coalesce(u.recall_enabled, true)),
            r.recall_policy_snapshot, coalesce(p_host_policy, '{"enabled":false}'::jsonb)))
    FROM public.agent_run r JOIN public.app_chatthread c ON c.id = r.thread_id
    JOIN public.app_useridentity u ON u.id = c.identity_id
    JOIN public.app_court_topic ct ON ct.id = r.context_court_topic_id
    JOIN public.app_court court ON court.id = ct.court_id
    JOIN public.app_topic topic ON topic.id = ct.topic_id
    JOIN public.app_matter m ON m.id = c.matter_id AND m.identity_id = u.id
    WHERE r.id = p_run_id AND u.id = p_user_id AND u.deleted_at IS NULL
        AND c.deleted_at IS NULL AND m.deleted_at IS NULL AND ct.enabled AND court.enabled AND topic.enabled
$$;

CREATE FUNCTION public.agent_source_allowed(
    p_user_id bigint, p_kind text, p_id uuid, p_policies jsonb, p_depth integer DEFAULT 0
) RETURNS boolean LANGUAGE plpgsql STABLE
SET search_path = pg_catalog, public, pg_temp AS $$
DECLARE record_data record; source record; scope_court uuid; scope_topic uuid; scope_matter uuid;
    has_source boolean := false; basis_policies jsonb;
BEGIN
    IF p_depth > 12 OR NOT EXISTS (SELECT FROM public.app_useridentity WHERE id = p_user_id AND deleted_at IS NULL) THEN RETURN false; END IF;
    CASE p_kind
    WHEN 'document' THEN
        SELECT * INTO record_data FROM public.app_document WHERE id = p_id AND storage_state = 'available' AND deleted_at IS NULL;
        IF NOT FOUND THEN RETURN false; END IF;
        IF record_data.owner_kind = 'court' THEN RETURN record_data.state = 'published'; END IF;
        IF record_data.owner_user_id IS DISTINCT FROM p_user_id OR record_data.state <> 'private' THEN RETURN false; END IF;
        IF public.agent_scope_allowed(p_policies, NULL, NULL, NULL) THEN RETURN true; END IF;
        RETURN EXISTS (SELECT FROM public.app_matter_document md JOIN public.app_document base ON base.id = md.document_id
            JOIN public.app_matter m ON m.id = md.matter_id
            JOIN public.app_court_topic ct ON ct.id = m.court_topic_id WHERE base.key = record_data.key AND base.owner_user_id = p_user_id
            AND m.identity_id = p_user_id AND m.deleted_at IS NULL
            AND public.agent_scope_allowed(p_policies, ct.court_id, ct.topic_id, m.id));
    WHEN 'item', 'step' THEN
        IF p_kind = 'item' THEN
            SELECT c.* INTO record_data FROM public.app_chatmessage i JOIN public.app_chatthread c ON c.id = i.thread_id
                WHERE i.id = p_id AND i.redacted_at IS NULL AND i.context_state = 'accepted'
                    AND (NOT i.hidden AND NOT i.meta) AND i.item_kind = 'message' AND i.origin IN ('user', 'model');
        ELSE
            SELECT c.* INTO record_data FROM public.agent_run_step s JOIN public.agent_run r ON r.id = s.run_id
                JOIN public.app_chatthread c ON c.id = r.thread_id
                WHERE s.id = p_id AND s.redacted_at IS NULL AND s.state = 'completed';
        END IF;
        IF NOT FOUND OR record_data.identity_id IS DISTINCT FROM p_user_id OR record_data.deleted_at IS NOT NULL THEN RETURN false; END IF;
        IF record_data.matter_id IS NOT NULL AND NOT EXISTS (SELECT FROM public.app_matter WHERE id = record_data.matter_id AND deleted_at IS NULL) THEN RETURN false; END IF;
        RETURN public.agent_scope_allowed(p_policies, record_data.court_id, record_data.topic_id, record_data.matter_id);
    WHEN 'fact' THEN
        SELECT a.*, (CASE WHEN d.is_global THEN 'user' ELSE 'matter' END) AS scope INTO record_data FROM public.app_variableanswer a JOIN public.app_variable d ON d.id = a.variable_id
            WHERE a.id = p_id AND a.identity_id = p_user_id AND a.state = 'active' AND a.invalidated_at IS NULL
                AND a.confirmation_state <> 'rejected' AND d.in_schema;
        IF NOT FOUND THEN RETURN false; END IF;
        IF record_data.scope = 'matter' THEN
            SELECT ct.court_id, ct.topic_id, m.id INTO scope_court, scope_topic, scope_matter
                FROM public.app_matter m JOIN public.app_court_topic ct ON ct.id = m.court_topic_id
                WHERE m.id = record_data.matter_id AND m.identity_id = p_user_id AND m.deleted_at IS NULL;
            IF NOT FOUND THEN RETURN false; END IF;
        END IF;
        IF NOT public.agent_scope_allowed(p_policies, scope_court, scope_topic, scope_matter, record_data.scope = 'user') THEN RETURN false; END IF;
        -- Global personal facts remain reusable when contextual history is narrowed.
        -- Availability/ownership of their original evidence is still checked.
        basis_policies := CASE WHEN record_data.scope = 'user' THEN '[{}]'::jsonb ELSE p_policies END;
        IF record_data.confirmation_state = 'confirmed' AND NOT EXISTS (
            SELECT FROM public.app_fact_evidence e LEFT JOIN public.app_chatmessage i ON i.id = e.message_id
            WHERE e.answer_id = p_id AND e.role = 'confirmation' AND (e.submitted_by_id IS NOT NULL OR (i.origin = 'user' AND public.agent_source_allowed(p_user_id, 'item', i.id, basis_policies, p_depth + 1)))
        ) THEN RETURN false; END IF;
        FOR source IN SELECT * FROM public.app_fact_evidence WHERE answer_id = p_id AND role = 'basis' LOOP
            IF source.submitted_by_id IS NOT NULL OR public.agent_source_allowed(p_user_id,
                CASE WHEN source.message_id IS NOT NULL THEN 'item' WHEN source.document_id IS NOT NULL THEN 'document' ELSE 'step' END,
                coalesce(source.message_id, source.document_id, source.run_step_id), basis_policies, p_depth + 1) THEN has_source := true; END IF;
        END LOOP;
        RETURN has_source;
    WHEN 'memory' THEN
        SELECT * INTO record_data FROM public.agent_memory WHERE id = p_id AND identity_id = p_user_id
            AND state = 'active' AND invalidated_at IS NULL AND btrim(body) <> '';
        IF NOT FOUND OR NOT public.agent_source_allowed(p_user_id, 'step', record_data.generated_step_id, '[{}]', p_depth + 1) THEN RETURN false; END IF;
        IF record_data.matter_id IS NOT NULL THEN
            SELECT ct.court_id, ct.topic_id, m.id INTO scope_court, scope_topic, scope_matter
                FROM public.app_matter m JOIN public.app_court_topic ct ON ct.id = m.court_topic_id
                WHERE m.id = record_data.matter_id AND m.identity_id = p_user_id AND m.deleted_at IS NULL;
            IF NOT FOUND OR NOT public.agent_scope_allowed(p_policies, scope_court, scope_topic, scope_matter) THEN RETURN false; END IF;
        END IF;
        -- Every source must pass; a mixed-matter summary cannot leak excluded history.
        FOR source IN SELECT * FROM public.agent_memory_source WHERE memory_id = p_id LOOP
            has_source := true;
            IF NOT public.agent_source_allowed(p_user_id,
                CASE WHEN source.message_id IS NOT NULL THEN 'item' WHEN source.document_id IS NOT NULL THEN 'document' ELSE 'fact' END,
                coalesce(source.message_id, source.document_id, source.answer_id), p_policies, p_depth + 1) THEN RETURN false; END IF;
        END LOOP;
        RETURN has_source AND public.agent_scope_allowed(
            (SELECT jsonb_agg(jsonb_build_object('enabled', coalesce(p->'enabled', 'true'::jsonb))) FROM jsonb_array_elements(p_policies) p), NULL, NULL, NULL);
    WHEN 'progress' THEN
        SELECT m.id, ct.court_id, ct.topic_id, pp.last_run_step_id INTO record_data
            FROM public.app_phase_progress pp JOIN public.app_matter_procedure mp ON mp.id = pp.matter_procedure_id
            JOIN public.app_matter m ON m.id = mp.matter_id JOIN public.app_court_topic ct ON ct.id = m.court_topic_id
            WHERE pp.id = p_id AND m.identity_id = p_user_id AND m.deleted_at IS NULL;
        IF NOT FOUND THEN RETURN false; END IF;
        RETURN public.agent_scope_allowed(p_policies, record_data.court_id, record_data.topic_id, record_data.id)
            AND (record_data.last_run_step_id IS NULL OR public.agent_source_allowed(p_user_id, 'step', record_data.last_run_step_id, p_policies, p_depth + 1));
    ELSE RETURN false;
    END CASE;
END
$$;

CREATE FUNCTION public.agent_private_candidates(
    p_user_id bigint, p_policies jsonb, p_categories text[], p_source_id uuid DEFAULT NULL
) RETURNS TABLE(category text, source_id uuid, revision_id uuid, title text, body text,
    court_id uuid, topic_id uuid, matter_id uuid, labels jsonb)
LANGUAGE sql STABLE SET search_path = pg_catalog, public, pg_temp AS $$
    SELECT 'user_documents', d.id, d.id, d.title, coalesce(ch.body, d.title), NULL::uuid, NULL::uuid, NULL::uuid,
        jsonb_build_object('authority', 'private', 'chunk_id', ch.id, 'locator', ch.locator,
            'index_revision', d.index_revision, 'ordinal', ch.ordinal, 'content_available', ch.id IS NOT NULL,
            'observed_at', d.created_at, 'associations', coalesce((
                SELECT jsonb_agg(jsonb_build_object('matter_id', m.id, 'court_id', ct.court_id, 'topic_id', ct.topic_id))
                FROM public.app_matter_document md JOIN public.app_document base ON base.id = md.document_id
                JOIN public.app_matter m ON m.id = md.matter_id JOIN public.app_court_topic ct ON ct.id = m.court_topic_id
                WHERE base.key = d.key AND base.owner_user_id = p_user_id AND m.identity_id = p_user_id AND m.deleted_at IS NULL
                    AND public.agent_scope_allowed(p_policies, ct.court_id, ct.topic_id, m.id)), '[]'::jsonb))
    FROM public.app_document d
    LEFT JOIN public.app_document_chunk ch ON ch.document_id = d.id AND d.index_state = 'ready' AND d.index_invalidated_at IS NULL
    WHERE 'user_documents' = ANY(p_categories) AND d.owner_user_id = p_user_id
        AND (CASE WHEN p_source_id IS NULL THEN NOT EXISTS (
            SELECT FROM public.app_document newer WHERE newer.owner_user_id = p_user_id AND newer.key = d.key AND newer.version > d.version
                AND newer.state = 'private' AND newer.storage_state = 'available' AND newer.deleted_at IS NULL
        ) ELSE d.id = p_source_id END)
        AND public.agent_source_allowed(p_user_id, 'document', d.id, p_policies)
    UNION ALL
    SELECT CASE WHEN (CASE WHEN d.is_global THEN 'user' ELSE 'matter' END) = 'user' THEN 'user_facts' ELSE 'matter_facts' END,
        a.id, d.id, d.label, d.label || ': ' || a.value::text, ct.court_id, ct.topic_id, a.matter_id,
        jsonb_build_object('authority', 'private', 'fact_key', d.name, 'value', a.value,
            'evidence_kind', a.evidence_kind, 'confirmation_state', a.confirmation_state,
            'observed_at', a.observed_at, 'effective_from', a.effective_from, 'effective_to', a.effective_to)
    FROM public.app_variableanswer a JOIN public.app_variable d ON d.id = a.variable_id
    LEFT JOIN public.app_matter m ON m.id = a.matter_id LEFT JOIN public.app_court_topic ct ON ct.id = m.court_topic_id
    WHERE (CASE WHEN (CASE WHEN d.is_global THEN 'user' ELSE 'matter' END) = 'user' THEN 'user_facts' ELSE 'matter_facts' END) = ANY(p_categories)
        AND a.identity_id = p_user_id AND (p_source_id IS NULL OR a.id = p_source_id)
        AND public.agent_source_allowed(p_user_id, 'fact', a.id, p_policies)
    UNION ALL
    SELECT 'conversation_history', i.id, NULL::uuid, c.description, i.search_text, c.court_id, c.topic_id, c.matter_id,
        jsonb_build_object('authority', 'private_history', 'thread_id', c.id, 'origin', i.origin, 'observed_at', i.created_at)
    FROM public.app_chatmessage i JOIN public.app_chatthread c ON c.id = i.thread_id
    WHERE 'conversation_history' = ANY(p_categories) AND c.identity_id = p_user_id
        AND (p_source_id IS NULL OR i.id = p_source_id) AND i.search_text IS NOT NULL
        AND public.agent_source_allowed(p_user_id, 'item', i.id, p_policies)
    UNION ALL
    SELECT 'memory', mem.id, NULL::uuid, 'Conversation memory', mem.body, ct.court_id, ct.topic_id, mem.matter_id,
        jsonb_build_object('authority', 'private_summary', 'kind', mem.kind, 'observed_at', mem.created_at,
            'source_ids', (SELECT jsonb_agg(coalesce(s.message_id, s.answer_id, s.document_id)) FROM public.agent_memory_source s WHERE s.memory_id = mem.id))
    FROM public.agent_memory mem LEFT JOIN public.app_matter m ON m.id = mem.matter_id
    LEFT JOIN public.app_court_topic ct ON ct.id = m.court_topic_id
    WHERE 'memory' = ANY(p_categories) AND mem.identity_id = p_user_id AND (p_source_id IS NULL OR mem.id = p_source_id)
        AND public.agent_source_allowed(p_user_id, 'memory', mem.id, p_policies)
    UNION ALL
    SELECT 'procedure_progress', pp.id, ph.flow_id, ph.title, ph.title || ': ' || pp.state,
        ct.court_id, ct.topic_id, m.id, jsonb_build_object('authority', 'private_progress', 'state', pp.state, 'page_id', ph.id, 'observed_at', pp.updated_at)
    FROM public.app_phase_progress pp JOIN public.app_topicflowinterviewpage ph ON ph.id = pp.page_id
    JOIN public.app_matter_procedure mp ON mp.id = pp.matter_procedure_id JOIN public.app_matter m ON m.id = mp.matter_id
    JOIN public.app_court_topic ct ON ct.id = m.court_topic_id
    WHERE 'procedure_progress' = ANY(p_categories) AND m.identity_id = p_user_id AND (p_source_id IS NULL OR pp.id = p_source_id)
        AND public.agent_source_allowed(p_user_id, 'progress', pp.id, p_policies)
$$;

CREATE FUNCTION public.agent_search_private(
    p_user_id bigint, p_run_id uuid, p_host_policy jsonb, p_query text,
    p_categories text[] DEFAULT ARRAY['user_documents','user_facts','matter_facts','procedure_progress','conversation_history','memory'],
    p_filters jsonb DEFAULT '{}', p_limit integer DEFAULT 10
) RETURNS SETOF jsonb LANGUAGE plpgsql STABLE SECURITY DEFINER
SET search_path = pg_catalog, public, pg_temp AS $$
DECLARE ctx jsonb; query tsquery;
BEGIN
    IF p_categories IS NULL OR NOT p_categories <@ ARRAY['user_documents','user_facts','matter_facts','procedure_progress','conversation_history','memory']::text[]
        OR jsonb_typeof(p_filters) IS DISTINCT FROM 'object' OR p_query IS NULL OR length(p_query) > 512
        OR p_limit IS NULL OR p_limit < 1 OR p_limit > 20 THEN RAISE EXCEPTION 'Invalid private search arguments' USING ERRCODE = '22023'; END IF;
    ctx := public.agent_lookup_context(p_user_id, p_run_id, p_host_policy);
    IF ctx IS NULL THEN RETURN; END IF;
    query := websearch_to_tsquery('english', p_query);
    RETURN QUERY WITH candidates AS (
        SELECT c.*, ts_rank_cd(to_tsvector('english', c.body), query) AS score
        FROM public.agent_private_candidates(p_user_id, ctx->'policies' || jsonb_build_array(p_filters), p_categories) c
        WHERE p_query = '' OR to_tsvector('english', c.body) @@ query
    ), best AS (SELECT DISTINCT ON (category, source_id) * FROM candidates ORDER BY category, source_id, score DESC, labels->>'ordinal', labels->>'chunk_id')
    SELECT jsonb_build_object('category', b.category, 'source_id', b.source_id, 'revision_id', b.revision_id,
        'title', left(b.title, 200), 'snippet', left(b.body, 1000), 'court_id', b.court_id, 'topic_id', b.topic_id,
        'matter_id', b.matter_id, 'labels', CASE WHEN octet_length(b.labels::text) <= 4096 THEN b.labels ELSE
            jsonb_build_object('authority', b.labels->'authority', 'evidence_kind', b.labels->'evidence_kind',
                'confirmation_state', b.labels->'confirmation_state', 'metadata_truncated', true) END,
        'score', b.score, 'scoring_method', 'postgres_english_full_text')
    FROM best b ORDER BY b.score DESC, b.source_id LIMIT p_limit;
END
$$;

CREATE FUNCTION public.agent_get_private_source(
    p_user_id bigint, p_run_id uuid, p_host_policy jsonb, p_category text, p_source_id uuid, p_filters jsonb DEFAULT '{}'
) RETURNS SETOF jsonb LANGUAGE plpgsql STABLE SECURITY DEFINER
SET search_path = pg_catalog, public, pg_temp AS $$
DECLARE ctx jsonb;
BEGIN
    IF p_category IS NULL OR p_category <> ALL(ARRAY['user_documents','user_facts','matter_facts','procedure_progress','conversation_history','memory'])
        OR p_source_id IS NULL OR jsonb_typeof(p_filters) IS DISTINCT FROM 'object' THEN
        RAISE EXCEPTION 'Invalid private source arguments' USING ERRCODE = '22023';
    END IF;
    ctx := public.agent_lookup_context(p_user_id, p_run_id, p_host_policy);
    IF ctx IS NULL THEN RETURN; END IF;
    RETURN QUERY SELECT jsonb_build_object('category', c.category, 'source_id', c.source_id, 'revision_id', c.revision_id,
        'title', left(c.title, 200), 'snippet', left(c.body, 1000), 'court_id', c.court_id, 'topic_id', c.topic_id,
        'matter_id', c.matter_id, 'labels', CASE WHEN octet_length(c.labels::text) <= 4096 THEN c.labels ELSE
            jsonb_build_object('authority', c.labels->'authority', 'evidence_kind', c.labels->'evidence_kind',
                'confirmation_state', c.labels->'confirmation_state', 'metadata_truncated', true) END)
    FROM public.agent_private_candidates(p_user_id, ctx->'policies' || jsonb_build_array(p_filters), ARRAY[p_category], p_source_id) c
    ORDER BY c.labels->>'ordinal', c.labels->>'chunk_id' LIMIT 1;
END
$$;

CREATE FUNCTION public.agent_corpus_candidates(p_user_id bigint, p_run_id uuid)
RETURNS TABLE(source_id uuid, revision_id uuid, title text, body text, court_id uuid, topic_id uuid, labels jsonb)
LANGUAGE sql STABLE SET search_path = pg_catalog, public, pg_temp AS $$
    WITH context AS (SELECT public.agent_lookup_context(p_user_id, p_run_id, '{}') AS ctx)
    SELECT doc.id, doc.id, doc.title, coalesce(ch.body, doc.title), (ctx->>'court_id')::uuid, (ctx->>'topic_id')::uuid,
        jsonb_build_object('authority', 'published_court_source', 'chunk_id', ch.id, 'index_revision', doc.index_revision,
            'locator', ch.locator, 'content_available', ch.id IS NOT NULL, 'published_at', doc.published_at)
    FROM context JOIN public.app_corpus_document cd ON cd.court_topic_id = (ctx->>'court_topic_id')::uuid AND cd.enabled
    JOIN public.app_document base ON base.id = cd.document_id AND base.version = 1
    JOIN public.app_document doc ON doc.key = base.key AND doc.owner_court_id = base.owner_court_id
        AND doc.id::text = ctx->'manifest'->'documents'->>base.id::text
        AND doc.state = 'published' AND doc.storage_state = 'available' AND doc.deleted_at IS NULL
    LEFT JOIN public.app_document_chunk ch ON ch.document_id = doc.id AND doc.index_state = 'ready' AND doc.index_invalidated_at IS NULL
    UNION ALL
    SELECT p.id, p.id, p.name, p.guidance, (ctx->>'court_id')::uuid, (ctx->>'topic_id')::uuid,
        jsonb_build_object('authority', 'published_procedure', 'flow_id', p.id, 'published_at', p.published_at)
    FROM context JOIN public.app_topicflow base ON base.court_topic_id = (ctx->>'court_topic_id')::uuid AND base.version = 1
    JOIN public.app_topicflow p ON p.court_topic_id = base.court_topic_id AND p.slug = base.slug
        AND p.id::text = ctx->'manifest'->'procedures'->>base.id::text AND p.state = 'published'
    UNION ALL
    SELECT ph.id, p.id, ph.title, ph.instructions, (ctx->>'court_id')::uuid, (ctx->>'topic_id')::uuid,
        jsonb_build_object('authority', 'published_phase', 'flow_id', p.id, 'phase_key', ph.key)
    FROM context JOIN public.app_topicflow base ON base.court_topic_id = (ctx->>'court_topic_id')::uuid AND base.version = 1
    JOIN public.app_topicflow p ON p.court_topic_id = base.court_topic_id AND p.slug = base.slug
        AND p.id::text = ctx->'manifest'->'procedures'->>base.id::text AND p.state = 'published'
    JOIN public.app_topicflowinterviewpage ph ON ph.flow_id = p.id
$$;

CREATE FUNCTION public.agent_search_corpus(p_user_id bigint, p_run_id uuid, p_query text, p_limit integer DEFAULT 10)
RETURNS SETOF jsonb LANGUAGE plpgsql STABLE SECURITY DEFINER
SET search_path = pg_catalog, public, pg_temp AS $$
DECLARE query tsquery;
BEGIN
    IF p_query IS NULL OR length(p_query) > 512 OR p_limit IS NULL OR p_limit < 1 OR p_limit > 20 THEN
        RAISE EXCEPTION 'Invalid corpus search arguments' USING ERRCODE = '22023';
    END IF;
    query := websearch_to_tsquery('english', p_query);
    RETURN QUERY WITH candidates AS (
        SELECT c.*, ts_rank_cd(to_tsvector('english', c.body), query) AS score
        FROM public.agent_corpus_candidates(p_user_id, p_run_id) c WHERE p_query = '' OR to_tsvector('english', c.body) @@ query
    ), best AS (SELECT DISTINCT ON (source_id) * FROM candidates ORDER BY source_id, score DESC, labels->>'chunk_id')
    SELECT jsonb_build_object('category', 'court_corpus', 'source_id', b.source_id, 'revision_id', b.revision_id,
        'title', left(b.title, 200), 'snippet', left(b.body, 1000), 'court_id', b.court_id, 'topic_id', b.topic_id,
        'labels', CASE WHEN octet_length(b.labels::text) <= 4096 THEN b.labels ELSE
            jsonb_build_object('authority', b.labels->'authority', 'metadata_truncated', true) END,
        'score', b.score, 'scoring_method', 'postgres_english_full_text')
    FROM best b ORDER BY b.score DESC, b.source_id LIMIT p_limit;
END
$$;

CREATE FUNCTION public.agent_get_corpus_source(p_user_id bigint, p_run_id uuid, p_source_id uuid)
RETURNS SETOF jsonb LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = pg_catalog, public, pg_temp AS $$
    SELECT jsonb_build_object('category', 'court_corpus', 'source_id', c.source_id, 'revision_id', c.revision_id,
        'title', left(c.title, 200), 'snippet', left(c.body, 1000), 'court_id', c.court_id, 'topic_id', c.topic_id,
        'labels', CASE WHEN octet_length(c.labels::text) <= 4096 THEN c.labels ELSE
            jsonb_build_object('authority', c.labels->'authority', 'metadata_truncated', true) END)
    FROM public.agent_corpus_candidates(p_user_id, p_run_id) c WHERE c.source_id = p_source_id
    ORDER BY c.labels->>'chunk_id' LIMIT 1
$$;



ALTER TABLE public.app_promptartifact ADD CONSTRAINT prompt_artifact_digest CHECK (canonical_payload = '' OR content_hash = encode(sha256(convert_to(canonical_payload, 'UTF8')), 'hex'));
CREATE FUNCTION public.app_message_sequence() RETURNS trigger LANGUAGE plpgsql SET search_path = pg_catalog, public, pg_temp AS $$
BEGIN
    IF NEW.sequence IS NULL THEN
        UPDATE public.app_chatthread SET next_sequence = next_sequence + 1 WHERE id = NEW.thread_id RETURNING next_sequence - 1 INTO NEW.sequence;
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER app_message_sequence BEFORE INSERT ON public.app_chatmessage FOR EACH ROW EXECUTE FUNCTION public.app_message_sequence();



CREATE FUNCTION public.app_guard_published_revision() RETURNS trigger
LANGUAGE plpgsql SET search_path = pg_catalog, public, pg_temp AS $$
DECLARE row_data jsonb := CASE WHEN TG_OP = 'DELETE' THEN to_jsonb(OLD) ELSE to_jsonb(NEW) END;
    previous_data jsonb := to_jsonb(OLD); parent_state text; row_version jsonb; flow uuid;
BEGIN
    IF TG_TABLE_NAME IN ('app_topicflow', 'app_document', 'agent_prompt') THEN
        parent_state := OLD.state;
        IF parent_state IN ('published', 'private', 'withdrawn') THEN
            RAISE EXCEPTION 'Published revisions cannot be deleted' USING ERRCODE = '23514';
        END IF;
    ELSE
        FOREACH row_version IN ARRAY ARRAY[row_data, previous_data] LOOP
            flow := (row_version->>'flow_id')::uuid;
            IF flow IS NULL THEN
                SELECT flow_id INTO flow FROM public.app_topicflowinterviewpage WHERE id = (row_version->>'page_id')::uuid;
            END IF;
            SELECT state INTO parent_state FROM public.app_topicflow WHERE id = flow;
            IF parent_state IN ('published', 'withdrawn') THEN
                RAISE EXCEPTION 'Published flow composition is immutable' USING ERRCODE = '23514';
            END IF;
        END LOOP;
    END IF;
    RETURN CASE WHEN TG_OP = 'DELETE' THEN OLD ELSE NEW END;
END $$;
CREATE TRIGGER app_revision_delete BEFORE DELETE ON public.app_topicflow FOR EACH ROW EXECUTE FUNCTION public.app_guard_published_revision();
CREATE TRIGGER app_revision_delete BEFORE DELETE ON public.app_document FOR EACH ROW EXECUTE FUNCTION public.app_guard_published_revision();
CREATE TRIGGER app_revision_delete BEFORE DELETE ON public.agent_prompt FOR EACH ROW EXECUTE FUNCTION public.app_guard_published_revision();
CREATE TRIGGER app_revision_composition BEFORE INSERT OR UPDATE OR DELETE ON public.app_topicflowsection FOR EACH ROW EXECUTE FUNCTION public.app_guard_published_revision();
CREATE TRIGGER app_revision_composition BEFORE INSERT OR UPDATE OR DELETE ON public.app_topicflowinterviewpage FOR EACH ROW EXECUTE FUNCTION public.app_guard_published_revision();
CREATE TRIGGER app_revision_composition BEFORE INSERT OR UPDATE OR DELETE ON public.app_topicflowinterviewvariable FOR EACH ROW EXECUTE FUNCTION public.app_guard_published_revision();
CREATE TRIGGER app_revision_composition BEFORE INSERT OR UPDATE OR DELETE ON public.app_topicflowformcondition FOR EACH ROW EXECUTE FUNCTION public.app_guard_published_revision();
CREATE TRIGGER app_revision_composition BEFORE INSERT OR UPDATE OR DELETE ON public.app_topicflowlink FOR EACH ROW EXECUTE FUNCTION public.app_guard_published_revision();
CREATE TRIGGER app_revision_composition BEFORE INSERT OR UPDATE OR DELETE ON public.app_topicflowdeadline FOR EACH ROW EXECUTE FUNCTION public.app_guard_published_revision();
CREATE TRIGGER app_revision_composition BEFORE INSERT OR UPDATE OR DELETE ON public.app_phase_document FOR EACH ROW EXECUTE FUNCTION public.app_guard_published_revision();

DO $grants$
DECLARE t text; f record; role_name text;
BEGIN
    FOREACH role_name IN ARRAY ARRAY['agent_dev_crud', 'agent_dev_reader', 'agent_dev_lookup'] LOOP
        IF EXISTS (SELECT FROM pg_roles WHERE rolname = role_name) THEN
            IF EXISTS (SELECT FROM pg_roles WHERE rolname = role_name AND (rolsuper OR rolcreatedb OR rolcreaterole OR rolreplication OR rolbypassrls OR rolcanlogin)) THEN
                RAISE EXCEPTION 'Agent permission groups must be unprivileged NOLOGIN roles';
            END IF;
            EXECUTE format('GRANT USAGE ON SCHEMA public TO %I', role_name);
        END IF;
    END LOOP;
    FOREACH t IN ARRAY ARRAY['app_useridentity', 'app_topic', 'app_court', 'app_court_topic', 'app_matter', 'app_topicflow', 'app_topicflowinterviewpage', 'app_topicflowinterviewvariable', 'app_topicflowdeadline', 'app_variable', 'app_variableanswer', 'app_chatthread', 'app_chatmessage', 'app_phase_document', 'agent_prompt', 'app_document', 'app_corpus_document', 'app_matter_document', 'app_document_chunk', 'app_fact_evidence', 'app_matter_procedure', 'app_phase_progress', 'agent_memory', 'agent_memory_source', 'app_message_attachment', 'agent_run', 'agent_run_step', 'app_promptartifact', 'app_import_audit'] LOOP
        EXECUTE format('REVOKE ALL ON public.%I FROM PUBLIC', t);
        IF EXISTS (SELECT FROM pg_roles WHERE rolname = 'agent_dev_lookup') THEN
            EXECUTE format('REVOKE ALL ON public.%I FROM agent_dev_lookup', t);
        END IF;
        IF EXISTS (SELECT FROM pg_roles WHERE rolname = 'agent_dev_crud') THEN
            EXECUTE format('GRANT SELECT, INSERT, UPDATE, DELETE ON public.%I TO agent_dev_crud', t);
        END IF;
        IF EXISTS (SELECT FROM pg_roles WHERE rolname = 'agent_dev_reader') THEN
            EXECUTE format('GRANT SELECT ON public.%I TO agent_dev_reader', t);
        END IF;
    END LOOP;
    FOR f IN SELECT oid::regprocedure AS signature, proname FROM pg_proc WHERE pronamespace = 'public'::regnamespace AND (proname LIKE 'agent!_%' ESCAPE '!' OR proname IN ('app_message_sequence', 'app_guard_published_revision')) LOOP
        EXECUTE format('REVOKE ALL ON FUNCTION %s FROM PUBLIC', f.signature);
        IF EXISTS (SELECT FROM pg_roles WHERE rolname = 'agent_dev_lookup') THEN
            EXECUTE format('REVOKE ALL ON FUNCTION %s FROM agent_dev_lookup', f.signature);
        END IF;
        IF EXISTS (SELECT FROM pg_roles WHERE rolname = 'agent_dev_crud') THEN
            EXECUTE format('GRANT EXECUTE ON FUNCTION %s TO agent_dev_crud', f.signature);
        END IF;
        IF EXISTS (SELECT FROM pg_roles WHERE rolname = 'agent_dev_reader') THEN
            EXECUTE format('GRANT EXECUTE ON FUNCTION %s TO agent_dev_reader', f.signature);
            IF f.proname IN ('agent_search_private','agent_get_private_source','agent_search_corpus','agent_get_corpus_source') THEN
                GRANT CREATE ON SCHEMA public TO agent_dev_reader;
                EXECUTE format('ALTER FUNCTION %s OWNER TO agent_dev_reader', f.signature);
                REVOKE CREATE ON SCHEMA public FROM agent_dev_reader;
                IF EXISTS (SELECT FROM pg_roles WHERE rolname = 'agent_dev_lookup') THEN
                    EXECUTE format('GRANT EXECUTE ON FUNCTION %s TO agent_dev_lookup', f.signature);
                END IF;
            END IF;
        END IF;
    END LOOP;
END $grants$;
""",
        reverse_sql=r"""
ALTER TABLE public.app_chatthread DROP CONSTRAINT shared_scope_fk_1;
ALTER TABLE public.app_chatthread DROP CONSTRAINT shared_scope_fk_2;
ALTER TABLE public.app_variableanswer DROP CONSTRAINT shared_scope_fk_3;
ALTER TABLE public.agent_memory DROP CONSTRAINT shared_scope_fk_4;
ALTER TABLE public.agent_memory DROP CONSTRAINT shared_scope_fk_5;
ALTER TABLE public.app_chatmessage DROP CONSTRAINT shared_scope_fk_6;
ALTER TABLE public.app_chatmessage DROP CONSTRAINT shared_scope_fk_7;
ALTER TABLE public.agent_run DROP CONSTRAINT shared_scope_fk_8;

DO $$ DECLARE f record; BEGIN FOR f IN SELECT oid::regprocedure AS signature FROM pg_proc WHERE pronamespace = 'public'::regnamespace AND proname IN ('agent_touch_updated_at', 'agent_guard_immutable', 'agent_validate_record', 'agent_scope_allowed', 'agent_lookup_context', 'agent_source_allowed', 'agent_private_candidates', 'agent_search_private', 'agent_get_private_source', 'agent_corpus_candidates', 'agent_search_corpus', 'agent_get_corpus_source', 'app_message_sequence', 'app_guard_published_revision') LOOP EXECUTE format('DROP FUNCTION %s CASCADE', f.signature); END LOOP; END $$;
DROP INDEX IF EXISTS public.agent_document_work;
DROP INDEX IF EXISTS public.agent_fact_active;
DROP INDEX IF EXISTS public.agent_run_state;
DROP INDEX IF EXISTS public.agent_conversation_recent;
DROP INDEX IF EXISTS public.agent_matter_recent;
DROP INDEX IF EXISTS public.agent_run_step_completed;
DROP INDEX IF EXISTS public.agent_run_active;
DROP INDEX IF EXISTS public.agent_conversation_item_fts;
DROP INDEX IF EXISTS public.agent_memory_fts;
DROP INDEX IF EXISTS public.agent_document_chunk_fts;
ALTER TABLE public.app_promptartifact DROP CONSTRAINT prompt_artifact_digest;
ALTER TABLE public.agent_run_step ALTER COLUMN "operation_key" DROP DEFAULT;
ALTER TABLE public.agent_run_step ALTER COLUMN "kind" DROP DEFAULT;
ALTER TABLE public.agent_run ALTER COLUMN "request_key" DROP DEFAULT;
ALTER TABLE public.agent_memory_source ALTER COLUMN "locator_sha256" DROP DEFAULT;
ALTER TABLE public.agent_memory ALTER COLUMN "body" DROP DEFAULT;
ALTER TABLE public.agent_memory ALTER COLUMN "kind" DROP DEFAULT;
ALTER TABLE public.agent_prompt ALTER COLUMN "body" DROP DEFAULT;
ALTER TABLE public.agent_prompt ALTER COLUMN "key" DROP DEFAULT;
ALTER TABLE public.app_useridentity ALTER COLUMN "recall_limits" DROP DEFAULT;
ALTER TABLE public.app_useridentity ALTER COLUMN "session_key" DROP DEFAULT;
ALTER TABLE public.app_useridentity ALTER COLUMN "updated_at" DROP DEFAULT;
ALTER TABLE public.app_useridentity ALTER COLUMN "created_at" DROP DEFAULT;
ALTER TABLE public.app_topicflowdeadline ALTER COLUMN "order" DROP DEFAULT;
ALTER TABLE public.app_topicflowdeadline ALTER COLUMN "offset_days" DROP DEFAULT;
ALTER TABLE public.app_topicflowdeadline ALTER COLUMN "description" DROP DEFAULT;
ALTER TABLE public.app_topicflowdeadline ALTER COLUMN "label" DROP DEFAULT;
ALTER TABLE public.app_topicflowdeadline ALTER COLUMN "id" DROP DEFAULT;
ALTER TABLE public.app_topicflowdeadline ALTER COLUMN "updated_at" DROP DEFAULT;
ALTER TABLE public.app_topicflowdeadline ALTER COLUMN "created_at" DROP DEFAULT;
ALTER TABLE public.app_topicflowinterviewvariable ALTER COLUMN "required" DROP DEFAULT;
ALTER TABLE public.app_topicflowinterviewvariable ALTER COLUMN "order" DROP DEFAULT;
ALTER TABLE public.app_topicflowinterviewvariable ALTER COLUMN "id" DROP DEFAULT;
ALTER TABLE public.app_topicflowinterviewvariable ALTER COLUMN "updated_at" DROP DEFAULT;
ALTER TABLE public.app_topicflowinterviewvariable ALTER COLUMN "created_at" DROP DEFAULT;
ALTER TABLE public.app_topicflowinterviewpage ALTER COLUMN "completion_criteria" DROP DEFAULT;
ALTER TABLE public.app_topicflowinterviewpage ALTER COLUMN "instructions" DROP DEFAULT;
ALTER TABLE public.app_topicflowinterviewpage ALTER COLUMN "key" DROP DEFAULT;
ALTER TABLE public.app_topicflowinterviewpage ALTER COLUMN "order" DROP DEFAULT;
ALTER TABLE public.app_topicflowinterviewpage ALTER COLUMN "description" DROP DEFAULT;
ALTER TABLE public.app_topicflowinterviewpage ALTER COLUMN "title" DROP DEFAULT;
ALTER TABLE public.app_topicflowinterviewpage ALTER COLUMN "id" DROP DEFAULT;
ALTER TABLE public.app_topicflowinterviewpage ALTER COLUMN "updated_at" DROP DEFAULT;
ALTER TABLE public.app_topicflowinterviewpage ALTER COLUMN "created_at" DROP DEFAULT;
ALTER TABLE public.app_variableanswer ALTER COLUMN "state" DROP DEFAULT;
ALTER TABLE public.app_variableanswer ALTER COLUMN "confirmation_state" DROP DEFAULT;
ALTER TABLE public.app_variableanswer ALTER COLUMN "evidence_kind" DROP DEFAULT;
ALTER TABLE public.app_variableanswer ALTER COLUMN "reviewed" DROP DEFAULT;
ALTER TABLE public.app_variableanswer ALTER COLUMN "id" DROP DEFAULT;
ALTER TABLE public.app_variableanswer ALTER COLUMN "updated_at" DROP DEFAULT;
ALTER TABLE public.app_variableanswer ALTER COLUMN "created_at" DROP DEFAULT;
ALTER TABLE public.app_variable ALTER COLUMN "value_schema" DROP DEFAULT;
ALTER TABLE public.app_variable ALTER COLUMN "version" DROP DEFAULT;
ALTER TABLE public.app_variable ALTER COLUMN "in_schema" DROP DEFAULT;
ALTER TABLE public.app_variable ALTER COLUMN "is_global" DROP DEFAULT;
ALTER TABLE public.app_variable ALTER COLUMN "choices" DROP DEFAULT;
ALTER TABLE public.app_variable ALTER COLUMN "data_type" DROP DEFAULT;
ALTER TABLE public.app_variable ALTER COLUMN "required" DROP DEFAULT;
ALTER TABLE public.app_variable ALTER COLUMN "help_text" DROP DEFAULT;
ALTER TABLE public.app_variable ALTER COLUMN "question" DROP DEFAULT;
ALTER TABLE public.app_variable ALTER COLUMN "label" DROP DEFAULT;
ALTER TABLE public.app_variable ALTER COLUMN "name" DROP DEFAULT;
ALTER TABLE public.app_variable ALTER COLUMN "id" DROP DEFAULT;
ALTER TABLE public.app_variable ALTER COLUMN "updated_at" DROP DEFAULT;
ALTER TABLE public.app_variable ALTER COLUMN "created_at" DROP DEFAULT;
ALTER TABLE public.app_topicflow ALTER COLUMN "state" DROP DEFAULT;
ALTER TABLE public.app_topicflow ALTER COLUMN "metadata" DROP DEFAULT;
ALTER TABLE public.app_topicflow ALTER COLUMN "guidance" DROP DEFAULT;
ALTER TABLE public.app_topicflow ALTER COLUMN "version" DROP DEFAULT;
ALTER TABLE public.app_topicflow ALTER COLUMN "order" DROP DEFAULT;
ALTER TABLE public.app_topicflow ALTER COLUMN "enabled" DROP DEFAULT;
ALTER TABLE public.app_topicflow ALTER COLUMN "name" DROP DEFAULT;
ALTER TABLE public.app_topicflow ALTER COLUMN "slug" DROP DEFAULT;
ALTER TABLE public.app_topicflow ALTER COLUMN "id" DROP DEFAULT;
ALTER TABLE public.app_topicflow ALTER COLUMN "updated_at" DROP DEFAULT;
ALTER TABLE public.app_topicflow ALTER COLUMN "created_at" DROP DEFAULT;
ALTER TABLE public.app_topic ALTER COLUMN "enabled" DROP DEFAULT;
ALTER TABLE public.app_topic ALTER COLUMN "order" DROP DEFAULT;
ALTER TABLE public.app_topic ALTER COLUMN "prompts" DROP DEFAULT;
ALTER TABLE public.app_topic ALTER COLUMN "meta_description" DROP DEFAULT;
ALTER TABLE public.app_topic ALTER COLUMN "icon" DROP DEFAULT;
ALTER TABLE public.app_topic ALTER COLUMN "description" DROP DEFAULT;
ALTER TABLE public.app_topic ALTER COLUMN "subtitle" DROP DEFAULT;
ALTER TABLE public.app_topic ALTER COLUMN "title" DROP DEFAULT;
ALTER TABLE public.app_topic ALTER COLUMN "slug" DROP DEFAULT;
ALTER TABLE public.app_topic ALTER COLUMN "id" DROP DEFAULT;
ALTER TABLE public.app_topic ALTER COLUMN "updated_at" DROP DEFAULT;
ALTER TABLE public.app_topic ALTER COLUMN "created_at" DROP DEFAULT;
ALTER TABLE public.app_fact_evidence ALTER COLUMN "locator_sha256" DROP DEFAULT;
ALTER TABLE public.app_fact_evidence ALTER COLUMN "role" DROP DEFAULT;
ALTER TABLE public.app_document_chunk ALTER COLUMN "text_sha256" DROP DEFAULT;
ALTER TABLE public.app_document_chunk ALTER COLUMN "body" DROP DEFAULT;
ALTER TABLE public.app_document ALTER COLUMN "state" DROP DEFAULT;
ALTER TABLE public.app_document ALTER COLUMN "media_type" DROP DEFAULT;
ALTER TABLE public.app_document ALTER COLUMN "sha256" DROP DEFAULT;
ALTER TABLE public.app_document ALTER COLUMN "s3_key" DROP DEFAULT;
ALTER TABLE public.app_document ALTER COLUMN "s3_bucket" DROP DEFAULT;
ALTER TABLE public.app_document ALTER COLUMN "category" DROP DEFAULT;
ALTER TABLE public.app_document ALTER COLUMN "title" DROP DEFAULT;
ALTER TABLE public.app_document ALTER COLUMN "key" DROP DEFAULT;
ALTER TABLE public.app_document ALTER COLUMN "owner_kind" DROP DEFAULT;
ALTER TABLE public.app_phase_document ALTER COLUMN "purpose" DROP DEFAULT;
ALTER TABLE public.app_matter ALTER COLUMN "title" DROP DEFAULT;
ALTER TABLE public.app_court ALTER COLUMN "name" DROP DEFAULT;
ALTER TABLE public.app_court ALTER COLUMN "slug" DROP DEFAULT;
ALTER TABLE public.app_chatmessage ALTER COLUMN "context_state" DROP DEFAULT;
ALTER TABLE public.app_chatmessage ALTER COLUMN "origin" DROP DEFAULT;
ALTER TABLE public.app_chatmessage ALTER COLUMN "item_kind" DROP DEFAULT;
ALTER TABLE public.app_chatmessage ALTER COLUMN "git_sha" DROP DEFAULT;
ALTER TABLE public.app_chatmessage ALTER COLUMN "cost" DROP DEFAULT;
ALTER TABLE public.app_chatmessage ALTER COLUMN "num_tokens" DROP DEFAULT;
ALTER TABLE public.app_chatmessage ALTER COLUMN "meta" DROP DEFAULT;
ALTER TABLE public.app_chatmessage ALTER COLUMN "hidden" DROP DEFAULT;
ALTER TABLE public.app_chatmessage ALTER COLUMN "data" DROP DEFAULT;
ALTER TABLE public.app_chatmessage ALTER COLUMN "id" DROP DEFAULT;
ALTER TABLE public.app_chatmessage ALTER COLUMN "updated_at" DROP DEFAULT;
ALTER TABLE public.app_chatmessage ALTER COLUMN "created_at" DROP DEFAULT;
ALTER TABLE public.app_chatthread ALTER COLUMN "next_sequence" DROP DEFAULT;
ALTER TABLE public.app_chatthread ALTER COLUMN "status" DROP DEFAULT;
ALTER TABLE public.app_chatthread ALTER COLUMN "description" DROP DEFAULT;
ALTER TABLE public.app_chatthread ALTER COLUMN "state" DROP DEFAULT;
ALTER TABLE public.app_chatthread ALTER COLUMN "thread_type" DROP DEFAULT;
ALTER TABLE public.app_chatthread ALTER COLUMN "id" DROP DEFAULT;
ALTER TABLE public.app_chatthread ALTER COLUMN "updated_at" DROP DEFAULT;
ALTER TABLE public.app_chatthread ALTER COLUMN "created_at" DROP DEFAULT;
ALTER TABLE public.app_topicflow DROP CONSTRAINT app_topicflow_attribution;
ALTER TABLE public.agent_prompt DROP CONSTRAINT agent_prompt_attribution;
ALTER TABLE public.app_document DROP CONSTRAINT app_document_attribution;
ALTER TABLE public.app_chatmessage DROP CONSTRAINT app_chatmessage_thread_id_deduplication_key_unique;
ALTER TABLE public.app_chatmessage DROP CONSTRAINT app_chatmessage_thread_id_sequence_unique;
ALTER TABLE public.app_chatthread DROP CONSTRAINT app_chatthread_id_identity_id_unique;
ALTER TABLE public.agent_run_step DROP CONSTRAINT agent_run_step_check_5;
ALTER TABLE public.agent_run_step DROP CONSTRAINT agent_run_step_check_4;
ALTER TABLE public.agent_run_step DROP CONSTRAINT agent_run_step_check_3;
ALTER TABLE public.agent_run_step DROP CONSTRAINT agent_run_step_check_2;
ALTER TABLE public.agent_run DROP CONSTRAINT agent_run_check_32;
ALTER TABLE public.agent_run DROP CONSTRAINT agent_run_check_31;
ALTER TABLE public.agent_run DROP CONSTRAINT agent_run_check_28;
ALTER TABLE public.agent_run DROP CONSTRAINT agent_run_check_27;
ALTER TABLE public.agent_run DROP CONSTRAINT agent_run_check_24;
ALTER TABLE public.agent_run DROP CONSTRAINT agent_run_check_22;
ALTER TABLE public.agent_run DROP CONSTRAINT agent_run_check_21;
ALTER TABLE public.agent_run DROP CONSTRAINT agent_run_check_20;
ALTER TABLE public.agent_run DROP CONSTRAINT agent_run_check_19;
ALTER TABLE public.agent_run DROP CONSTRAINT agent_run_check_14;
ALTER TABLE public.agent_run DROP CONSTRAINT agent_run_check_6;
ALTER TABLE public.agent_run DROP CONSTRAINT agent_run_check_5;
ALTER TABLE public.agent_run DROP CONSTRAINT agent_run_check_4;
ALTER TABLE public.app_message_attachment DROP CONSTRAINT app_message_attachment_check_3;
ALTER TABLE public.app_chatmessage DROP CONSTRAINT app_chatmessage_check_18;
ALTER TABLE public.app_chatmessage DROP CONSTRAINT app_chatmessage_check_17;
ALTER TABLE public.app_chatmessage DROP CONSTRAINT app_chatmessage_check_16;
ALTER TABLE public.app_chatmessage DROP CONSTRAINT app_chatmessage_check_15;
ALTER TABLE public.app_chatmessage DROP CONSTRAINT app_chatmessage_check_8;
ALTER TABLE public.app_chatmessage DROP CONSTRAINT app_chatmessage_check_7;
ALTER TABLE public.app_chatmessage DROP CONSTRAINT app_chatmessage_check_6;
ALTER TABLE public.app_chatmessage DROP CONSTRAINT app_chatmessage_check_5;
ALTER TABLE public.app_chatmessage DROP CONSTRAINT app_chatmessage_check_4;
ALTER TABLE public.app_chatthread DROP CONSTRAINT app_chatthread_check_11;
ALTER TABLE public.app_chatthread DROP CONSTRAINT app_chatthread_check_10;
ALTER TABLE public.app_chatthread DROP CONSTRAINT app_chatthread_check_8;
ALTER TABLE public.app_chatthread DROP CONSTRAINT app_chatthread_check_7;
ALTER TABLE public.agent_memory_source DROP CONSTRAINT agent_memory_source_check_7;
ALTER TABLE public.agent_memory_source DROP CONSTRAINT agent_memory_source_check_6;
ALTER TABLE public.agent_memory DROP CONSTRAINT agent_memory_check_14;
ALTER TABLE public.agent_memory DROP CONSTRAINT agent_memory_check_13;
ALTER TABLE public.agent_memory DROP CONSTRAINT agent_memory_check_12;
ALTER TABLE public.agent_memory DROP CONSTRAINT agent_memory_check_5;
ALTER TABLE public.agent_memory DROP CONSTRAINT agent_memory_check_3;
ALTER TABLE public.app_phase_progress DROP CONSTRAINT app_phase_progress_check_9;
ALTER TABLE public.app_phase_progress DROP CONSTRAINT app_phase_progress_check_3;
ALTER TABLE public.app_matter_procedure DROP CONSTRAINT app_matter_procedure_check_7;
ALTER TABLE public.app_matter_procedure DROP CONSTRAINT app_matter_procedure_check_3;
ALTER TABLE public.app_fact_evidence DROP CONSTRAINT app_fact_evidence_check_8;
ALTER TABLE public.app_fact_evidence DROP CONSTRAINT app_fact_evidence_check_7;
ALTER TABLE public.app_fact_evidence DROP CONSTRAINT app_fact_evidence_check_2;
ALTER TABLE public.app_variableanswer DROP CONSTRAINT app_variableanswer_check_14;
ALTER TABLE public.app_variableanswer DROP CONSTRAINT app_variableanswer_check_13;
ALTER TABLE public.app_variableanswer DROP CONSTRAINT app_variableanswer_check_7;
ALTER TABLE public.app_variableanswer DROP CONSTRAINT app_variableanswer_check_6;
ALTER TABLE public.app_variableanswer DROP CONSTRAINT app_variableanswer_check_5;
ALTER TABLE public.app_variable DROP CONSTRAINT app_variable_check_3;
ALTER TABLE public.app_variable DROP CONSTRAINT app_variable_check_2;
ALTER TABLE public.app_document_chunk DROP CONSTRAINT app_document_chunk_check_5;
ALTER TABLE public.app_document_chunk DROP CONSTRAINT app_document_chunk_check_2;
ALTER TABLE public.app_document DROP CONSTRAINT app_document_check_46;
ALTER TABLE public.app_document DROP CONSTRAINT app_document_check_45;
ALTER TABLE public.app_document DROP CONSTRAINT app_document_check_41;
ALTER TABLE public.app_document DROP CONSTRAINT app_document_check_39;
ALTER TABLE public.app_document DROP CONSTRAINT app_document_check_32;
ALTER TABLE public.app_document DROP CONSTRAINT app_document_check_31;
ALTER TABLE public.app_document DROP CONSTRAINT app_document_check_30;
ALTER TABLE public.app_document DROP CONSTRAINT app_document_check_29;
ALTER TABLE public.app_document DROP CONSTRAINT app_document_check_27;
ALTER TABLE public.app_document DROP CONSTRAINT app_document_check_21;
ALTER TABLE public.app_document DROP CONSTRAINT app_document_check_20;
ALTER TABLE public.app_document DROP CONSTRAINT app_document_check_15;
ALTER TABLE public.app_document DROP CONSTRAINT app_document_check_14;
ALTER TABLE public.app_document DROP CONSTRAINT app_document_check_10;
ALTER TABLE public.app_document DROP CONSTRAINT app_document_check_9;
ALTER TABLE public.app_document DROP CONSTRAINT app_document_check_6;
ALTER TABLE public.app_document DROP CONSTRAINT app_document_check_1;
ALTER TABLE public.agent_prompt DROP CONSTRAINT agent_prompt_check_14;
ALTER TABLE public.agent_prompt DROP CONSTRAINT agent_prompt_check_13;
ALTER TABLE public.agent_prompt DROP CONSTRAINT agent_prompt_check_7;
ALTER TABLE public.agent_prompt DROP CONSTRAINT agent_prompt_check_6;
ALTER TABLE public.agent_prompt DROP CONSTRAINT agent_prompt_check_5;
ALTER TABLE public.app_phase_document DROP CONSTRAINT app_phase_document_check_4;
ALTER TABLE public.app_phase_document DROP CONSTRAINT app_phase_document_check_3;
ALTER TABLE public.app_topicflowinterviewvariable DROP CONSTRAINT app_topicflowinterviewvariable_check_3;
ALTER TABLE public.app_topicflowinterviewpage DROP CONSTRAINT app_topicflowinterviewpage_check_3;
ALTER TABLE public.app_topicflow DROP CONSTRAINT app_topicflow_check_15;
ALTER TABLE public.app_topicflow DROP CONSTRAINT app_topicflow_check_14;
ALTER TABLE public.app_topicflow DROP CONSTRAINT app_topicflow_check_7;
ALTER TABLE public.app_topicflow DROP CONSTRAINT app_topicflow_check_4;
ALTER TABLE public.app_matter DROP CONSTRAINT app_matter_check_10;
ALTER TABLE public.app_matter DROP CONSTRAINT app_matter_check_5;
ALTER TABLE public.app_useridentity DROP CONSTRAINT app_useridentity_check_2;
ALTER TABLE public.app_document_chunk DROP COLUMN search_vector, DROP COLUMN embedding;
""",
    )]
