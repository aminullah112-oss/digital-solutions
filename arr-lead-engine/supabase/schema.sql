-- ARR Lead Engine V11 — Supabase schema.
-- Run once in the Supabase SQL editor. Then Authentication > Users > Add user
-- (email + password) and turn OFF "Allow new users to sign up" so only you can log in.
--
-- Model: one row per lead; the whole lead (activities included) lives in `data`.
-- Every row is private to its owner via RLS (owner = auth.uid()). No policy grants
-- anything to `anon`, so the publishable key alone can read nothing.

create table if not exists public.leads (
  id         text primary key,
  owner      uuid not null default auth.uid() references auth.users(id) on delete cascade,
  data       jsonb not null,
  updated_at timestamptz not null default now()
);

create index if not exists leads_owner_updated_idx on public.leads (owner, updated_at);

alter table public.leads enable row level security;

drop policy if exists "owner select" on public.leads;
drop policy if exists "owner insert" on public.leads;
drop policy if exists "owner update" on public.leads;
drop policy if exists "owner delete" on public.leads;

create policy "owner select" on public.leads for select to authenticated using (owner = auth.uid());
create policy "owner insert" on public.leads for insert to authenticated with check (owner = auth.uid());
create policy "owner update" on public.leads for update to authenticated using (owner = auth.uid()) with check (owner = auth.uid());
create policy "owner delete" on public.leads for delete to authenticated using (owner = auth.uid());

revoke all on public.leads from anon;
