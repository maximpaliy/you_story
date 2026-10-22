-- ADR-011 identity-only schema/function foundation. No existing-row backfill.
ALTER TABLE identity.invitation ADD COLUMN admission_kind text;
ALTER TABLE identity.invitation ADD COLUMN permitted_subject text;
ALTER TABLE identity.invitation ADD CONSTRAINT invitation_admission_kind_check
  CHECK (admission_kind IS NULL OR admission_kind IN ('bearer','allowlist'));
ALTER TABLE identity.invitation ADD CONSTRAINT invitation_subject_binding_check CHECK (
  CASE WHEN admission_kind = 'allowlist' THEN
    permitted_subject IS NOT NULL AND pg_catalog.octet_length(permitted_subject) BETWEEN 1 AND 255
    AND pg_catalog.octet_length(permitted_subject) = pg_catalog.char_length(permitted_subject)
    AND issuer = 'https://accounts.google.com' AND pg_catalog.octet_length(token_digest) = 32
  ELSE permitted_subject IS NULL END
);
CREATE UNIQUE INDEX invitation_pending_allowlist_idx ON identity.invitation(issuer,permitted_subject)
  WHERE admission_kind = 'allowlist' AND consumed_at IS NULL;
ALTER TABLE identity.external_identity ADD CONSTRAINT external_identity_id_user_unique UNIQUE(id,user_id);
ALTER TABLE identity.login_session ADD COLUMN external_identity_id uuid;
ALTER TABLE identity.login_session ADD COLUMN csrf_digest bytea;
ALTER TABLE identity.login_session ADD CONSTRAINT session_csrf_digest_check
  CHECK (csrf_digest IS NULL OR pg_catalog.octet_length(csrf_digest) = 32);
ALTER TABLE identity.login_session ADD CONSTRAINT session_external_identity_user_fk
  FOREIGN KEY (external_identity_id,user_id) REFERENCES identity.external_identity(id,user_id);
CREATE INDEX session_active_user_idx ON identity.login_session(user_id,created_at,id)
  WHERE revoked_at IS NULL;
CREATE TABLE identity.login_transaction (
  id uuid PRIMARY KEY,
  state_digest bytea NOT NULL UNIQUE CHECK (pg_catalog.octet_length(state_digest) = 32),
  nonce_digest bytea NOT NULL CHECK (pg_catalog.octet_length(nonce_digest) = 32),
  binder_digest bytea NOT NULL CHECK (pg_catalog.octet_length(binder_digest) = 32),
  pkce_challenge text NOT NULL CHECK (pkce_challenge ~ '^[A-Za-z0-9_-]{43}$'),
  encrypted_verifier bytea CHECK (pg_catalog.octet_length(encrypted_verifier) BETWEEN 1 AND 4096),
  client_config_id text NOT NULL CHECK (client_config_id = 'google-web'),
  invitation_digest bytea CHECK (pg_catalog.octet_length(invitation_digest) = 32),
  destination text NOT NULL CHECK (destination IN ('home','calendar','catalog')),
  status text NOT NULL CHECK (status IN ('pending','claimed','succeeded','failed','expired','invalidated')),
  created_at timestamptz NOT NULL,
  expires_at timestamptz NOT NULL,
  claimed_at timestamptz,
  CHECK (expires_at > created_at AND expires_at <= created_at + interval '600 seconds'),
  CHECK ((status = 'pending' AND encrypted_verifier IS NOT NULL AND claimed_at IS NULL)
     OR (status <> 'pending' AND encrypted_verifier IS NULL)),
  CHECK (status NOT IN ('claimed','succeeded','failed') OR claimed_at IS NOT NULL)
);
CREATE INDEX login_transaction_binder_idx ON identity.login_transaction(binder_digest,status,expires_at);
CREATE INDEX login_transaction_cleanup_idx ON identity.login_transaction(expires_at,id);
CREATE INDEX login_transaction_pending_cleanup_idx ON identity.login_transaction(expires_at,id)
  WHERE status IN ('pending','claimed');
CREATE TABLE identity.auth_rate_limit (
  scope text NOT NULL CHECK (scope IN ('IP-start','IP-callback','binder-start','invitation-attempt',
    'user-issuance','__transaction_capacity','__counter_capacity')),
  subject_digest bytea NOT NULL CHECK (pg_catalog.octet_length(subject_digest) = 32),
  window_start timestamptz NOT NULL,
  count bigint NOT NULL CHECK (count >= 0),
  expires_at timestamptz NOT NULL,
  PRIMARY KEY (scope,subject_digest,window_start),
  CHECK (CASE scope
    WHEN '__transaction_capacity' THEN count <= 100000
    WHEN '__counter_capacity' THEN count BETWEEN 2 AND 200000
    WHEN 'binder-start' THEN count <= 6
    WHEN 'IP-start' THEN count <= 21
    WHEN 'IP-callback' THEN count <= 21
    ELSE count <= 11 END),
  CHECK (scope NOT IN ('__transaction_capacity','__counter_capacity') OR
    (subject_digest = pg_catalog.decode(pg_catalog.repeat('00',32),'hex')
      AND window_start = '1970-01-01 00:00:00+00'::timestamptz AND expires_at = 'infinity'::timestamptz))
);
CREATE INDEX auth_rate_limit_cleanup_idx ON identity.auth_rate_limit(expires_at,scope,subject_digest,window_start)
  WHERE scope NOT IN ('__transaction_capacity','__counter_capacity');
