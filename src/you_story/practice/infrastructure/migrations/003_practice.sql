CREATE SCHEMA practice AUTHORIZATION app_owner;
REVOKE ALL ON SCHEMA practice FROM PUBLIC;
GRANT USAGE ON SCHEMA practice TO app_runtime;
CREATE FUNCTION practice.immutable_columns() RETURNS trigger LANGUAGE plpgsql SET search_path = pg_catalog AS $$
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
REVOKE ALL ON FUNCTION practice.immutable_columns() FROM PUBLIC;
CREATE TABLE practice."session" (tenant_id uuid NOT NULL, id uuid PRIMARY KEY, started_at timestamptz, ended_at timestamptz, local_date date NOT NULL, time_zone text NOT NULL, notes text NOT NULL, status text NOT NULL, created_at timestamptz NOT NULL DEFAULT pg_catalog.now(), updated_at timestamptz NOT NULL DEFAULT pg_catalog.now(), version bigint NOT NULL DEFAULT 1 CHECK (version > 0), UNIQUE (tenant_id,id));
ALTER TABLE practice."session" ENABLE ROW LEVEL SECURITY;
ALTER TABLE practice."session" FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON practice."session" FOR ALL TO app_runtime USING (tenant_id = identity.current_tenant_id()) WITH CHECK (tenant_id = identity.current_tenant_id());
CREATE TRIGGER immutable_ownership BEFORE UPDATE ON practice."session" FOR EACH ROW EXECUTE FUNCTION practice.immutable_columns('tenant_id','id');
GRANT SELECT, INSERT, UPDATE, DELETE ON practice."session" TO app_runtime;
CREATE TABLE practice."record" (tenant_id uuid NOT NULL, id uuid PRIMARY KEY, session_id uuid NOT NULL, catalog_entry_id uuid NOT NULL, duration_seconds numeric CHECK (duration_seconds >= 0), notes text NOT NULL, FOREIGN KEY (tenant_id,session_id) REFERENCES practice.session(tenant_id,id), created_at timestamptz NOT NULL DEFAULT pg_catalog.now(), updated_at timestamptz NOT NULL DEFAULT pg_catalog.now(), version bigint NOT NULL DEFAULT 1 CHECK (version > 0), UNIQUE (tenant_id,id));
ALTER TABLE practice."record" ENABLE ROW LEVEL SECURITY;
ALTER TABLE practice."record" FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON practice."record" FOR ALL TO app_runtime USING (tenant_id = identity.current_tenant_id()) WITH CHECK (tenant_id = identity.current_tenant_id());
CREATE TRIGGER immutable_ownership BEFORE UPDATE ON practice."record" FOR EACH ROW EXECUTE FUNCTION practice.immutable_columns('tenant_id','id', 'session_id', 'catalog_entry_id');
GRANT SELECT, INSERT, UPDATE, DELETE ON practice."record" TO app_runtime;
CREATE TABLE practice."content_snapshot" (tenant_id uuid NOT NULL, id uuid PRIMARY KEY, record_id uuid NOT NULL, schema_version bigint NOT NULL CHECK (schema_version > 0), content jsonb NOT NULL CHECK (pg_catalog.jsonb_typeof(content) = 'object'), FOREIGN KEY (tenant_id,record_id) REFERENCES practice.record(tenant_id,id), UNIQUE (tenant_id,record_id), created_at timestamptz NOT NULL DEFAULT pg_catalog.now(), UNIQUE (tenant_id,id));
ALTER TABLE practice."content_snapshot" ENABLE ROW LEVEL SECURITY;
ALTER TABLE practice."content_snapshot" FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON practice."content_snapshot" FOR ALL TO app_runtime USING (tenant_id = identity.current_tenant_id()) WITH CHECK (tenant_id = identity.current_tenant_id());
CREATE TRIGGER immutable_ownership BEFORE UPDATE ON practice."content_snapshot" FOR EACH ROW EXECUTE FUNCTION practice.immutable_columns('tenant_id','id');
GRANT SELECT, INSERT ON practice."content_snapshot" TO app_runtime;
CREATE FUNCTION practice.immutable_snapshot() RETURNS trigger LANGUAGE plpgsql SET search_path = pg_catalog AS $$
BEGIN RAISE EXCEPTION 'immutable snapshot' USING ERRCODE = '42501'; END;
$$;
REVOKE ALL ON FUNCTION practice.immutable_snapshot() FROM PUBLIC;
CREATE TRIGGER immutable_snapshot BEFORE UPDATE OR DELETE ON practice.content_snapshot FOR EACH ROW EXECUTE FUNCTION practice.immutable_snapshot();
