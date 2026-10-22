CREATE SCHEMA media AUTHORIZATION app_owner;
REVOKE ALL ON SCHEMA media FROM PUBLIC;
CREATE FUNCTION media.immutable_columns() RETURNS trigger LANGUAGE plpgsql SET search_path = pg_catalog AS $$
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
REVOKE ALL ON FUNCTION media.immutable_columns() FROM PUBLIC;
CREATE TABLE media."upload_intent" (tenant_id uuid NOT NULL, id uuid PRIMARY KEY, record_id uuid NOT NULL, object_key text NOT NULL UNIQUE, content_type text NOT NULL, size_bytes bigint CHECK (size_bytes >= 0), checksum text, state text NOT NULL, retention_state text NOT NULL, created_at timestamptz NOT NULL DEFAULT pg_catalog.now(), updated_at timestamptz NOT NULL DEFAULT pg_catalog.now(), version bigint NOT NULL DEFAULT 1 CHECK (version > 0), UNIQUE (tenant_id,id));
ALTER TABLE media."upload_intent" ENABLE ROW LEVEL SECURITY;
ALTER TABLE media."upload_intent" FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON media."upload_intent" FOR ALL TO app_runtime USING (tenant_id = identity.current_tenant_id()) WITH CHECK (tenant_id = identity.current_tenant_id());
CREATE TRIGGER immutable_ownership BEFORE UPDATE ON media."upload_intent" FOR EACH ROW EXECUTE FUNCTION media.immutable_columns('tenant_id','id');
CREATE TABLE media."attachment" (tenant_id uuid NOT NULL, id uuid PRIMARY KEY, upload_intent_id uuid NOT NULL, record_id uuid NOT NULL, object_key text NOT NULL UNIQUE, content_type text NOT NULL, size_bytes bigint CHECK (size_bytes >= 0), checksum text, state text NOT NULL, retention_state text NOT NULL, FOREIGN KEY (tenant_id,upload_intent_id) REFERENCES media.upload_intent(tenant_id,id), UNIQUE (tenant_id,upload_intent_id), created_at timestamptz NOT NULL DEFAULT pg_catalog.now(), updated_at timestamptz NOT NULL DEFAULT pg_catalog.now(), version bigint NOT NULL DEFAULT 1 CHECK (version > 0), UNIQUE (tenant_id,id));
ALTER TABLE media."attachment" ENABLE ROW LEVEL SECURITY;
ALTER TABLE media."attachment" FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON media."attachment" FOR ALL TO app_runtime USING (tenant_id = identity.current_tenant_id()) WITH CHECK (tenant_id = identity.current_tenant_id());
CREATE TRIGGER immutable_ownership BEFORE UPDATE ON media."attachment" FOR EACH ROW EXECUTE FUNCTION media.immutable_columns('tenant_id','id');