-- Reviewed initialization of a newly-created empty technical control table only.
INSERT INTO identity.auth_rate_limit(scope,subject_digest,window_start,count,expires_at) VALUES
 ('__transaction_capacity',pg_catalog.decode(pg_catalog.repeat('00',32),'hex'),'1970-01-01 00:00:00+00',0,'infinity'),
 ('__counter_capacity',pg_catalog.decode(pg_catalog.repeat('00',32),'hex'),'1970-01-01 00:00:00+00',2,'infinity');
REVOKE ALL ON identity.login_transaction, identity.auth_rate_limit FROM PUBLIC, app_runtime;

CREATE FUNCTION identity._auth_now() RETURNS timestamptz
  LANGUAGE sql VOLATILE SET search_path = pg_catalog, identity
  AS $$ SELECT pg_catalog.clock_timestamp() $$;
CREATE FUNCTION identity._auth_digest(p_value bytea) RETURNS boolean
  LANGUAGE sql IMMUTABLE SET search_path = pg_catalog, identity
  AS $$ SELECT p_value IS NOT NULL AND pg_catalog.octet_length(p_value) = 32 $$;
CREATE FUNCTION identity._auth_lock() RETURNS timestamptz
  LANGUAGE plpgsql VOLATILE SET search_path = pg_catalog, identity AS $$
BEGIN
  PERFORM pg_catalog.set_config('lock_timeout','2000',true);
  PERFORM pg_catalog.set_config('statement_timeout','5000',true);
  PERFORM pg_catalog.pg_advisory_xact_lock(7923462011::bigint);
  RETURN identity._auth_now();
END;
$$;
CREATE FUNCTION identity._auth_cleanup(p_now timestamptz) RETURNS void
  LANGUAGE plpgsql VOLATILE SET search_path = pg_catalog, identity AS $$
DECLARE v_row record; v_deleted bigint := 0; v_counters bigint := 0;
BEGIN
  -- Each indexed branch contributes at most 100; at most 100 rows are processed.
  FOR v_row IN
    SELECT candidates.id,candidates.expires_at FROM (
      (SELECT tx.id,tx.expires_at FROM identity.login_transaction tx
        WHERE tx.expires_at <= p_now - interval '86400 seconds'
        ORDER BY tx.expires_at,tx.id LIMIT 100)
      UNION
      (SELECT tx.id,tx.expires_at FROM identity.login_transaction tx
        WHERE tx.status IN ('pending','claimed') AND tx.expires_at <= p_now
        ORDER BY tx.expires_at,tx.id LIMIT 100)
    ) candidates ORDER BY candidates.expires_at,candidates.id LIMIT 100
  LOOP
    IF v_row.expires_at <= p_now - interval '86400 seconds' THEN
      DELETE FROM identity.login_transaction tx WHERE tx.id = v_row.id;
      v_deleted := v_deleted + 1;
    ELSE
      UPDATE identity.login_transaction tx SET status = 'expired',encrypted_verifier = NULL
        WHERE tx.id = v_row.id AND tx.status IN ('pending','claimed');
    END IF;
  END LOOP;
  WITH eligible AS (
    SELECT rl.scope,rl.subject_digest,rl.window_start FROM identity.auth_rate_limit rl
      WHERE rl.scope NOT IN ('__transaction_capacity','__counter_capacity') AND rl.expires_at <= p_now
      ORDER BY rl.expires_at,rl.scope,rl.subject_digest,rl.window_start LIMIT 100
  ), removed AS (
    DELETE FROM identity.auth_rate_limit rl USING eligible e
      WHERE (rl.scope,rl.subject_digest,rl.window_start) = (e.scope,e.subject_digest,e.window_start)
      RETURNING 1
  ) SELECT pg_catalog.count(*) INTO v_counters FROM removed;
  UPDATE identity.auth_rate_limit rl SET count = rl.count - v_deleted
    WHERE rl.scope = '__transaction_capacity';
  UPDATE identity.auth_rate_limit rl SET count = rl.count - v_counters
    WHERE rl.scope = '__counter_capacity';
END;
$$;
CREATE FUNCTION identity._auth_consume(p_scope text,p_subject bytea,p_now timestamptz)
  RETURNS TABLE(allowed boolean,window_end timestamptz)
  LANGUAGE plpgsql VOLATILE SET search_path = pg_catalog, identity AS $$
