-- Foreign keys stay within the new model. Provider tool_call_id is an opaque string.
DO $foreign_keys$
DECLARE c record; target_table text; target_column text;
BEGIN
    FOR c IN SELECT table_name, column_name FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name LIKE 'agent\_%' ESCAPE '\'
          AND column_name LIKE '%\_id' ESCAPE '\'
          AND NOT (table_name = 'agent_user' AND column_name = 'user_id')
          AND column_name <> 'tool_call_id'
    LOOP
        target_table := CASE c.column_name
            WHEN 'previous_version_id' THEN c.table_name
            WHEN 'context_court_topic_id' THEN 'agent_court_topic'
            WHEN 'checkpoint_step_id' THEN 'agent_run_step'
            WHEN 'supersedes_id' THEN c.table_name
            WHEN 'owner_user_id' THEN 'agent_user'
            WHEN 'owner_court_id' THEN 'agent_court'
            WHEN 'last_run_step_id' THEN 'agent_run_step'
            WHEN 'generated_step_id' THEN 'agent_run_step'
            WHEN 'anchor_fact_definition_id' THEN 'agent_fact_definition'
            ELSE 'agent_' || left(c.column_name, -3) END;
        target_column := CASE WHEN target_table = 'agent_user' THEN 'user_id' ELSE 'id' END;
        EXECUTE format('ALTER TABLE public.%I ADD CONSTRAINT %I FOREIGN KEY (%I) REFERENCES public.%I(%I) ON DELETE RESTRICT DEFERRABLE INITIALLY IMMEDIATE',
            c.table_name, c.table_name || '_' || c.column_name || '_fk', c.column_name, target_table, target_column);
        EXECUTE format('CREATE INDEX %I ON public.%I(%I)',
            c.table_name || '_' || c.column_name || '_idx', c.table_name, c.column_name);
    END LOOP;
END
$foreign_keys$;

ALTER TABLE public.agent_conversation ADD FOREIGN KEY (matter_id, user_id, court_topic_id)
    REFERENCES public.agent_matter(id, user_id, court_topic_id);
ALTER TABLE public.agent_conversation ADD FOREIGN KEY (court_topic_id, court_id, topic_id)
    REFERENCES public.agent_court_topic(id, court_id, topic_id);
ALTER TABLE public.agent_fact_assertion ADD FOREIGN KEY (matter_id, user_id)
    REFERENCES public.agent_matter(id, user_id);
ALTER TABLE public.agent_memory ADD FOREIGN KEY (matter_id, user_id)
    REFERENCES public.agent_matter(id, user_id);
ALTER TABLE public.agent_memory ADD FOREIGN KEY (conversation_id, user_id)
    REFERENCES public.agent_conversation(id, user_id);
ALTER TABLE public.agent_conversation_item ADD FOREIGN KEY (run_id, conversation_id)
    REFERENCES public.agent_run(id, conversation_id);
ALTER TABLE public.agent_conversation_item ADD FOREIGN KEY (run_step_id, run_id)
    REFERENCES public.agent_run_step(id, run_id);
ALTER TABLE public.agent_run ADD FOREIGN KEY (checkpoint_step_id, id)
    REFERENCES public.agent_run_step(id, run_id);

CREATE INDEX agent_matter_recent ON public.agent_matter(user_id, updated_at DESC);
CREATE INDEX agent_conversation_recent ON public.agent_conversation(user_id, updated_at DESC);
CREATE INDEX agent_run_state ON public.agent_run(state, updated_at);
CREATE INDEX agent_fact_active ON public.agent_fact_assertion(user_id, fact_definition_id, matter_id, observed_at DESC)
    WHERE state = 'active' AND invalidated_at IS NULL;
CREATE INDEX agent_document_work ON public.agent_document(storage_state, index_state);

