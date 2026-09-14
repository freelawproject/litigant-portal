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

CREATE FUNCTION public.agent_lookup_context(p_user_id text, p_run_id uuid, p_host_policy jsonb)
RETURNS jsonb LANGUAGE sql STABLE SET search_path = pg_catalog, public, pg_temp AS $$
    SELECT jsonb_build_object('court_topic_id', r.context_court_topic_id, 'court_id', ct.court_id,
        'topic_id', ct.topic_id, 'matter_id', c.matter_id, 'manifest', r.manifest,
        'policies', jsonb_build_array(u.recall_limits || jsonb_build_object('enabled', coalesce(u.recall_enabled, true)),
            r.recall_policy_snapshot, coalesce(p_host_policy, '{"enabled":false}'::jsonb)))
    FROM public.agent_run r JOIN public.agent_conversation c ON c.id = r.conversation_id
    JOIN public.agent_user u ON u.user_id = c.user_id
    JOIN public.agent_court_topic ct ON ct.id = r.context_court_topic_id
    JOIN public.agent_court court ON court.id = ct.court_id
    JOIN public.agent_topic topic ON topic.id = ct.topic_id
    JOIN public.agent_matter m ON m.id = c.matter_id AND m.user_id = u.user_id
    WHERE r.id = p_run_id AND u.user_id = p_user_id AND u.deleted_at IS NULL
        AND c.deleted_at IS NULL AND m.deleted_at IS NULL AND ct.enabled AND court.enabled AND topic.enabled
$$;

CREATE FUNCTION public.agent_source_allowed(
    p_user_id text, p_kind text, p_id uuid, p_policies jsonb, p_depth integer DEFAULT 0
) RETURNS boolean LANGUAGE plpgsql STABLE
SET search_path = pg_catalog, public, pg_temp AS $$
DECLARE record_data record; source record; scope_court uuid; scope_topic uuid; scope_matter uuid;
    has_source boolean := false; basis_policies jsonb;
