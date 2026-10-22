-- Cluster-local disposable fixture only; never load this into the HTTP process.
CREATE ROLE app_owner LOGIN PASSWORD 'owner-fixture' NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
CREATE ROLE app_runtime LOGIN PASSWORD 'runtime-fixture' NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS NOINHERIT;
REVOKE ALL ON DATABASE you_story_issue9_test FROM PUBLIC;
REVOKE CREATE, TEMP ON DATABASE you_story_issue9_test FROM app_runtime;
GRANT CONNECT ON DATABASE you_story_issue9_test TO app_owner, app_runtime;
GRANT CREATE ON DATABASE you_story_issue9_test TO app_owner;
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
COMMENT ON DATABASE you_story_issue9_test IS 'codex-issue9-disposable-fixture-2026-10-22';
