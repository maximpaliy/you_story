-- Universal storage invariants and immutable, version-dispatched source policy.
INSERT INTO catalog.source(id,key,name) VALUES ('10000000-0000-4000-8000-000000000001','yousician','Yousician');
INSERT INTO catalog.instrument(id,key,name) VALUES
 ('20000000-0000-4000-8000-000000000001','guitar','Guitar'),
 ('20000000-0000-4000-8000-000000000002','piano','Piano');
INSERT INTO catalog.source_definition(id,source_id,definition_version,definition) VALUES
 ('30000000-0000-4000-8000-000000000001','10000000-0000-4000-8000-000000000001',1,
 '{"max_depth":3,"types":["song","version","fragment"],"parent_rules":[{"parent_type":null,"child_type":"song"},{"parent_type":"song","child_type":"version"},{"parent_type":"version","child_type":"fragment"}],"practiceable_types":["version","fragment"],"metadata_rules":[{"entry_type":"song","fields":[{"key":"author","kind":"text","nullable":true,"required_on_create":false,"required_on_replace":true,"min":1,"max":200,"default":null}]},{"entry_type":"version","fields":[{"key":"level","kind":"integer","nullable":false,"required_on_create":true,"required_on_replace":true,"min":0,"max":15,"default":null}]},{"entry_type":"fragment","fields":[{"key":"length_seconds","kind":"integer","nullable":true,"required_on_create":false,"required_on_replace":true,"min":1,"max":2147483647,"default":null},{"key":"notes_count","kind":"integer","nullable":false,"required_on_create":false,"required_on_replace":true,"min":0,"max":2147483647,"default":0}]}]}'::jsonb);
CREATE FUNCTION catalog.protect_definition() RETURNS trigger LANGUAGE plpgsql SET search_path=pg_catalog AS $$
BEGIN RAISE EXCEPTION 'published definition immutable' USING ERRCODE='23514'; END;
$$;
REVOKE ALL ON FUNCTION catalog.protect_definition() FROM PUBLIC;
CREATE TRIGGER immutable_published_definition BEFORE UPDATE OR DELETE ON catalog.source_definition FOR EACH ROW EXECUTE FUNCTION catalog.protect_definition();
CREATE TRIGGER immutable_entry_scope BEFORE UPDATE ON catalog.entry FOR EACH ROW EXECUTE FUNCTION catalog.immutable_columns('catalog_id','instrument_id','entry_type');
CREATE FUNCTION catalog.validate_entry() RETURNS trigger LANGUAGE plpgsql SET search_path=pg_catalog,catalog AS $$
DECLARE policy jsonb; fields jsonb; field jsonb; value jsonb; parent_type text; parent_state text;
        cursor_id uuid; next_id uuid; depth integer := 1; maximum integer; key_name text;