-- Trigger helpers are internal routines, not model-callable tools.
CREATE FUNCTION public.agent_touch_updated_at() RETURNS trigger
LANGUAGE plpgsql SET search_path = pg_catalog, public, pg_temp AS $$
BEGIN
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
    CASE TG_TABLE_NAME
    WHEN 'agent_user' THEN
        IF OLD.user_id IS DISTINCT FROM NEW.user_id THEN
            RAISE EXCEPTION 'Agent user identity is immutable' USING ERRCODE = '23514';
        END IF;
    WHEN 'agent_matter' THEN
        IF (OLD.user_id, OLD.court_topic_id) IS DISTINCT FROM (NEW.user_id, NEW.court_topic_id) THEN
            RAISE EXCEPTION 'Matter ownership and scope are immutable' USING ERRCODE = '23514';
        END IF;
    WHEN 'agent_conversation' THEN
        IF OLD.user_id IS DISTINCT FROM NEW.user_id
            OR (OLD.matter_id IS NOT NULL AND OLD.matter_id IS DISTINCT FROM NEW.matter_id)
            OR (OLD.court_id IS NOT NULL AND OLD.court_id IS DISTINCT FROM NEW.court_id)
            OR (OLD.topic_id IS NOT NULL AND OLD.topic_id IS DISTINCT FROM NEW.topic_id) THEN
            RAISE EXCEPTION 'Bound conversation ownership and scope are immutable' USING ERRCODE = '23514';
        END IF;
    WHEN 'agent_court_topic' THEN
        frozen := true; allowed := allowed || ARRAY['config', 'enabled'];
    WHEN 'agent_procedure', 'agent_prompt', 'agent_document' THEN
        FOREACH field IN ARRAY ARRAY['key','slug','court_topic_id','owner_kind','owner_court_id','owner_user_id','version','previous_version_id'] LOOP
            IF old_data->field IS DISTINCT FROM new_data->field THEN
                RAISE EXCEPTION 'Revision identity and lineage are immutable' USING ERRCODE = '23514';
            END IF;
        END LOOP;
        frozen := OLD.state IN ('published','private','withdrawn');
        allowed := allowed || ARRAY['state'];
        IF TG_TABLE_NAME = 'agent_document' THEN
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
    WHEN 'agent_phase', 'agent_phase_fact', 'agent_phase_document', 'agent_phase_deadline' THEN
        IF TG_TABLE_NAME = 'agent_phase' THEN
            SELECT state INTO parent_state FROM public.agent_procedure
                WHERE id = (old_data->>'procedure_id')::uuid;
        ELSE
            SELECT v.state INTO parent_state FROM public.agent_phase p
                JOIN public.agent_procedure v ON v.id = p.procedure_id
                WHERE p.id = (old_data->>'phase_id')::uuid;
        END IF;
        frozen := parent_state IN ('published', 'withdrawn');
    WHEN 'agent_fact_definition' THEN
        frozen := true; allowed := allowed || ARRAY['enabled'];
    WHEN 'agent_run' THEN
        IF OLD.conversation_id IS DISTINCT FROM NEW.conversation_id THEN
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
    WHEN 'agent_conversation_item' THEN
        IF (OLD.conversation_id, OLD.run_id, OLD.run_step_id, OLD.sequence, OLD.deduplication_key, OLD.origin, OLD.item_kind, OLD.visibility)
            IS DISTINCT FROM (NEW.conversation_id, NEW.run_id, NEW.run_step_id, NEW.sequence, NEW.deduplication_key, NEW.origin, NEW.item_kind, NEW.visibility) THEN
            RAISE EXCEPTION 'Conversation item lineage is immutable' USING ERRCODE = '23514';
        END IF;
    WHEN 'agent_document_chunk' THEN
        IF OLD.document_id IS DISTINCT FROM NEW.document_id THEN
            RAISE EXCEPTION 'Chunk source is immutable' USING ERRCODE = '23514';
        END IF;
    WHEN 'agent_fact_evidence', 'agent_memory_source' THEN frozen := true;
    WHEN 'agent_fact_assertion' THEN
        frozen := true; allowed := allowed || ARRAY['state', 'confirmation_state', 'invalidated_at', 'value'];
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
DECLARE owner_id text; source_owner text; scope_id uuid; other_scope uuid;
    parent_state text; parent_kind text; actual_count integer; bad_count integer; fact_scope text; fact_key text;
    j jsonb := to_jsonb(NEW); previous jsonb; field text; doc public.agent_document%ROWTYPE; source_id uuid;
    entry record; anchor jsonb; selected jsonb; target_table text; highest integer;