BEGIN
    IF p_depth > 12 OR NOT EXISTS (SELECT FROM public.agent_user WHERE user_id = p_user_id AND deleted_at IS NULL) THEN RETURN false; END IF;
    CASE p_kind
    WHEN 'document' THEN
        SELECT * INTO record_data FROM public.agent_document WHERE id = p_id AND storage_state = 'available' AND deleted_at IS NULL;
        IF NOT FOUND THEN RETURN false; END IF;
        IF record_data.owner_kind = 'court' THEN RETURN record_data.state = 'published'; END IF;
        IF record_data.owner_user_id IS DISTINCT FROM p_user_id OR record_data.state <> 'private' THEN RETURN false; END IF;
        IF public.agent_scope_allowed(p_policies, NULL, NULL, NULL) THEN RETURN true; END IF;
        RETURN EXISTS (SELECT FROM public.agent_matter_document md JOIN public.agent_document base ON base.id = md.document_id
            JOIN public.agent_matter m ON m.id = md.matter_id
            JOIN public.agent_court_topic ct ON ct.id = m.court_topic_id WHERE base.key = record_data.key AND base.owner_user_id = p_user_id
            AND m.user_id = p_user_id AND m.deleted_at IS NULL
            AND public.agent_scope_allowed(p_policies, ct.court_id, ct.topic_id, m.id));
    WHEN 'item', 'step' THEN
        IF p_kind = 'item' THEN
            SELECT c.* INTO record_data FROM public.agent_conversation_item i JOIN public.agent_conversation c ON c.id = i.conversation_id
                WHERE i.id = p_id AND i.redacted_at IS NULL AND i.context_state = 'accepted'
                    AND i.visibility = 'user' AND i.item_kind = 'message' AND i.origin IN ('user', 'model');
        ELSE
            SELECT c.* INTO record_data FROM public.agent_run_step s JOIN public.agent_run r ON r.id = s.run_id
                JOIN public.agent_conversation c ON c.id = r.conversation_id
                WHERE s.id = p_id AND s.redacted_at IS NULL AND s.state = 'completed';
        END IF;
        IF NOT FOUND OR record_data.user_id IS DISTINCT FROM p_user_id OR record_data.deleted_at IS NOT NULL THEN RETURN false; END IF;
        IF record_data.matter_id IS NOT NULL AND NOT EXISTS (SELECT FROM public.agent_matter WHERE id = record_data.matter_id AND deleted_at IS NULL) THEN RETURN false; END IF;
        RETURN public.agent_scope_allowed(p_policies, record_data.court_id, record_data.topic_id, record_data.matter_id);
    WHEN 'fact' THEN
        SELECT a.*, d.scope INTO record_data FROM public.agent_fact_assertion a JOIN public.agent_fact_definition d ON d.id = a.fact_definition_id
            WHERE a.id = p_id AND a.user_id = p_user_id AND a.state = 'active' AND a.invalidated_at IS NULL
                AND a.confirmation_state <> 'rejected' AND d.enabled;
        IF NOT FOUND THEN RETURN false; END IF;
        IF record_data.scope = 'matter' THEN
            SELECT ct.court_id, ct.topic_id, m.id INTO scope_court, scope_topic, scope_matter
                FROM public.agent_matter m JOIN public.agent_court_topic ct ON ct.id = m.court_topic_id
                WHERE m.id = record_data.matter_id AND m.user_id = p_user_id AND m.deleted_at IS NULL;
            IF NOT FOUND THEN RETURN false; END IF;
        END IF;
        IF NOT public.agent_scope_allowed(p_policies, scope_court, scope_topic, scope_matter, record_data.scope = 'user') THEN RETURN false; END IF;
        -- Global personal facts remain reusable when contextual history is narrowed.
        -- Availability/ownership of their original evidence is still checked.
        basis_policies := CASE WHEN record_data.scope = 'user' THEN '[{}]'::jsonb ELSE p_policies END;
        IF record_data.confirmation_state = 'confirmed' AND NOT EXISTS (
            SELECT FROM public.agent_fact_evidence e JOIN public.agent_conversation_item i ON i.id = e.conversation_item_id
            WHERE e.fact_assertion_id = p_id AND e.role = 'confirmation' AND i.origin = 'user'
                AND public.agent_source_allowed(p_user_id, 'item', i.id, basis_policies, p_depth + 1)
        ) THEN RETURN false; END IF;
        FOR source IN SELECT * FROM public.agent_fact_evidence WHERE fact_assertion_id = p_id AND role = 'basis' LOOP
            IF public.agent_source_allowed(p_user_id,
                CASE WHEN source.conversation_item_id IS NOT NULL THEN 'item' WHEN source.document_id IS NOT NULL THEN 'document' ELSE 'step' END,
                coalesce(source.conversation_item_id, source.document_id, source.run_step_id), basis_policies, p_depth + 1) THEN has_source := true; END IF;
        END LOOP;
        RETURN has_source;
    WHEN 'memory' THEN
        SELECT * INTO record_data FROM public.agent_memory WHERE id = p_id AND user_id = p_user_id
            AND state = 'active' AND invalidated_at IS NULL AND btrim(body) <> '';
        IF NOT FOUND OR NOT public.agent_source_allowed(p_user_id, 'step', record_data.generated_step_id, '[{}]', p_depth + 1) THEN RETURN false; END IF;
        IF record_data.matter_id IS NOT NULL THEN
            SELECT ct.court_id, ct.topic_id, m.id INTO scope_court, scope_topic, scope_matter
                FROM public.agent_matter m JOIN public.agent_court_topic ct ON ct.id = m.court_topic_id
                WHERE m.id = record_data.matter_id AND m.user_id = p_user_id AND m.deleted_at IS NULL;
            IF NOT FOUND OR NOT public.agent_scope_allowed(p_policies, scope_court, scope_topic, scope_matter) THEN RETURN false; END IF;
        END IF;
        -- Every source must pass; a mixed-matter summary cannot leak excluded history.
        FOR source IN SELECT * FROM public.agent_memory_source WHERE memory_id = p_id LOOP
            has_source := true;
            IF NOT public.agent_source_allowed(p_user_id,
                CASE WHEN source.conversation_item_id IS NOT NULL THEN 'item' WHEN source.document_id IS NOT NULL THEN 'document' ELSE 'fact' END,
                coalesce(source.conversation_item_id, source.document_id, source.fact_assertion_id), p_policies, p_depth + 1) THEN RETURN false; END IF;
        END LOOP;
        RETURN has_source AND public.agent_scope_allowed(
            (SELECT jsonb_agg(jsonb_build_object('enabled', coalesce(p->'enabled', 'true'::jsonb))) FROM jsonb_array_elements(p_policies) p), NULL, NULL, NULL);
    WHEN 'progress' THEN
        SELECT m.id, ct.court_id, ct.topic_id, pp.last_run_step_id INTO record_data
            FROM public.agent_phase_progress pp JOIN public.agent_matter_procedure mp ON mp.id = pp.matter_procedure_id
            JOIN public.agent_matter m ON m.id = mp.matter_id JOIN public.agent_court_topic ct ON ct.id = m.court_topic_id
            WHERE pp.id = p_id AND m.user_id = p_user_id AND m.deleted_at IS NULL;
        IF NOT FOUND THEN RETURN false; END IF;
        RETURN public.agent_scope_allowed(p_policies, record_data.court_id, record_data.topic_id, record_data.id)
            AND public.agent_source_allowed(p_user_id, 'step', record_data.last_run_step_id, p_policies, p_depth + 1);
    ELSE RETURN false;
    END CASE;