BEGIN
  -- This actor-scoped lock also serializes direct runtime SQL against public commands.
  PERFORM 1 FROM catalog.catalog WHERE tenant_id=NEW.tenant_id AND id=NEW.catalog_id FOR UPDATE;
  IF NOT FOUND THEN RAISE EXCEPTION 'catalog unavailable' USING ERRCODE='23514'; END IF;
  IF TG_OP='UPDATE' AND OLD.lifecycle_state <> 'active' THEN
    RAISE EXCEPTION 'terminal entry' USING ERRCODE='23514';
  END IF;
  IF NEW.name <> normalize(NEW.name,NFC) OR NEW.name <> btrim(NEW.name, E' \t\n\r\f\v\u0085\u00a0\u1680\u2000\u2001\u2002\u2003\u2004\u2005\u2006\u2007\u2008\u2009\u200a\u2028\u2029\u202f\u205f\u3000\u001c\u001d\u001e\u001f') OR char_length(NEW.name) NOT BETWEEN 1 AND 200 THEN
    RAISE EXCEPTION 'invalid name' USING ERRCODE='23514';
  END IF;
  SELECT definition INTO policy FROM catalog.source_definition WHERE id=NEW.source_definition_id AND source_id=NEW.source_id;
  maximum := (policy->>'max_depth')::integer;
  IF policy IS NULL OR maximum IS NULL OR maximum NOT BETWEEN 1 AND 16 OR NOT (policy->'types' ? NEW.entry_type) THEN
    RAISE EXCEPTION 'invalid definition' USING ERRCODE='23514';
  END IF;
  IF NEW.parent_entry_id IS NOT NULL THEN
    SELECT entry_type,lifecycle_state INTO parent_type,parent_state FROM catalog.entry
      WHERE tenant_id=NEW.tenant_id AND id=NEW.parent_entry_id AND catalog_id=NEW.catalog_id
      AND source_id=NEW.source_id AND source_definition_id=NEW.source_definition_id AND instrument_id=NEW.instrument_id;
    IF NOT FOUND OR parent_state <> 'active' THEN RAISE EXCEPTION 'invalid parent' USING ERRCODE='23514'; END IF;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM jsonb_array_elements(policy->'parent_rules') rule
       WHERE rule->>'child_type'=NEW.entry_type AND rule->>'parent_type' IS NOT DISTINCT FROM parent_type) THEN
    RAISE EXCEPTION 'invalid edge' USING ERRCODE='23514';
  END IF;
  cursor_id := NEW.parent_entry_id;
  WHILE cursor_id IS NOT NULL LOOP
    IF cursor_id=NEW.id OR depth >= maximum THEN RAISE EXCEPTION 'invalid ancestry' USING ERRCODE='23514'; END IF;
    SELECT parent_entry_id INTO next_id FROM catalog.entry WHERE tenant_id=NEW.tenant_id AND id=cursor_id AND catalog_id=NEW.catalog_id;
    IF NOT FOUND THEN RAISE EXCEPTION 'invalid ancestry' USING ERRCODE='23514'; END IF;
    cursor_id := next_id; depth := depth+1;
  END LOOP;
  SELECT rule->'fields' INTO fields FROM jsonb_array_elements(policy->'metadata_rules') rule WHERE rule->>'entry_type'=NEW.entry_type;
  IF fields IS NULL OR jsonb_typeof(NEW.metadata) <> 'object' OR
    EXISTS (SELECT 1 FROM jsonb_object_keys(NEW.metadata) k WHERE NOT EXISTS
      (SELECT 1 FROM jsonb_array_elements(fields) f WHERE f->>'key'=k)) THEN
    RAISE EXCEPTION 'invalid metadata' USING ERRCODE='23514';
  END IF;
  FOR field IN SELECT jsonb_array_elements(fields) LOOP
    key_name:=field->>'key'; value:=NEW.metadata->key_name;
    IF value IS NULL THEN RAISE EXCEPTION 'missing metadata' USING ERRCODE='23514'; END IF;
    IF value='null'::jsonb THEN
      IF NOT (field->>'nullable')::boolean THEN RAISE EXCEPTION 'invalid null' USING ERRCODE='23514'; END IF;
    ELSIF field->>'kind'='integer' THEN
      IF jsonb_typeof(value)<>'number' OR value::text !~ '^-?[0-9]+$' THEN
        RAISE EXCEPTION 'invalid integer' USING ERRCODE='23514';
      END IF;
      IF (value::text)::numeric < (field->>'min')::numeric OR (value::text)::numeric > (field->>'max')::numeric THEN
        RAISE EXCEPTION 'invalid integer' USING ERRCODE='23514';
      END IF;
    ELSIF field->>'kind'='text' THEN
      IF jsonb_typeof(value)<>'string' OR (value#>>'{}') <> normalize(value#>>'{}',NFC) OR
        (value#>>'{}') <> btrim(value#>>'{}', E' \t\n\r\f\v\u0085\u00a0\u1680\u2000\u2001\u2002\u2003\u2004\u2005\u2006\u2007\u2008\u2009\u200a\u2028\u2029\u202f\u205f\u3000\u001c\u001d\u001e\u001f') OR char_length(value#>>'{}') < (field->>'min')::integer OR
        char_length(value#>>'{}') > (field->>'max')::integer THEN
        RAISE EXCEPTION 'invalid text' USING ERRCODE='23514';
      END IF;
    ELSE RAISE EXCEPTION 'unknown metadata kind' USING ERRCODE='23514'; END IF;
  END LOOP;
  IF NEW.lifecycle_state='tombstone' AND EXISTS (SELECT 1 FROM catalog.entry WHERE tenant_id=NEW.tenant_id AND parent_entry_id=NEW.id AND lifecycle_state='active') THEN
    RAISE EXCEPTION 'active children' USING ERRCODE='23514';
  END IF;
  RETURN NEW;
END;
$$;
REVOKE ALL ON FUNCTION catalog.validate_entry() FROM PUBLIC;
CREATE TRIGGER validate_entry BEFORE INSERT OR UPDATE ON catalog.entry FOR EACH ROW EXECUTE FUNCTION catalog.validate_entry();
CREATE INDEX entry_tenant_name_id ON catalog.entry(tenant_id,name COLLATE "C",id) WHERE lifecycle_state='active';
CREATE INDEX entry_tenant_parent_order ON catalog.entry(tenant_id,parent_entry_id,created_at,id);