DECLARE v_limit bigint; v_seconds integer; v_start timestamptz; v_end timestamptz;
  v_count bigint; v_capacity bigint; v_fresh timestamptz; v_new_start timestamptz; v_exists boolean;
BEGIN
  IF NOT identity._auth_digest(p_subject) THEN
    RAISE EXCEPTION 'invalid authentication limit input' USING ERRCODE = '22023';
  END IF;
  CASE p_scope
    WHEN 'IP-start' THEN v_limit := 20; v_seconds := 600;
    WHEN 'IP-callback' THEN v_limit := 20; v_seconds := 600;
    WHEN 'binder-start' THEN v_limit := 5; v_seconds := 600;
    WHEN 'invitation-attempt' THEN v_limit := 10; v_seconds := 3600;
    WHEN 'user-issuance' THEN v_limit := 10; v_seconds := 600;
    ELSE RAISE EXCEPTION 'invalid authentication limit input' USING ERRCODE = '22023';
  END CASE;
  v_start := pg_catalog.to_timestamp(pg_catalog.floor(extract(epoch FROM p_now) / v_seconds) * v_seconds);
  LOOP
    SELECT rl.count INTO v_count FROM identity.auth_rate_limit rl
      WHERE rl.scope = p_scope AND rl.subject_digest = p_subject AND rl.window_start = v_start FOR UPDATE;
    v_exists := FOUND;
    IF NOT v_exists THEN
      SELECT rl.count INTO v_capacity FROM identity.auth_rate_limit rl
        WHERE rl.scope = '__counter_capacity' FOR UPDATE;
    END IF;
    -- A row/capacity wait must not charge a stale fixed window.
    v_fresh := identity._auth_now();
    v_new_start := pg_catalog.to_timestamp(pg_catalog.floor(extract(epoch FROM v_fresh) / v_seconds) * v_seconds);
    IF v_new_start <> v_start THEN v_start := v_new_start; CONTINUE; END IF;
    v_end := v_start + pg_catalog.make_interval(secs => v_seconds);
    IF NOT v_exists THEN
      IF v_capacity IS NULL OR v_capacity >= 200000 THEN
        RAISE EXCEPTION 'authentication capacity unavailable' USING ERRCODE = '53300';
      END IF;
      INSERT INTO identity.auth_rate_limit(scope,subject_digest,window_start,count,expires_at)
        VALUES(p_scope,p_subject,v_start,1,v_end + interval '86400 seconds');
      UPDATE identity.auth_rate_limit rl SET count = rl.count + 1 WHERE rl.scope = '__counter_capacity';
      v_count := 1;
    ELSE
      v_count := least(v_count + 1,v_limit + 1);
      UPDATE identity.auth_rate_limit rl SET count = v_count
        WHERE rl.scope = p_scope AND rl.subject_digest = p_subject AND rl.window_start = v_start;
    END IF;
    RETURN QUERY SELECT v_count <= v_limit,v_end;
    RETURN;
  END LOOP;
END;
$$;

CREATE FUNCTION identity.consume_auth_limit(p_scope text,p_subject bytea)
  RETURNS TABLE(allowed boolean,window_end timestamptz)
  LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, identity AS $$
DECLARE v_now timestamptz;
BEGIN
  v_now := identity._auth_lock();
  IF p_scope IN ('IP-start','IP-callback') AND identity._auth_digest(p_subject) THEN
    PERFORM identity._auth_cleanup(v_now);
  END IF;
  RETURN QUERY SELECT r.allowed,r.window_end FROM identity._auth_consume(p_scope,p_subject,v_now) r;
EXCEPTION WHEN invalid_parameter_value OR insufficient_resources THEN RETURN;
END;
$$;

CREATE FUNCTION identity.start_web_login(p_id uuid,p_binder bytea,p_state bytea,p_nonce bytea,
  p_challenge text,p_cipher bytea,p_config text,p_invitation bytea,p_destination text,p_binder_expiry timestamptz)
  RETURNS TABLE(result text,id uuid,expires_at timestamptz)
  LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, identity AS $$
