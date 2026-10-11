-- Platform: application role, tenants, users, refresh tokens, audit trail.
-- Runs as the database owner. The application connects as app_rw, which is subject to RLS.

do $$
begin
  if not exists (select from pg_roles where rolname = 'app_rw') then
    create role app_rw login password '${app_rw_password}';
  else
    alter role app_rw with login password '${app_rw_password}';
  end if;
end $$;

grant usage on schema public to app_rw;
alter default privileges in schema public grant select, insert, update, delete on tables to app_rw;
alter default privileges in schema public grant usage, select on sequences to app_rw;

create table tenant (
  id          uuid primary key,
  name        varchar(200) not null,
  created_at  timestamptz not null default now()
);

create table app_user (
  id             uuid primary key,
  tenant_id      uuid not null references tenant (id),
  email          varchar(320) not null,
  full_name      varchar(200) not null,
  password_hash  varchar(100),
  roles          varchar(200) not null default 'USER',
  active         boolean not null default true,
  version        int not null default 0,
  created_at     timestamptz not null default now(),
  updated_at     timestamptz not null default now(),
  created_by     uuid,
  updated_by     uuid
);
create unique index ux_app_user_email on app_user (lower(email));
create index ix_app_user_tenant on app_user (tenant_id);

create table refresh_token (
  id          uuid primary key,
  user_id     uuid not null references app_user (id) on delete cascade,
  family_id   uuid not null,
  token_hash  bytea not null unique,
  expires_at  timestamptz not null,
  revoked_at  timestamptz,
  created_at  timestamptz not null default now()
);
create index ix_refresh_token_family on refresh_token (family_id);

-- Audit: monthly range partitions, created/dropped by audit_maintain().
create table audit_event (
  id           uuid not null,
  tenant_id    uuid,
  actor_id     uuid,
  action       varchar(64) not null,
  entity_type  varchar(64),
  entity_id    varchar(64),
  details      jsonb,
  ip           varchar(64),
  created_at   timestamptz not null default now(),
  primary key (id, created_at)
) partition by range (created_at);
create index ix_audit_event_tenant_time on audit_event (tenant_id, created_at desc);
create index ix_audit_event_entity on audit_event (entity_type, entity_id);

alter table audit_event enable row level security;
alter table audit_event force row level security;
create policy tenant_isolation on audit_event
  using (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid)
  with check (tenant_id is null or tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid);

create or replace function audit_maintain(retention_months int) returns void
language plpgsql security definer set search_path = public as $$
declare
  m       date;
  part    text;
  cutoff  date := (date_trunc('month', now()) - make_interval(months => retention_months))::date;
  r       record;
begin
  for i in 0..2 loop
    m := (date_trunc('month', now()) + make_interval(months => i))::date;
    part := format('audit_event_%s', to_char(m, 'YYYYMM'));
    if to_regclass(part) is null then
      execute format('create table %I partition of audit_event for values from (%L) to (%L)',
                     part, m, (m + interval '1 month')::date);
    end if;
  end loop;
  for r in
    select c.relname
    from pg_inherits i
    join pg_class c on c.oid = i.inhrelid
    join pg_class p on p.oid = i.inhparent
    where p.relname = 'audit_event'
  loop
    if to_date(right(r.relname, 6), 'YYYYMM') < cutoff then
      execute format('drop table %I', r.relname);
    end if;
  end loop;
end $$;

revoke all on function audit_maintain(int) from public;
grant execute on function audit_maintain(int) to app_rw;
select audit_maintain(3);
