CREATE SCHEMA identity AUTHORIZATION app_owner;
REVOKE ALL ON SCHEMA identity FROM PUBLIC;
GRANT USAGE ON SCHEMA identity TO app_runtime;
CREATE FUNCTION identity.immutable_columns() RETURNS trigger LANGUAGE plpgsql SET search_path = pg_catalog AS $$
DECLARE column_name text;
BEGIN
  FOREACH column_name IN ARRAY TG_ARGV LOOP
    IF pg_catalog.to_jsonb(OLD) -> column_name IS DISTINCT FROM pg_catalog.to_jsonb(NEW) -> column_name THEN
      RAISE EXCEPTION 'immutable ownership' USING ERRCODE = '42501';
    END IF;
  END LOOP;
  RETURN NEW;
END;
$$;
REVOKE ALL ON FUNCTION identity.immutable_columns() FROM PUBLIC;
CREATE FUNCTION identity.current_tenant_id() RETURNS uuid LANGUAGE plpgsql STABLE SET search_path = pg_catalog, identity AS $$
DECLARE raw_value text;
BEGIN
 raw_value := pg_catalog.current_setting('app.tenant_id', true);
 IF raw_value IS NULL OR raw_value = '' OR raw_value !~ '^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$' THEN
   RAISE EXCEPTION 'tenant context invalid' USING ERRCODE = '42501';
 END IF;
 RETURN raw_value::pg_catalog.uuid;
END;
$$;
REVOKE ALL ON FUNCTION identity.current_tenant_id() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION identity.current_tenant_id() TO app_runtime;
CREATE TABLE identity."user" (id uuid PRIMARY KEY, state text NOT NULL CHECK (state IN ('active','disabled')), created_at timestamptz NOT NULL DEFAULT pg_catalog.now(), updated_at timestamptz NOT NULL DEFAULT pg_catalog.now(), version bigint NOT NULL DEFAULT 1 CHECK (version > 0));
CREATE TABLE identity."tenant" (id uuid PRIMARY KEY, owner_user_id uuid NOT NULL UNIQUE REFERENCES identity."user"(id), state text NOT NULL CHECK (state IN ('active','disabled')), provisioning_state text NOT NULL CHECK (provisioning_state IN ('catalog_pending','ready')), UNIQUE (id, owner_user_id), created_at timestamptz NOT NULL DEFAULT pg_catalog.now(), updated_at timestamptz NOT NULL DEFAULT pg_catalog.now(), version bigint NOT NULL DEFAULT 1 CHECK (version > 0));
CREATE TABLE identity."external_identity" (id uuid PRIMARY KEY, provider text NOT NULL, subject text NOT NULL, user_id uuid NOT NULL REFERENCES identity."user"(id), state text NOT NULL CHECK (state IN ('active','disabled')), UNIQUE (provider,subject), created_at timestamptz NOT NULL DEFAULT pg_catalog.now(), updated_at timestamptz NOT NULL DEFAULT pg_catalog.now(), version bigint NOT NULL DEFAULT 1 CHECK (version > 0));
CREATE TABLE identity."invitation" (id uuid PRIMARY KEY, token_digest bytea NOT NULL UNIQUE, issuer text NOT NULL, expires_at timestamptz NOT NULL, consumed_at timestamptz, consumed_provider text, consumed_subject text, consumed_user_id uuid REFERENCES identity."user"(id), CHECK ((consumed_at IS NULL AND consumed_provider IS NULL AND consumed_subject IS NULL AND consumed_user_id IS NULL) OR (consumed_at IS NOT NULL AND consumed_provider IS NOT NULL AND consumed_subject IS NOT NULL AND consumed_user_id IS NOT NULL)), created_at timestamptz NOT NULL DEFAULT pg_catalog.now(), updated_at timestamptz NOT NULL DEFAULT pg_catalog.now(), version bigint NOT NULL DEFAULT 1 CHECK (version > 0));
CREATE TABLE identity."login_session" (id uuid PRIMARY KEY, token_digest bytea NOT NULL UNIQUE, user_id uuid NOT NULL REFERENCES identity."user"(id), tenant_id uuid NOT NULL, issued_at timestamptz NOT NULL, last_seen_at timestamptz NOT NULL, absolute_expires_at timestamptz NOT NULL, revoked_at timestamptz, FOREIGN KEY (tenant_id,user_id) REFERENCES identity.tenant(id,owner_user_id), created_at timestamptz NOT NULL DEFAULT pg_catalog.now(), updated_at timestamptz NOT NULL DEFAULT pg_catalog.now(), version bigint NOT NULL DEFAULT 1 CHECK (version > 0));
CREATE TABLE identity."user_preference" (tenant_id uuid NOT NULL, id uuid PRIMARY KEY, user_id uuid NOT NULL, settings jsonb NOT NULL CHECK (pg_catalog.jsonb_typeof(settings) = 'object'), UNIQUE (tenant_id,user_id), created_at timestamptz NOT NULL DEFAULT pg_catalog.now(), updated_at timestamptz NOT NULL DEFAULT pg_catalog.now(), version bigint NOT NULL DEFAULT 1 CHECK (version > 0), UNIQUE (tenant_id,id));
ALTER TABLE identity."user_preference" ENABLE ROW LEVEL SECURITY;
ALTER TABLE identity."user_preference" FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON identity."user_preference" FOR ALL TO app_runtime USING (tenant_id = identity.current_tenant_id()) WITH CHECK (tenant_id = identity.current_tenant_id());
CREATE TRIGGER immutable_ownership BEFORE UPDATE ON identity."user_preference" FOR EACH ROW EXECUTE FUNCTION identity.immutable_columns('tenant_id','id', 'user_id');
GRANT SELECT, INSERT, UPDATE, DELETE ON identity."user_preference" TO app_runtime;