DECLARE v_now timestamptz; v_capacity bigint;
BEGIN
  v_now := identity._auth_lock();
  IF p_id IS NULL OR NOT identity._auth_digest(p_binder) OR NOT identity._auth_digest(p_state)
    OR NOT identity._auth_digest(p_nonce) OR p_challenge IS NULL
    OR p_challenge !~ '^[A-Za-z0-9_-]{43}$' OR p_cipher IS NULL
    OR pg_catalog.octet_length(p_cipher) NOT BETWEEN 1 AND 4096
    OR p_config IS DISTINCT FROM 'google-web' OR p_destination IS NULL
    OR p_destination NOT IN ('home','calendar','catalog')
    OR (p_invitation IS NOT NULL AND NOT identity._auth_digest(p_invitation))
    OR p_binder_expiry IS NULL OR p_binder_expiry <= v_now
    OR NOT pg_catalog.isfinite(p_binder_expiry)
  THEN RETURN QUERY SELECT 'invalid'::text,NULL::uuid,NULL::timestamptz; RETURN; END IF;
  IF EXISTS(SELECT 1 FROM identity.login_transaction tx WHERE tx.id = p_id OR tx.state_digest = p_state) THEN
    RETURN QUERY SELECT 'invalid'::text,NULL::uuid,NULL::timestamptz; RETURN;
  END IF;
  IF EXISTS(SELECT 1 FROM identity.login_transaction tx WHERE tx.binder_digest = p_binder
    AND tx.status IN ('claimed','succeeded') AND tx.expires_at > v_now) THEN
    RETURN QUERY SELECT 'in_progress'::text,NULL::uuid,NULL::timestamptz; RETURN;
  END IF;
  SELECT rl.count INTO v_capacity FROM identity.auth_rate_limit rl
    WHERE rl.scope = '__transaction_capacity' FOR UPDATE;
  IF v_capacity IS NULL OR v_capacity >= 100000 THEN
    RETURN QUERY SELECT 'unavailable'::text,NULL::uuid,NULL::timestamptz; RETURN;
  END IF;
  UPDATE identity.login_transaction tx SET status = 'invalidated',encrypted_verifier = NULL
    WHERE tx.binder_digest = p_binder AND tx.status = 'pending';
  v_now := identity._auth_now();
  IF p_binder_expiry <= v_now THEN
    RAISE EXCEPTION 'authentication authority expired' USING ERRCODE = 'YA002';
  END IF;
  INSERT INTO identity.login_transaction(id,state_digest,nonce_digest,binder_digest,pkce_challenge,
    encrypted_verifier,client_config_id,invitation_digest,destination,status,created_at,expires_at)
    VALUES(p_id,p_state,p_nonce,p_binder,p_challenge,p_cipher,p_config,p_invitation,p_destination,
      'pending',v_now,least(v_now + interval '600 seconds',p_binder_expiry));
  UPDATE identity.auth_rate_limit rl SET count = rl.count + 1 WHERE rl.scope = '__transaction_capacity';
  RETURN QUERY SELECT 'ok'::text,tx.id,tx.expires_at FROM identity.login_transaction tx WHERE tx.id = p_id;
EXCEPTION WHEN unique_violation OR foreign_key_violation OR check_violation OR SQLSTATE 'YA002' THEN
  RETURN QUERY SELECT 'invalid'::text,NULL::uuid,NULL::timestamptz;
END;
$$;

CREATE FUNCTION identity.claim_web_login(p_state bytea,p_binder bytea,p_config text)
  RETURNS TABLE(id uuid,nonce_digest bytea,encrypted_verifier bytea,pkce_challenge text,
    client_config_id text,invitation_digest bytea,destination text)
  LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, identity AS $$
DECLARE v_now timestamptz; v_tx identity.login_transaction%ROWTYPE;
BEGIN
  v_now := identity._auth_lock();
  IF NOT identity._auth_digest(p_state) OR NOT identity._auth_digest(p_binder)
    OR p_config IS DISTINCT FROM 'google-web' THEN RETURN; END IF;
  SELECT tx.* INTO v_tx FROM identity.login_transaction tx
    WHERE tx.state_digest = p_state AND tx.binder_digest = p_binder
      AND tx.client_config_id = p_config AND tx.status = 'pending' AND tx.expires_at > v_now FOR UPDATE;
  IF NOT FOUND THEN RETURN; END IF;
  v_now := identity._auth_now();
  IF v_tx.expires_at <= v_now THEN RETURN; END IF;
  UPDATE identity.login_transaction tx SET status = 'claimed',claimed_at = v_now,encrypted_verifier = NULL
    WHERE tx.id = v_tx.id;
  RETURN QUERY SELECT v_tx.id,v_tx.nonce_digest,v_tx.encrypted_verifier,v_tx.pkce_challenge,
    v_tx.client_config_id,v_tx.invitation_digest,v_tx.destination;
END;
$$;
CREATE FUNCTION identity.fail_web_login(p_id uuid,p_binder bytea) RETURNS boolean
  LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, identity AS $$
DECLARE v_now timestamptz;
BEGIN
  v_now := identity._auth_lock();
  IF p_id IS NULL OR NOT identity._auth_digest(p_binder) THEN RETURN false; END IF;
  UPDATE identity.login_transaction tx SET status = 'failed',encrypted_verifier = NULL
    WHERE tx.id = p_id AND tx.binder_digest = p_binder AND tx.status = 'claimed';
  RETURN FOUND;
END;
$$;