BEGIN
    -- Check the final chunk set at commit, allowing an atomic delete/insert replacement.
    IF TG_NARGS = 1 AND TG_ARGV[0] = 'index' THEN
        IF TG_TABLE_NAME = 'agent_document' THEN source_id := coalesce(NEW.id, OLD.id);
        ELSE source_id := coalesce(NEW.document_id, OLD.document_id); END IF;
        SELECT * INTO doc FROM public.agent_document WHERE id = source_id;
        IF NOT FOUND THEN RETURN NULL; END IF;
        SELECT count(*), count(*) FILTER (WHERE
            (doc.embedding_dimensions IS NULL AND embedding IS NOT NULL) OR
            (doc.embedding_dimensions IS NOT NULL AND (embedding IS NULL OR public.vector_dims(embedding) <> doc.embedding_dimensions)) OR
            length(body) > coalesce((doc.index_config->>'max_characters')::integer, 65536))
            INTO actual_count, bad_count FROM public.agent_document_chunk WHERE document_id = source_id;
        IF doc.index_invalidated_at IS NULL AND (bad_count > 0 OR
            (doc.index_state = 'ready' AND actual_count <> doc.chunk_count) OR
            (doc.index_state <> 'ready' AND actual_count > 0)) THEN
            RAISE EXCEPTION 'Active index must contain its declared bounded chunks and matching embeddings' USING ERRCODE = '23514';
        END IF;
        RETURN NULL;
    END IF;
    CASE TG_TABLE_NAME
    WHEN 'agent_procedure', 'agent_prompt', 'agent_document' THEN
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
        IF TG_TABLE_NAME = 'agent_procedure' AND j->>'state' = 'published' AND EXISTS (
            SELECT FROM public.agent_phase ph JOIN public.agent_phase_document pd ON pd.phase_id = ph.id
            WHERE ph.procedure_id = NEW.id AND NOT EXISTS (SELECT FROM public.agent_corpus_document cd
                WHERE cd.court_topic_id = (j->>'court_topic_id')::uuid AND cd.document_id = pd.document_id AND cd.enabled)
        ) THEN RAISE EXCEPTION 'Procedure references a document outside its corpus' USING ERRCODE = '23514'; END IF;
    WHEN 'agent_corpus_document' THEN
        SELECT ct.court_id, d.owner_court_id INTO scope_id, other_scope
            FROM public.agent_court_topic ct, public.agent_document d
            WHERE ct.id = NEW.court_topic_id AND d.id = NEW.document_id AND d.version = 1;
        IF scope_id IS DISTINCT FROM other_scope OR scope_id IS NULL THEN
            RAISE EXCEPTION 'Corpus document must belong to the same court' USING ERRCODE = '23514';
        END IF;
    WHEN 'agent_matter_document' THEN
        SELECT m.user_id, d.owner_user_id INTO owner_id, source_owner
            FROM public.agent_matter m, public.agent_document d WHERE m.id = NEW.matter_id AND d.id = NEW.document_id AND d.version = 1;
        IF owner_id IS DISTINCT FROM source_owner OR owner_id IS NULL THEN
            RAISE EXCEPTION 'Matter document owner mismatch' USING ERRCODE = '23514';
        END IF;
    WHEN 'agent_phase', 'agent_phase_fact', 'agent_phase_document', 'agent_phase_deadline' THEN
        IF TG_TABLE_NAME = 'agent_phase' THEN
            SELECT state INTO parent_state FROM public.agent_procedure WHERE id = NEW.procedure_id;
        ELSE
            SELECT p.state, p.court_topic_id INTO parent_state, scope_id
                FROM public.agent_phase ph JOIN public.agent_procedure p ON p.id = ph.procedure_id WHERE ph.id = (j->>'phase_id')::uuid;
        END IF;
        IF parent_state IN ('published', 'withdrawn') THEN
            RAISE EXCEPTION 'Edit phases only within a draft revision' USING ERRCODE = '23514';
        END IF;
        IF TG_TABLE_NAME = 'agent_phase_document' AND NOT EXISTS (
            SELECT FROM public.agent_corpus_document WHERE court_topic_id = scope_id AND document_id = (j->>'document_id')::uuid AND enabled
        ) THEN
            RAISE EXCEPTION 'Phase document must belong to its court/topic corpus' USING ERRCODE = '23514';
        END IF;
    WHEN 'agent_document_chunk' THEN
        IF NEW.text_sha256 <> encode(sha256(convert_to(NEW.body,'UTF8')),'hex') THEN
            RAISE EXCEPTION 'Chunk text digest mismatch' USING ERRCODE = '23514';
        END IF;
        PERFORM id FROM public.agent_document WHERE id = NEW.document_id FOR UPDATE;
    WHEN 'agent_fact_assertion' THEN
        SELECT scope, key INTO fact_scope, fact_key FROM public.agent_fact_definition WHERE id = NEW.fact_definition_id;
        IF (fact_scope = 'user') IS DISTINCT FROM (NEW.matter_id IS NULL) THEN
            RAISE EXCEPTION 'Fact scope mismatch' USING ERRCODE = '23514';
        END IF;
        IF NEW.supersedes_id IS NOT NULL AND NOT EXISTS (
            SELECT FROM public.agent_fact_assertion a JOIN public.agent_fact_definition d ON d.id = a.fact_definition_id
            WHERE a.id = NEW.supersedes_id AND a.user_id = NEW.user_id
                AND a.matter_id IS NOT DISTINCT FROM NEW.matter_id AND d.key = fact_key AND d.scope = fact_scope
        ) THEN RAISE EXCEPTION 'Fact supersession owner/key/scope mismatch' USING ERRCODE = '23514'; END IF;
    WHEN 'agent_fact_definition' THEN
        IF EXISTS (SELECT FROM public.agent_fact_definition WHERE key = NEW.key AND scope <> NEW.scope) THEN
            RAISE EXCEPTION 'A semantic fact key cannot change scope between versions' USING ERRCODE = '23514';
        END IF;
    WHEN 'agent_matter_procedure' THEN
        SELECT m.court_topic_id, p.court_topic_id INTO scope_id, other_scope
            FROM public.agent_matter m, public.agent_procedure p WHERE m.id = NEW.matter_id AND p.id = NEW.procedure_id AND p.version = 1;
        IF scope_id IS DISTINCT FROM other_scope OR scope_id IS NULL THEN RAISE EXCEPTION 'Matter procedure scope mismatch' USING ERRCODE = '23514'; END IF;
    WHEN 'agent_phase_progress' THEN
        IF NOT EXISTS (SELECT FROM public.agent_matter_procedure mp JOIN public.agent_procedure base ON base.id = mp.procedure_id
            JOIN public.agent_phase ph ON ph.id = NEW.phase_id JOIN public.agent_procedure p ON p.id = ph.procedure_id
                AND p.slug = base.slug AND p.court_topic_id = base.court_topic_id
            JOIN public.agent_run_step s ON s.id = NEW.last_run_step_id JOIN public.agent_run r ON r.id = s.run_id
            JOIN public.agent_conversation c ON c.id = r.conversation_id AND c.matter_id = mp.matter_id
            WHERE mp.id = NEW.matter_procedure_id AND r.manifest->'procedures'->>base.id::text = p.id::text) THEN
            RAISE EXCEPTION 'Progress must use this matter and its pinned phase revision' USING ERRCODE = '23514';
        END IF;
    WHEN 'agent_memory' THEN
        SELECT c.user_id INTO source_owner FROM public.agent_run_step s JOIN public.agent_run r ON r.id = s.run_id
            JOIN public.agent_conversation c ON c.id = r.conversation_id WHERE s.id = NEW.generated_step_id;
        IF NEW.user_id IS DISTINCT FROM source_owner THEN RAISE EXCEPTION 'Memory generation owner mismatch' USING ERRCODE = '23514'; END IF;
        IF NEW.supersedes_id IS NOT NULL AND NOT EXISTS (SELECT FROM public.agent_memory WHERE id = NEW.supersedes_id AND user_id = NEW.user_id) THEN
            RAISE EXCEPTION 'Memory supersession owner mismatch' USING ERRCODE = '23514';
        END IF;
    WHEN 'agent_fact_evidence', 'agent_memory_source' THEN
        IF TG_TABLE_NAME = 'agent_fact_evidence' THEN
            SELECT user_id INTO owner_id FROM public.agent_fact_assertion WHERE id = NEW.fact_assertion_id;
        ELSE SELECT user_id INTO owner_id FROM public.agent_memory WHERE id = NEW.memory_id;
        END IF;
        IF j->>'conversation_item_id' IS NOT NULL THEN
            SELECT c.user_id INTO source_owner FROM public.agent_conversation_item i
                JOIN public.agent_conversation c ON c.id = i.conversation_id WHERE i.id = (j->>'conversation_item_id')::uuid;
        ELSIF j->>'document_id' IS NOT NULL THEN
            SELECT owner_user_id, owner_kind INTO source_owner, parent_kind
                FROM public.agent_document WHERE id = (j->>'document_id')::uuid;
            IF parent_kind = 'court' THEN source_owner := owner_id; END IF;
        ELSIF j->>'run_step_id' IS NOT NULL THEN
            SELECT c.user_id INTO source_owner FROM public.agent_run_step s JOIN public.agent_run r ON r.id = s.run_id
                JOIN public.agent_conversation c ON c.id = r.conversation_id WHERE s.id = (j->>'run_step_id')::uuid;
        ELSE SELECT user_id INTO source_owner FROM public.agent_fact_assertion WHERE id = (j->>'fact_assertion_id')::uuid;
        END IF;
        IF owner_id IS DISTINCT FROM source_owner OR source_owner IS NULL THEN
            RAISE EXCEPTION 'Private evidence/source owner mismatch' USING ERRCODE = '23514';
        END IF;
    WHEN 'agent_message_attachment' THEN
        SELECT c.user_id INTO owner_id FROM public.agent_conversation_item i JOIN public.agent_conversation c ON c.id = i.conversation_id
            WHERE i.id = NEW.conversation_item_id AND i.item_kind = 'message' AND i.visibility = 'user';
        SELECT owner_user_id INTO source_owner FROM public.agent_document WHERE id = NEW.document_id;
        IF owner_id IS DISTINCT FROM source_owner OR owner_id IS NULL THEN
            RAISE EXCEPTION 'Attachment must match the message owner' USING ERRCODE = '23514';
        END IF;
    WHEN 'agent_run_step' THEN
        IF NEW.instruction_canonical_json IS NOT NULL AND NEW.redacted_at IS NULL
            AND NEW.instruction_sha256 <> encode(sha256(convert_to(NEW.instruction_canonical_json,'UTF8')),'hex') THEN
            RAISE EXCEPTION 'Instruction snapshot digest mismatch' USING ERRCODE = '23514';
        END IF;
    WHEN 'agent_run' THEN
        IF NEW.checkpoint_sequence > 0 AND NEW.checkpoint_conversation_sequence > 0 AND NOT EXISTS (
            SELECT FROM public.agent_conversation_item WHERE conversation_id = NEW.conversation_id AND sequence = NEW.checkpoint_conversation_sequence
        ) THEN RAISE EXCEPTION 'Checkpoint cursor must belong to this conversation' USING ERRCODE = '23514'; END IF;
        IF NEW.context_selected_at IS NOT NULL AND (TG_OP = 'INSERT' OR OLD.context_selected_at IS NULL) THEN
            SELECT court_topic_id INTO scope_id FROM public.agent_conversation WHERE id = NEW.conversation_id;
            IF scope_id IS DISTINCT FROM NEW.context_court_topic_id THEN RAISE EXCEPTION 'Run context scope mismatch' USING ERRCODE = '23514'; END IF;
            IF NEW.manifest_sha256 <> encode(sha256(convert_to(NEW.manifest::text,'UTF8')),'hex') THEN RAISE EXCEPTION 'Manifest digest mismatch' USING ERRCODE = '23514'; END IF;
            FOREACH field IN ARRAY ARRAY['documents','procedures','prompts'] LOOP
                IF jsonb_typeof(NEW.manifest->field) IS DISTINCT FROM 'object' THEN RAISE EXCEPTION 'Manifest requires revision maps' USING ERRCODE = '23514'; END IF;
                target_table := CASE field WHEN 'documents' THEN 'agent_document' WHEN 'procedures' THEN 'agent_procedure' ELSE 'agent_prompt' END;
                FOR entry IN SELECT * FROM jsonb_each_text(NEW.manifest->field) LOOP
                    EXECUTE format('SELECT to_jsonb(p) FROM public.%I p WHERE id::text = $1 AND version = 1',target_table) INTO anchor USING entry.key;
                    EXECUTE format('SELECT to_jsonb(p) FROM public.%I p WHERE id::text = $1 AND state = ''published''',target_table) INTO selected USING entry.value;
                    IF anchor IS NULL OR selected IS NULL THEN RAISE EXCEPTION 'Manifest references unknown/unpublished revisions' USING ERRCODE = '23514'; END IF;
                    IF field = 'documents' THEN
                        IF anchor->>'owner_kind' <> 'court' OR anchor->'owner_court_id' IS DISTINCT FROM selected->'owner_court_id'
                            OR anchor->'key' IS DISTINCT FROM selected->'key' OR selected->>'storage_state' <> 'available' OR selected->>'deleted_at' IS NOT NULL
                            OR NOT EXISTS (SELECT FROM public.agent_corpus_document WHERE document_id::text = entry.key AND court_topic_id = scope_id AND enabled) THEN
                            RAISE EXCEPTION 'Manifest document scope/family mismatch' USING ERRCODE = '23514';
                        END IF;
                        SELECT max(version) INTO highest FROM public.agent_document WHERE owner_court_id::text = anchor->>'owner_court_id'
                            AND key = anchor->>'key' AND state = 'published' AND storage_state = 'available' AND deleted_at IS NULL;
                    ELSIF field = 'procedures' THEN
                        IF anchor->>'court_topic_id' IS DISTINCT FROM scope_id::text OR anchor->'court_topic_id' IS DISTINCT FROM selected->'court_topic_id'
                            OR anchor->'slug' IS DISTINCT FROM selected->'slug' THEN RAISE EXCEPTION 'Manifest procedure scope/family mismatch' USING ERRCODE = '23514'; END IF;
                        SELECT max(version) INTO highest FROM public.agent_procedure WHERE court_topic_id = scope_id AND slug = anchor->>'slug' AND state = 'published';
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
        AND tablename LIKE 'agent\_%' ESCAPE '\'
    LOOP
        EXECUTE format('CREATE TRIGGER agent_01_immutable BEFORE UPDATE ON public.%I FOR EACH ROW EXECUTE FUNCTION public.agent_guard_immutable()', t.tablename);
        EXECUTE format('CREATE TRIGGER agent_02_validate BEFORE INSERT OR UPDATE ON public.%I FOR EACH ROW EXECUTE FUNCTION public.agent_validate_record()', t.tablename);
        EXECUTE format('CREATE TRIGGER agent_03_timestamp BEFORE UPDATE ON public.%I FOR EACH ROW EXECUTE FUNCTION public.agent_touch_updated_at()', t.tablename);
    END LOOP;
END
$triggers$;

CREATE CONSTRAINT TRIGGER agent_document_index_complete AFTER INSERT OR UPDATE ON public.agent_document
    DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION public.agent_validate_record('index');
CREATE CONSTRAINT TRIGGER agent_chunk_index_complete AFTER INSERT OR UPDATE OR DELETE ON public.agent_document_chunk
    DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION public.agent_validate_record('index');
