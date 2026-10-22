CREATE SCHEMA catalog AUTHORIZATION app_owner;
REVOKE ALL ON SCHEMA catalog FROM PUBLIC;
GRANT USAGE ON SCHEMA catalog TO app_runtime;
CREATE FUNCTION catalog.immutable_columns() RETURNS trigger LANGUAGE plpgsql SET search_path = pg_catalog AS $$
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
REVOKE ALL ON FUNCTION catalog.immutable_columns() FROM PUBLIC;
CREATE TABLE catalog."source" (id uuid PRIMARY KEY, key text NOT NULL UNIQUE, name text NOT NULL, created_at timestamptz NOT NULL DEFAULT pg_catalog.now());
GRANT SELECT ON catalog."source" TO app_runtime;
CREATE TABLE catalog."instrument" (id uuid PRIMARY KEY, key text NOT NULL UNIQUE, name text NOT NULL, created_at timestamptz NOT NULL DEFAULT pg_catalog.now());
GRANT SELECT ON catalog."instrument" TO app_runtime;
CREATE TABLE catalog."source_definition" (id uuid PRIMARY KEY, source_id uuid NOT NULL REFERENCES catalog.source(id), definition_version bigint NOT NULL CHECK (definition_version > 0), definition jsonb NOT NULL CHECK (pg_catalog.jsonb_typeof(definition) = 'object'), UNIQUE (source_id,definition_version), UNIQUE (id,source_id), created_at timestamptz NOT NULL DEFAULT pg_catalog.now());
GRANT SELECT ON catalog."source_definition" TO app_runtime;
CREATE TABLE catalog."catalog" (tenant_id uuid NOT NULL, id uuid PRIMARY KEY, visibility text NOT NULL CHECK (visibility = 'personal'), UNIQUE (tenant_id), created_at timestamptz NOT NULL DEFAULT pg_catalog.now(), updated_at timestamptz NOT NULL DEFAULT pg_catalog.now(), version bigint NOT NULL DEFAULT 1 CHECK (version > 0), UNIQUE (tenant_id,id));
ALTER TABLE catalog."catalog" ENABLE ROW LEVEL SECURITY;
ALTER TABLE catalog."catalog" FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON catalog."catalog" FOR ALL TO app_runtime USING (tenant_id = identity.current_tenant_id()) WITH CHECK (tenant_id = identity.current_tenant_id());
CREATE TRIGGER immutable_ownership BEFORE UPDATE ON catalog."catalog" FOR EACH ROW EXECUTE FUNCTION catalog.immutable_columns('tenant_id','id');
GRANT SELECT, INSERT, UPDATE, DELETE ON catalog."catalog" TO app_runtime;
CREATE TABLE catalog."catalog_grant" (tenant_id uuid NOT NULL, id uuid PRIMARY KEY, catalog_id uuid NOT NULL, grantee_tenant_id uuid NOT NULL CHECK (grantee_tenant_id = tenant_id), role text NOT NULL CHECK (role = 'owner'), FOREIGN KEY (tenant_id,catalog_id) REFERENCES catalog.catalog(tenant_id,id), UNIQUE (tenant_id,catalog_id), created_at timestamptz NOT NULL DEFAULT pg_catalog.now(), updated_at timestamptz NOT NULL DEFAULT pg_catalog.now(), version bigint NOT NULL DEFAULT 1 CHECK (version > 0), UNIQUE (tenant_id,id));
ALTER TABLE catalog."catalog_grant" ENABLE ROW LEVEL SECURITY;
ALTER TABLE catalog."catalog_grant" FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON catalog."catalog_grant" FOR ALL TO app_runtime USING (tenant_id = identity.current_tenant_id()) WITH CHECK (tenant_id = identity.current_tenant_id());
CREATE TRIGGER immutable_ownership BEFORE UPDATE ON catalog."catalog_grant" FOR EACH ROW EXECUTE FUNCTION catalog.immutable_columns('tenant_id','id', 'catalog_id', 'grantee_tenant_id', 'role');
GRANT SELECT, INSERT, UPDATE, DELETE ON catalog."catalog_grant" TO app_runtime;
CREATE TABLE catalog."entry" (tenant_id uuid NOT NULL, id uuid PRIMARY KEY, catalog_id uuid NOT NULL, source_id uuid NOT NULL, source_definition_id uuid NOT NULL, instrument_id uuid NOT NULL REFERENCES catalog.instrument(id), parent_entry_id uuid, entry_type text NOT NULL, name text NOT NULL, metadata jsonb NOT NULL CHECK (pg_catalog.jsonb_typeof(metadata) = 'object'), lifecycle_state text NOT NULL CHECK (lifecycle_state IN ('active','tombstone')), FOREIGN KEY (tenant_id,catalog_id) REFERENCES catalog.catalog(tenant_id,id), FOREIGN KEY (source_definition_id,source_id) REFERENCES catalog.source_definition(id,source_id), UNIQUE (tenant_id,id,catalog_id,source_id,source_definition_id,instrument_id), FOREIGN KEY (tenant_id,parent_entry_id,catalog_id,source_id,source_definition_id,instrument_id) REFERENCES catalog.entry(tenant_id,id,catalog_id,source_id,source_definition_id,instrument_id), CHECK (parent_entry_id IS DISTINCT FROM id), created_at timestamptz NOT NULL DEFAULT pg_catalog.now(), updated_at timestamptz NOT NULL DEFAULT pg_catalog.now(), version bigint NOT NULL DEFAULT 1 CHECK (version > 0), UNIQUE (tenant_id,id));
ALTER TABLE catalog."entry" ENABLE ROW LEVEL SECURITY;
ALTER TABLE catalog."entry" FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON catalog."entry" FOR ALL TO app_runtime USING (tenant_id = identity.current_tenant_id()) WITH CHECK (tenant_id = identity.current_tenant_id());
CREATE TRIGGER immutable_ownership BEFORE UPDATE ON catalog."entry" FOR EACH ROW EXECUTE FUNCTION catalog.immutable_columns('tenant_id','id', 'source_id', 'source_definition_id');
GRANT SELECT, INSERT, UPDATE, DELETE ON catalog."entry" TO app_runtime;