CREATE FUNCTION identity.finish_web_login(p_id uuid,p_binder bytea,p_issuer text,p_subject text,
  p_session_id uuid,p_session_digest bytea,p_csrf_digest bytea)
  RETURNS TABLE(result text,user_id uuid,tenant_id uuid,session_id uuid,provisioning_state text,
    absolute_expires_at timestamptz,window_end timestamptz)
  LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, identity AS $$
DECLARE v_now timestamptz; v_tx identity.login_transaction%ROWTYPE;
  v_identity identity.external_identity%ROWTYPE; v_admission identity.invitation%ROWTYPE;
  v_user_id uuid; v_tenant_id uuid; v_identity_id uuid; v_state text; v_provisioning text;
  v_limit record; v_count bigint; v_old uuid; v_has_identity boolean;
BEGIN
  v_now := identity._auth_lock();
  IF p_id IS NULL OR p_session_id IS NULL OR NOT identity._auth_digest(p_binder)
    OR NOT identity._auth_digest(p_session_digest) OR NOT identity._auth_digest(p_csrf_digest)
    OR p_issuer IS DISTINCT FROM 'https://accounts.google.com' OR p_subject IS NULL
    OR pg_catalog.octet_length(p_subject) NOT BETWEEN 1 AND 255
    OR pg_catalog.octet_length(p_subject) <> pg_catalog.char_length(p_subject)
  THEN RETURN QUERY SELECT 'invalid'::text,NULL::uuid,NULL::uuid,NULL::uuid,NULL::text,
    NULL::timestamptz,NULL::timestamptz; RETURN; END IF;
  SELECT tx.* INTO v_tx FROM identity.login_transaction tx WHERE tx.id = p_id
    AND tx.binder_digest = p_binder AND tx.status = 'claimed' AND tx.expires_at > v_now FOR UPDATE;
  IF NOT FOUND THEN
    RETURN QUERY SELECT 'invalid'::text,NULL::uuid,NULL::uuid,NULL::uuid,NULL::text,
      NULL::timestamptz,NULL::timestamptz; RETURN;
  END IF;
  SELECT ei.* INTO v_identity FROM identity.external_identity ei
    WHERE ei.provider = p_issuer AND ei.subject = p_subject FOR UPDATE;
  v_has_identity := FOUND;
  IF v_has_identity THEN
    SELECT u.id,t.id,t.provisioning_state INTO v_user_id,v_tenant_id,v_provisioning
      FROM identity."user" u JOIN identity.tenant t ON t.owner_user_id = u.id
      WHERE u.id = v_identity.user_id AND u.state = 'active' AND t.state = 'active'
        AND v_identity.state = 'active' FOR UPDATE OF u,t;
    IF NOT FOUND THEN
      RETURN QUERY SELECT 'invalid'::text,NULL::uuid,NULL::uuid,NULL::uuid,NULL::text,
        NULL::timestamptz,NULL::timestamptz; RETURN;
    END IF;
    v_now := identity._auth_now();
    SELECT t.provisioning_state INTO v_provisioning FROM identity.external_identity ei
      JOIN identity."user" u ON u.id = ei.user_id JOIN identity.tenant t ON t.owner_user_id = u.id
      WHERE ei.id = v_identity.id AND ei.state = 'active' AND u.id = v_user_id
        AND t.id = v_tenant_id AND u.state = 'active' AND t.state = 'active';
    IF NOT FOUND OR v_tx.expires_at <= v_now THEN
      RETURN QUERY SELECT 'invalid'::text,NULL::uuid,NULL::uuid,NULL::uuid,NULL::text,
        NULL::timestamptz,NULL::timestamptz; RETURN;
    END IF;
    v_identity_id := v_identity.id;
  ELSE
    IF v_tx.invitation_digest IS NOT NULL THEN
      -- Bound bearer attempts consume only their own budget, even when eligibility fails.
      SELECT r.* INTO v_limit FROM identity._auth_consume('invitation-attempt',v_tx.invitation_digest,v_now) r;
      IF NOT v_limit.allowed THEN
        RETURN QUERY SELECT 'limited'::text,NULL::uuid,NULL::uuid,NULL::uuid,NULL::text,
          NULL::timestamptz,v_limit.window_end; RETURN;
      END IF;
      SELECT i.* INTO v_admission FROM identity.invitation i
        WHERE i.token_digest = v_tx.invitation_digest
          AND coalesce(i.admission_kind,'bearer') = 'bearer' FOR UPDATE;
    ELSE
      SELECT i.* INTO v_admission FROM identity.invitation i
        WHERE i.admission_kind = 'allowlist' AND i.issuer = p_issuer AND i.permitted_subject = p_subject
          AND i.consumed_at IS NULL AND i.expires_at > v_now FOR UPDATE;
    END IF;
    v_now := identity._auth_now();
    IF v_tx.expires_at <= v_now OR v_admission.id IS NULL OR v_admission.issuer <> p_issuer
      OR v_admission.expires_at <= v_now OR v_admission.consumed_at IS NOT NULL THEN
      RETURN QUERY SELECT 'invalid'::text,NULL::uuid,NULL::uuid,NULL::uuid,NULL::text,
        NULL::timestamptz,NULL::timestamptz; RETURN;
    END IF;
  END IF;
  -- Only this inner unit may create identity/session authority. Attempt budget above survives failure.
  BEGIN
    IF NOT v_has_identity THEN
      v_user_id := pg_catalog.gen_random_uuid(); v_tenant_id := pg_catalog.gen_random_uuid();
      v_identity_id := pg_catalog.gen_random_uuid(); v_provisioning := 'catalog_pending';
      INSERT INTO identity."user"(id,state,created_at,updated_at,version)
        VALUES(v_user_id,'active',v_now,v_now,1);
      INSERT INTO identity.tenant(id,owner_user_id,state,provisioning_state,created_at,updated_at,version)
        VALUES(v_tenant_id,v_user_id,'active','catalog_pending',v_now,v_now,1);
      INSERT INTO identity.external_identity(id,provider,subject,user_id,state,created_at,updated_at,version)
        VALUES(v_identity_id,p_issuer,p_subject,v_user_id,'active',v_now,v_now,1);
      UPDATE identity.invitation i SET consumed_at = v_now,consumed_provider = p_issuer,
        consumed_subject = p_subject,consumed_user_id = v_user_id,updated_at = v_now,version = i.version + 1
        WHERE i.id = v_admission.id;
    END IF;
    -- Lock existing candidate sessions before sampling final issuance time.
    PERFORM s.id FROM identity.login_session s WHERE s.user_id = v_user_id AND s.revoked_at IS NULL
      AND s.absolute_expires_at > v_now AND s.last_seen_at + interval '604800 seconds' > v_now
      ORDER BY s.created_at,s.id FOR UPDATE;
    v_now := identity._auth_now();
    IF v_tx.expires_at <= v_now THEN
      RAISE EXCEPTION 'authentication authority expired' USING ERRCODE = 'YA002';
    END IF;
    SELECT r.* INTO v_limit FROM identity._auth_consume('user-issuance',
      pg_catalog.sha256(pg_catalog.convert_to('you-story:auth-user:v1','UTF8')
        || pg_catalog.decode('00','hex') || pg_catalog.uuid_send(v_user_id)),v_now) r;
    v_now := identity._auth_now();
    IF v_tx.expires_at <= v_now OR (NOT v_has_identity AND v_admission.expires_at <= v_now) THEN
      RAISE EXCEPTION 'authentication authority expired' USING ERRCODE = 'YA002';
    END IF;
    IF NOT v_limit.allowed THEN
      IF NOT v_has_identity THEN
        RAISE EXCEPTION 'authentication issuance limited' USING ERRCODE = 'YA001';
      END IF;
      RETURN QUERY SELECT 'limited'::text,NULL::uuid,NULL::uuid,NULL::uuid,NULL::text,
        NULL::timestamptz,v_limit.window_end; RETURN;
    END IF;
    SELECT pg_catalog.count(*) INTO v_count FROM identity.login_session s
      JOIN identity.external_identity ei ON (ei.id,ei.user_id) = (s.external_identity_id,s.user_id)
      JOIN identity."user" u ON u.id = s.user_id
      JOIN identity.tenant t ON (t.id,t.owner_user_id) = (s.tenant_id,s.user_id)
      WHERE s.user_id = v_user_id AND s.revoked_at IS NULL AND s.csrf_digest IS NOT NULL
        AND ei.state = 'active' AND u.state = 'active' AND t.state = 'active'
        AND s.absolute_expires_at > v_now AND s.last_seen_at + interval '604800 seconds' > v_now;
    WHILE v_count >= 10 LOOP
      SELECT s.id INTO v_old FROM identity.login_session s
        JOIN identity.external_identity ei ON (ei.id,ei.user_id) = (s.external_identity_id,s.user_id)
        JOIN identity.tenant t ON (t.id,t.owner_user_id) = (s.tenant_id,s.user_id)
        WHERE s.user_id = v_user_id AND s.revoked_at IS NULL AND s.csrf_digest IS NOT NULL
          AND ei.state = 'active' AND t.state = 'active' AND s.absolute_expires_at > v_now
          AND s.last_seen_at + interval '604800 seconds' > v_now ORDER BY s.created_at,s.id LIMIT 1;
      UPDATE identity.login_session s SET revoked_at = v_now,updated_at = v_now,version = s.version + 1
        WHERE s.id = v_old;
      v_count := v_count - 1;
    END LOOP;
    INSERT INTO identity.login_session(id,token_digest,user_id,tenant_id,issued_at,last_seen_at,
      absolute_expires_at,external_identity_id,csrf_digest,created_at,updated_at,version)
      VALUES(p_session_id,p_session_digest,v_user_id,v_tenant_id,v_now,v_now,
        v_now + interval '2592000 seconds',v_identity_id,p_csrf_digest,v_now,v_now,1);
    UPDATE identity.login_transaction tx SET status = 'succeeded',encrypted_verifier = NULL WHERE tx.id = p_id;
    RETURN QUERY SELECT 'ok'::text,v_user_id,v_tenant_id,p_session_id,v_provisioning,
      v_now + interval '2592000 seconds',NULL::timestamptz;
  EXCEPTION WHEN SQLSTATE 'YA001' THEN
    RETURN QUERY SELECT 'limited'::text,NULL::uuid,NULL::uuid,NULL::uuid,NULL::text,
      NULL::timestamptz,v_limit.window_end;
  WHEN insufficient_resources THEN
    RETURN QUERY SELECT 'unavailable'::text,NULL::uuid,NULL::uuid,NULL::uuid,NULL::text,
      NULL::timestamptz,NULL::timestamptz;
  WHEN OTHERS THEN
    IF SQLSTATE IN ('57014','55P03') THEN RAISE; END IF;
    RETURN QUERY SELECT 'invalid'::text,NULL::uuid,NULL::uuid,NULL::uuid,NULL::text,
      NULL::timestamptz,NULL::timestamptz;
  END;
