CREATE TRIGGER trg_change_requests_environment_insert
BEFORE INSERT ON change_requests
FOR EACH ROW
WHEN NEW.environment NOT IN ('local', 'development', 'staging', 'production')
     OR NOT EXISTS (
    SELECT 1
    FROM workspaces
    WHERE id = NEW.workspace_id AND environment = NEW.environment
)
BEGIN
    SELECT RAISE(ABORT, 'change request environment must match workspace');
END;

CREATE TRIGGER trg_change_requests_environment_update
BEFORE UPDATE OF workspace_id, environment ON change_requests
FOR EACH ROW
WHEN NEW.environment NOT IN ('local', 'development', 'staging', 'production')
     OR NOT EXISTS (
    SELECT 1
    FROM workspaces
    WHERE id = NEW.workspace_id AND environment = NEW.environment
)
BEGIN
    SELECT RAISE(ABORT, 'change request environment must match workspace');
END;

CREATE TRIGGER trg_workspaces_environment_insert_valid
BEFORE INSERT ON workspaces
FOR EACH ROW
WHEN NEW.environment NOT IN ('local', 'development', 'staging', 'production')
BEGIN
    SELECT RAISE(ABORT, 'workspace environment is invalid');
END;

CREATE TRIGGER trg_workspaces_environment_update_valid
BEFORE UPDATE OF environment ON workspaces
FOR EACH ROW
WHEN NEW.environment NOT IN ('local', 'development', 'staging', 'production')
BEGIN
    SELECT RAISE(ABORT, 'workspace environment is invalid');
END;

CREATE TRIGGER trg_change_requests_environment_immutable
BEFORE UPDATE OF workspace_id, environment ON change_requests
FOR EACH ROW
WHEN OLD.status <> 'DRAFT'
BEGIN
    SELECT RAISE(ABORT, 'submitted change request environment is immutable');
END;

CREATE TRIGGER trg_workspaces_environment_immutable
BEFORE UPDATE OF environment ON workspaces
FOR EACH ROW
WHEN OLD.environment IS NOT NEW.environment
     AND EXISTS (SELECT 1 FROM change_requests WHERE workspace_id = OLD.id)
BEGIN
    SELECT RAISE(ABORT, 'workspace environment is immutable after first change request');
END;

CREATE TRIGGER trg_executions_environment_insert
BEFORE INSERT ON executions
FOR EACH ROW
WHEN EXISTS (
    SELECT 1
    FROM change_requests cr
    JOIN workspaces w ON w.id = cr.workspace_id
    WHERE cr.id = NEW.request_id
      AND (
          cr.environment NOT IN ('local', 'development', 'staging', 'production')
          OR cr.environment IS NOT w.environment
      )
)
BEGIN
    SELECT RAISE(ABORT, 'execution environment does not match workspace');
END;
