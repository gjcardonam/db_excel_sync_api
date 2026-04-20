CREATE TABLE IF NOT EXISTS access_grants (
    id               bigserial PRIMARY KEY,
    created_at       timestamptz NOT NULL DEFAULT now(),
    source           varchar(32) NOT NULL,
    source_ref       varchar(128),
    granted_by_name  varchar(255),
    granted_by_email varchar(255),
    granted_by_id    varchar(128),
    user_email       varchar(255) NOT NULL,
    company          varchar(128) NOT NULL,
    status           varchar(32)  NOT NULL DEFAULT 'simulated',
    simulated        boolean      NOT NULL DEFAULT true,
    grafana_user_id  varchar(128),
    raw_message      text,
    notes            text
);

CREATE INDEX IF NOT EXISTS idx_access_grants_created_at
    ON access_grants (created_at DESC);

CREATE INDEX IF NOT EXISTS idx_access_grants_user_email
    ON access_grants (user_email);

CREATE INDEX IF NOT EXISTS idx_access_grants_company
    ON access_grants (company);

CREATE TABLE IF NOT EXISTS clickup_webhook_events (
    id          bigserial PRIMARY KEY,
    received_at timestamptz NOT NULL DEFAULT now(),
    source_ip   varchar(64),
    event_name  varchar(128),
    headers     jsonb NOT NULL,
    payload     jsonb NOT NULL,
    processed   boolean NOT NULL DEFAULT false,
    error       text
);

CREATE INDEX IF NOT EXISTS idx_clickup_webhook_events_received_at
    ON clickup_webhook_events (received_at DESC);