EXCEPTION WHEN insufficient_resources THEN
  RETURN QUERY SELECT 'unavailable'::text,NULL::uuid,NULL::uuid,NULL::uuid,NULL::text,
    NULL::timestamptz,NULL::timestamptz;
END;
$$;

CREATE FUNCTION identity.resolve_web_session(p_digest bytea)
  RETURNS TABLE(user_id uuid,tenant_id uuid,session_id uuid,provisioning_state text,absolute_expires_at timestamptz)
  LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, identity AS $$
DECLARE v_now timestamptz; v_session identity.login_session%ROWTYPE;
BEGIN
  v_now := identity._auth_lock();
  IF NOT identity._auth_digest(p_digest) THEN RETURN; END IF;
  SELECT s.* INTO v_session FROM identity.login_session s WHERE s.token_digest = p_digest;
  IF NOT FOUND OR v_session.external_identity_id IS NULL OR v_session.csrf_digest IS NULL THEN
    RETURN;
  END IF;
  -- Global runtime serialization plus explicit identity/user/tenant/session row-lock order.
  PERFORM ei.id FROM identity.external_identity ei WHERE ei.id = v_session.external_identity_id FOR UPDATE;
  PERFORM u.id FROM identity."user" u WHERE u.id = v_session.user_id FOR UPDATE;
  PERFORM t.id FROM identity.tenant t WHERE t.id = v_session.tenant_id FOR UPDATE;
  PERFORM s.id FROM identity.login_session s WHERE s.id = v_session.id FOR UPDATE;
  v_now := identity._auth_now();
  RETURN QUERY UPDATE identity.login_session s SET last_seen_at = greatest(s.last_seen_at,v_now),
    updated_at = v_now,version = s.version + 1
    FROM identity.external_identity ei,identity."user" u,identity.tenant t
    WHERE s.id = v_session.id AND s.token_digest = p_digest
      AND (s.user_id,s.tenant_id,s.external_identity_id) =
        (v_session.user_id,v_session.tenant_id,v_session.external_identity_id)
      AND s.external_identity_id = ei.id AND s.user_id = ei.user_id
      AND s.user_id = u.id AND (s.tenant_id,s.user_id) = (t.id,t.owner_user_id)
      AND s.csrf_digest IS NOT NULL AND s.revoked_at IS NULL
      AND ei.state = 'active' AND u.state = 'active' AND t.state = 'active'
      AND s.absolute_expires_at > v_now AND s.last_seen_at + interval '604800 seconds' > v_now
    RETURNING s.user_id,s.tenant_id,s.id,t.provisioning_state,s.absolute_expires_at;
