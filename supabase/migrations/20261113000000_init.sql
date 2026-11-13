-- Suki backend: accounts (settings sync) and push subscriptions only.
-- Price data never touches the database; the app works fully without it.

-- ------------------------------------------------------------------ user settings
create table if not exists public.user_settings (
  user_id uuid primary key references auth.users (id) on delete cascade,
  settings jsonb not null,
  updated_at timestamptz not null default now()
);

alter table public.user_settings enable row level security;

-- A user can read and write only their own row.
create policy "own settings: select" on public.user_settings
  for select to authenticated using (user_id = auth.uid());
create policy "own settings: insert" on public.user_settings
  for insert to authenticated with check (user_id = auth.uid());
create policy "own settings: update" on public.user_settings
  for update to authenticated using (user_id = auth.uid()) with check (user_id = auth.uid());
create policy "own settings: delete" on public.user_settings
  for delete to authenticated using (user_id = auth.uid());

-- ------------------------------------------------------------------ push subscriptions
-- A subscription belongs to a device; no account is needed. user_id is set when the
-- device is signed in, so deleting the account also removes its subscriptions.
create table if not exists public.push_subscriptions (
  id uuid primary key default gen_random_uuid(),
  endpoint text not null unique,
  p256dh text not null,
  auth text not null,
  region text not null,
  tracked_ids text[] not null default '{}',
  language text not null default 'en' check (language in ('en', 'fil')),
  user_id uuid references auth.users (id) on delete cascade,
  created_at timestamptz not null default now(),
  last_ok_at timestamptz,
  -- report date of the last alert sent, so a rerun never sends twice for the same report
  last_notified_for date
);

create index if not exists push_subscriptions_region_idx on public.push_subscriptions (region);

-- No direct table access for browsers. The scraper uses the service role key, which bypasses RLS.
alter table public.push_subscriptions enable row level security;

-- The browser manages only the row matching its own endpoint. Knowing the endpoint and its
-- auth secret (both private to that browser's push subscription) proves ownership.
create or replace function public.upsert_push_subscription(
  p_endpoint text,
  p_p256dh text,
  p_auth text,
  p_region text,
  p_tracked_ids text[],
  p_language text
) returns void
language plpgsql
security definer
set search_path = public
as $$
declare
  existing public.push_subscriptions%rowtype;
begin
  if p_endpoint is null or p_endpoint !~ '^https://' or length(p_endpoint) > 1000 then
    raise exception 'invalid endpoint';
  end if;
  if coalesce(array_length(p_tracked_ids, 1), 0) > 500 then
    raise exception 'too many tracked items';
  end if;

  select * into existing from public.push_subscriptions where endpoint = p_endpoint;
  if found then
    if existing.auth <> p_auth then
      raise exception 'not your subscription';
    end if;
    update public.push_subscriptions
       set p256dh = p_p256dh,
           region = p_region,
           tracked_ids = coalesce(p_tracked_ids, '{}'),
           language = case when p_language in ('en', 'fil') then p_language else 'en' end,
           user_id = coalesce(auth.uid(), user_id)
     where id = existing.id;
  else
    insert into public.push_subscriptions (endpoint, p256dh, auth, region, tracked_ids, language, user_id)
    values (
      p_endpoint, p_p256dh, p_auth, p_region, coalesce(p_tracked_ids, '{}'),
      case when p_language in ('en', 'fil') then p_language else 'en' end,
      auth.uid()
    );
  end if;
end;
$$;

create or replace function public.delete_push_subscription(p_endpoint text, p_auth text)
returns void
language sql
security definer
set search_path = public
as $$
  delete from public.push_subscriptions where endpoint = p_endpoint and auth = p_auth;
$$;

revoke all on function public.upsert_push_subscription(text, text, text, text, text[], text) from public;
revoke all on function public.delete_push_subscription(text, text) from public;
grant execute on function public.upsert_push_subscription(text, text, text, text, text[], text) to anon, authenticated;
grant execute on function public.delete_push_subscription(text, text) to anon, authenticated;

-- ------------------------------------------------------------------ delete account
-- Removes the settings row, push subscriptions tied to the user, and the auth user.
create or replace function public.delete_my_account()
returns void
language plpgsql
security definer
set search_path = public, auth
as $$
declare
  uid uuid := auth.uid();
begin
  if uid is null then
    raise exception 'not signed in';
  end if;
  delete from public.push_subscriptions where user_id = uid;
  delete from public.user_settings where user_id = uid;
  delete from auth.users where id = uid;
end;
$$;

revoke all on function public.delete_my_account() from public;
grant execute on function public.delete_my_account() to authenticated;