END
$$;

CREATE FUNCTION public.agent_private_candidates(
    p_user_id text, p_policies jsonb, p_categories text[], p_source_id uuid DEFAULT NULL
) RETURNS TABLE(category text, source_id uuid, revision_id uuid, title text, body text,
    court_id uuid, topic_id uuid, matter_id uuid, labels jsonb)
LANGUAGE sql STABLE SET search_path = pg_catalog, public, pg_temp AS $$
    SELECT 'user_documents', d.id, d.id, d.title, coalesce(ch.body, d.title), NULL::uuid, NULL::uuid, NULL::uuid,
        jsonb_build_object('authority', 'private', 'chunk_id', ch.id, 'locator', ch.locator,
            'index_revision', d.index_revision, 'ordinal', ch.ordinal, 'content_available', ch.id IS NOT NULL,
            'observed_at', d.created_at, 'associations', coalesce((
                SELECT jsonb_agg(jsonb_build_object('matter_id', m.id, 'court_id', ct.court_id, 'topic_id', ct.topic_id))
                FROM public.agent_matter_document md JOIN public.agent_document base ON base.id = md.document_id
                JOIN public.agent_matter m ON m.id = md.matter_id JOIN public.agent_court_topic ct ON ct.id = m.court_topic_id
                WHERE base.key = d.key AND base.owner_user_id = p_user_id AND m.user_id = p_user_id AND m.deleted_at IS NULL
                    AND public.agent_scope_allowed(p_policies, ct.court_id, ct.topic_id, m.id)), '[]'::jsonb))
    FROM public.agent_document d
    LEFT JOIN public.agent_document_chunk ch ON ch.document_id = d.id AND d.index_state = 'ready' AND d.index_invalidated_at IS NULL
    WHERE 'user_documents' = ANY(p_categories) AND d.owner_user_id = p_user_id
        AND (CASE WHEN p_source_id IS NULL THEN NOT EXISTS (
            SELECT FROM public.agent_document newer WHERE newer.owner_user_id = p_user_id AND newer.key = d.key AND newer.version > d.version
                AND newer.state = 'private' AND newer.storage_state = 'available' AND newer.deleted_at IS NULL
        ) ELSE d.id = p_source_id END)
        AND public.agent_source_allowed(p_user_id, 'document', d.id, p_policies)
    UNION ALL
    SELECT CASE WHEN d.scope = 'user' THEN 'user_facts' ELSE 'matter_facts' END,
        a.id, d.id, d.label, d.label || ': ' || a.value::text, ct.court_id, ct.topic_id, a.matter_id,
        jsonb_build_object('authority', 'private', 'fact_key', d.key, 'value', a.value,
            'evidence_kind', a.evidence_kind, 'confirmation_state', a.confirmation_state,
            'observed_at', a.observed_at, 'effective_from', a.effective_from, 'effective_to', a.effective_to)
    FROM public.agent_fact_assertion a JOIN public.agent_fact_definition d ON d.id = a.fact_definition_id
    LEFT JOIN public.agent_matter m ON m.id = a.matter_id LEFT JOIN public.agent_court_topic ct ON ct.id = m.court_topic_id
    WHERE (CASE WHEN d.scope = 'user' THEN 'user_facts' ELSE 'matter_facts' END) = ANY(p_categories)
        AND a.user_id = p_user_id AND (p_source_id IS NULL OR a.id = p_source_id)
        AND public.agent_source_allowed(p_user_id, 'fact', a.id, p_policies)
    UNION ALL
    SELECT 'conversation_history', i.id, NULL::uuid, c.title, i.search_text, c.court_id, c.topic_id, c.matter_id,
        jsonb_build_object('authority', 'private_history', 'conversation_id', c.id, 'origin', i.origin, 'observed_at', i.created_at)
    FROM public.agent_conversation_item i JOIN public.agent_conversation c ON c.id = i.conversation_id
    WHERE 'conversation_history' = ANY(p_categories) AND c.user_id = p_user_id
        AND (p_source_id IS NULL OR i.id = p_source_id) AND i.search_text IS NOT NULL
        AND public.agent_source_allowed(p_user_id, 'item', i.id, p_policies)
    UNION ALL
    SELECT 'memory', mem.id, NULL::uuid, 'Conversation memory', mem.body, ct.court_id, ct.topic_id, mem.matter_id,
        jsonb_build_object('authority', 'private_summary', 'kind', mem.kind, 'observed_at', mem.created_at,
            'source_ids', (SELECT jsonb_agg(coalesce(s.conversation_item_id, s.fact_assertion_id, s.document_id)) FROM public.agent_memory_source s WHERE s.memory_id = mem.id))
    FROM public.agent_memory mem LEFT JOIN public.agent_matter m ON m.id = mem.matter_id
    LEFT JOIN public.agent_court_topic ct ON ct.id = m.court_topic_id
    WHERE 'memory' = ANY(p_categories) AND mem.user_id = p_user_id AND (p_source_id IS NULL OR mem.id = p_source_id)
        AND public.agent_source_allowed(p_user_id, 'memory', mem.id, p_policies)
    UNION ALL
    SELECT 'procedure_progress', pp.id, ph.procedure_id, ph.title, ph.title || ': ' || pp.state,
        ct.court_id, ct.topic_id, m.id, jsonb_build_object('authority', 'private_progress', 'state', pp.state, 'phase_id', ph.id, 'observed_at', pp.updated_at)
    FROM public.agent_phase_progress pp JOIN public.agent_phase ph ON ph.id = pp.phase_id
    JOIN public.agent_matter_procedure mp ON mp.id = pp.matter_procedure_id JOIN public.agent_matter m ON m.id = mp.matter_id
    JOIN public.agent_court_topic ct ON ct.id = m.court_topic_id
    WHERE 'procedure_progress' = ANY(p_categories) AND m.user_id = p_user_id AND (p_source_id IS NULL OR pp.id = p_source_id)
        AND public.agent_source_allowed(p_user_id, 'progress', pp.id, p_policies)