END;
$$;
CREATE FUNCTION identity.revoke_web_session(p_digest bytea) RETURNS boolean
  LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, identity AS $$
DECLARE v_now timestamptz; v_session identity.login_session%ROWTYPE;
BEGIN
  v_now := identity._auth_lock();
  IF NOT identity._auth_digest(p_digest) THEN RETURN false; END IF;
  SELECT s.* INTO v_session FROM identity.login_session s WHERE s.token_digest = p_digest;
  IF NOT FOUND OR v_session.external_identity_id IS NULL OR v_session.csrf_digest IS NULL THEN
    RETURN false;
  END IF;
  -- Global runtime serialization plus explicit identity/user/tenant/session row-lock order.
  PERFORM ei.id FROM identity.external_identity ei WHERE ei.id = v_session.external_identity_id FOR UPDATE;
  PERFORM u.id FROM identity."user" u WHERE u.id = v_session.user_id FOR UPDATE;
  PERFORM t.id FROM identity.tenant t WHERE t.id = v_session.tenant_id FOR UPDATE;
  PERFORM s.id FROM identity.login_session s WHERE s.id = v_session.id FOR UPDATE;
  v_now := identity._auth_now();
  UPDATE identity.login_session s SET revoked_at = v_now,updated_at = v_now,version = s.version + 1
    FROM identity.external_identity ei,identity."user" u,identity.tenant t
    WHERE s.id = v_session.id AND s.token_digest = p_digest
      AND (s.user_id,s.tenant_id,s.external_identity_id) =
        (v_session.user_id,v_session.tenant_id,v_session.external_identity_id)
      AND s.external_identity_id = ei.id AND s.user_id = ei.user_id
      AND s.user_id = u.id AND (s.tenant_id,s.user_id) = (t.id,t.owner_user_id)
      AND s.csrf_digest IS NOT NULL AND s.revoked_at IS NULL
      AND ei.state = 'active' AND u.state = 'active' AND t.state = 'active'
      AND s.absolute_expires_at > v_now AND s.last_seen_at + interval '604800 seconds' > v_now
