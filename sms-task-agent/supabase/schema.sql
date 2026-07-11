-- SMS Screenshot Task Agent — Supabase schema
-- Run this in the Supabase SQL editor (or `supabase db push`).

-- Tasks captured from SMS screenshots.
create table if not exists tasks (
    id uuid primary key default gen_random_uuid(),
    screenshot_url text,
    extracted_text text,
    title text not null default 'Untitled task',
    assigned_list text not null default 'Inbox',
    due_date date,
    priority text check (priority in ('low', 'medium', 'high')),
    status text not null default 'open' check (status in ('open', 'done', 'archived')),
    -- How the list was chosen: 'explicit' (named in the SMS), 'auto' (model routed it),
    -- or 'corrected' (user overrode the model in the dashboard).
    routing_source text not null default 'auto' check (routing_source in ('explicit', 'auto', 'corrected')),
    confidence_score real check (confidence_score >= 0 and confidence_score <= 1),
    sms_body text,
    sender_phone text,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create index if not exists tasks_assigned_list_idx on tasks (assigned_list);
create index if not exists tasks_created_at_idx on tasks (created_at desc);

-- Training examples for the routing model. One row per (screenshot -> list) decision
-- the system can learn from: explicit SMS instructions and dashboard corrections
-- are ground truth; auto decisions are recorded but weighted lower.
create table if not exists routing_examples (
    id uuid primary key default gen_random_uuid(),
    task_id uuid references tasks (id) on delete cascade,
    summary text not null,          -- short description of the screenshot content
    keywords text[] not null default '{}',
    assigned_list text not null,
    source text not null check (source in ('explicit', 'correction', 'auto_confirmed')),
    created_at timestamptz not null default now()
);

create index if not exists routing_examples_list_idx on routing_examples (assigned_list);
create index if not exists routing_examples_created_at_idx on routing_examples (created_at desc);

-- Keep updated_at fresh on task edits.
create or replace function set_updated_at() returns trigger as $$
begin
    new.updated_at = now();
    return new;
end;
$$ language plpgsql;

drop trigger if exists tasks_set_updated_at on tasks;
create trigger tasks_set_updated_at
    before update on tasks
    for each row execute function set_updated_at();

-- Storage bucket for screenshots (private; backend serves signed URLs).
insert into storage.buckets (id, name, public)
values ('screenshots', 'screenshots', false)
on conflict (id) do nothing;

-- Row level security: the backend uses the service-role key, which bypasses RLS.
-- Enable RLS so the anon key can't read anything directly.
alter table tasks enable row level security;
alter table routing_examples enable row level security;
