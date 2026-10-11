-- Reference feature "note": the tenant-table template (copy for new features).
create table note (
  id          uuid primary key,
  tenant_id   uuid not null references tenant (id),
  owner_id    uuid not null references app_user (id),
  title       varchar(200) not null,
  content     text,
  version     int not null default 0,
  created_at  timestamptz not null default now(),
  updated_at  timestamptz not null default now(),
  created_by  uuid,
  updated_by  uuid
);
create index ix_note_tenant_created on note (tenant_id, created_at desc);

alter table note enable row level security;
alter table note force row level security;
create policy tenant_isolation on note
  using (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid)
  with check (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid);