;
  RETURN FOUND;
END;
$$;
CREATE FUNCTION identity.mark_catalog_ready(p_digest bytea) RETURNS boolean
  LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, identity AS $$
DECLARE v_now timestamptz; v_session identity.login_session%ROWTYPE; v_tenant_id uuid;
BEGIN
  v_now := identity._auth_lock();
  IF NOT identity._auth_digest(p_digest) THEN RETURN false; END IF;
  SELECT s.* INTO v_session FROM identity.login_session s WHERE s.token_digest = p_digest;
  IF NOT FOUND OR v_session.external_identity_id IS NULL OR v_session.csrf_digest IS NULL THEN
    RETURN false;
  END IF;
  -- Global runtime serialization plus explicit identity/user/tenant/session row-lock order.
  PERFORM ei.id FROM identity.external_identity ei WHERE ei.id = v_session.external_identity_id FOR UPDATE;
  PERFORM u.id FROM identity."user" u WHERE u.id = v_session.user_id FOR UPDATE;
  PERFORM t.id FROM identity.tenant t WHERE t.id = v_session.tenant_id FOR UPDATE;
  PERFORM s.id FROM identity.login_session s WHERE s.id = v_session.id FOR UPDATE;
  v_now := identity._auth_now();
  SELECT t.id INTO v_tenant_id FROM identity.login_session s,
    identity.external_identity ei,identity."user" u,identity.tenant t
    WHERE s.id = v_session.id AND s.token_digest = p_digest
      AND (s.user_id,s.tenant_id,s.external_identity_id) =
        (v_session.user_id,v_session.tenant_id,v_session.external_identity_id)
      AND s.external_identity_id = ei.id AND s.user_id = ei.user_id
      AND s.user_id = u.id AND (s.tenant_id,s.user_id) = (t.id,t.owner_user_id)
      AND s.csrf_digest IS NOT NULL AND s.revoked_at IS NULL
      AND ei.state = 'active' AND u.state = 'active' AND t.state = 'active'
      AND s.absolute_expires_at > v_now AND s.last_seen_at + interval '604800 seconds' > v_now
;
  IF NOT FOUND THEN RETURN false; END IF;
  UPDATE identity.tenant t SET provisioning_state = 'ready',updated_at = v_now,version = t.version + 1
    WHERE t.id = v_tenant_id AND t.state = 'active' AND t.provisioning_state = 'catalog_pending';
  RETURN true;
END;
$$;

REVOKE ALL ON FUNCTION identity._auth_now(),identity._auth_digest(bytea),identity._auth_lock(),
 identity._auth_cleanup(timestamptz),identity._auth_consume(text,bytea,timestamptz) FROM PUBLIC,app_runtime;
REVOKE ALL ON FUNCTION identity.start_web_login(uuid,bytea,bytea,bytea,text,bytea,text,bytea,text,timestamptz),
 identity.claim_web_login(bytea,bytea,text),identity.fail_web_login(uuid,bytea),
 identity.finish_web_login(uuid,bytea,text,text,uuid,bytea,bytea),identity.resolve_web_session(bytea),
 identity.revoke_web_session(bytea),identity.consume_auth_limit(text,bytea),identity.mark_catalog_ready(bytea)
 FROM PUBLIC,app_runtime;
GRANT EXECUTE ON FUNCTION identity.start_web_login(uuid,bytea,bytea,bytea,text,bytea,text,bytea,text,timestamptz),
 identity.claim_web_login(bytea,bytea,text),identity.fail_web_login(uuid,bytea),
 identity.finish_web_login(uuid,bytea,text,text,uuid,bytea,bytea),identity.resolve_web_session(bytea),
 identity.revoke_web_session(bytea),identity.consume_auth_limit(text,bytea),identity.mark_catalog_ready(bytea)
 TO app_runtime;