$$;

CREATE FUNCTION public.agent_search_private(
    p_user_id text, p_run_id uuid, p_host_policy jsonb, p_query text,
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
    p_user_id text, p_run_id uuid, p_host_policy jsonb, p_category text, p_source_id uuid, p_filters jsonb DEFAULT '{}'
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

CREATE FUNCTION public.agent_corpus_candidates(p_user_id text, p_run_id uuid)
RETURNS TABLE(source_id uuid, revision_id uuid, title text, body text, court_id uuid, topic_id uuid, labels jsonb)
LANGUAGE sql STABLE SET search_path = pg_catalog, public, pg_temp AS $$
    WITH context AS (SELECT public.agent_lookup_context(p_user_id, p_run_id, '{}') AS ctx)
    SELECT doc.id, doc.id, doc.title, coalesce(ch.body, doc.title), (ctx->>'court_id')::uuid, (ctx->>'topic_id')::uuid,
        jsonb_build_object('authority', 'published_court_source', 'chunk_id', ch.id, 'index_revision', doc.index_revision,
            'locator', ch.locator, 'content_available', ch.id IS NOT NULL, 'published_at', doc.published_at)
    FROM context JOIN public.agent_corpus_document cd ON cd.court_topic_id = (ctx->>'court_topic_id')::uuid AND cd.enabled
    JOIN public.agent_document base ON base.id = cd.document_id AND base.version = 1
    JOIN public.agent_document doc ON doc.key = base.key AND doc.owner_court_id = base.owner_court_id
        AND doc.id::text = ctx->'manifest'->'documents'->>base.id::text
        AND doc.state = 'published' AND doc.storage_state = 'available' AND doc.deleted_at IS NULL
    LEFT JOIN public.agent_document_chunk ch ON ch.document_id = doc.id AND doc.index_state = 'ready' AND doc.index_invalidated_at IS NULL
    UNION ALL
    SELECT p.id, p.id, p.title, p.guidance, (ctx->>'court_id')::uuid, (ctx->>'topic_id')::uuid,
        jsonb_build_object('authority', 'published_procedure', 'procedure_id', p.id, 'published_at', p.published_at)
    FROM context JOIN public.agent_procedure base ON base.court_topic_id = (ctx->>'court_topic_id')::uuid AND base.version = 1
    JOIN public.agent_procedure p ON p.court_topic_id = base.court_topic_id AND p.slug = base.slug
        AND p.id::text = ctx->'manifest'->'procedures'->>base.id::text AND p.state = 'published'
    UNION ALL
    SELECT ph.id, p.id, ph.title, ph.instructions, (ctx->>'court_id')::uuid, (ctx->>'topic_id')::uuid,
        jsonb_build_object('authority', 'published_phase', 'procedure_id', p.id, 'phase_key', ph.key)
    FROM context JOIN public.agent_procedure base ON base.court_topic_id = (ctx->>'court_topic_id')::uuid AND base.version = 1
    JOIN public.agent_procedure p ON p.court_topic_id = base.court_topic_id AND p.slug = base.slug
        AND p.id::text = ctx->'manifest'->'procedures'->>base.id::text AND p.state = 'published'
    JOIN public.agent_phase ph ON ph.procedure_id = p.id
$$;

CREATE FUNCTION public.agent_search_corpus(p_user_id text, p_run_id uuid, p_query text, p_limit integer DEFAULT 10)
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

CREATE FUNCTION public.agent_get_corpus_source(p_user_id text, p_run_id uuid, p_source_id uuid)
RETURNS SETOF jsonb LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = pg_catalog, public, pg_temp AS $$
    SELECT jsonb_build_object('category', 'court_corpus', 'source_id', c.source_id, 'revision_id', c.revision_id,
        'title', left(c.title, 200), 'snippet', left(c.body, 1000), 'court_id', c.court_id, 'topic_id', c.topic_id,
        'labels', CASE WHEN octet_length(c.labels::text) <= 4096 THEN c.labels ELSE
            jsonb_build_object('authority', c.labels->'authority', 'metadata_truncated', true) END)
    FROM public.agent_corpus_candidates(p_user_id, p_run_id) c WHERE c.source_id = p_source_id
    ORDER BY c.labels->>'chunk_id' LIMIT 1
$$;

-- Non-login group roles avoid installing credentials or changing host settings.
-- A dedicated future login can inherit exactly one of CRUD or lookup.
DO $roles$
DECLARE role_name text; t record; f record;
BEGIN
    FOREACH role_name IN ARRAY ARRAY['agent_dev_crud', 'agent_dev_lookup', 'agent_dev_reader'] LOOP
        IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = role_name) THEN
            EXECUTE format('CREATE ROLE %I NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS', role_name);
        ELSIF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = role_name AND NOT rolsuper AND NOT rolcreatedb
            AND NOT rolcreaterole AND NOT rolreplication AND NOT rolbypassrls AND NOT rolcanlogin) THEN
            RAISE EXCEPTION 'Existing experimental role has unexpected privileges';
        END IF;
    END LOOP;
    GRANT USAGE ON SCHEMA public TO agent_dev_crud, agent_dev_lookup, agent_dev_reader;
    FOR t IN SELECT tablename FROM pg_tables WHERE schemaname = 'public' AND tablename LIKE 'agent\_%' ESCAPE '\' LOOP
        EXECUTE format('REVOKE ALL ON public.%I FROM PUBLIC, agent_dev_lookup', t.tablename);
        EXECUTE format('GRANT SELECT, INSERT, UPDATE, DELETE ON public.%I TO agent_dev_crud', t.tablename);
        EXECUTE format('GRANT SELECT ON public.%I TO agent_dev_reader', t.tablename);
    END LOOP;
    FOR f IN SELECT p.oid::regprocedure AS signature, p.proname FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace
        WHERE n.nspname = 'public' AND p.proname LIKE 'agent\_%' ESCAPE '\'
    LOOP
        EXECUTE format('REVOKE ALL ON FUNCTION %s FROM PUBLIC, agent_dev_lookup', f.signature);
        EXECUTE format('GRANT EXECUTE ON FUNCTION %s TO agent_dev_crud, agent_dev_reader', f.signature);
        IF f.proname IN ('agent_search_private', 'agent_get_private_source', 'agent_search_corpus', 'agent_get_corpus_source') THEN
            EXECUTE format('ALTER FUNCTION %s OWNER TO agent_dev_reader', f.signature);
            EXECUTE format('GRANT EXECUTE ON FUNCTION %s TO agent_dev_lookup', f.signature);
        END IF;
    END LOOP;
END
$roles$;
