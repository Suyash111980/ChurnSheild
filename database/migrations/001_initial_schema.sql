-- ChurnShield initial schema for Supabase/PostgreSQL.
-- Learner-facing tables use RLS with no anonymous access policies by default.
-- Authenticate and authorize API requests before using the server-side service role.
create extension if not exists pgcrypto;

create table if not exists public.learners (
    id uuid primary key default gen_random_uuid(),
    id_student text not null,
    code_module text not null,
    code_presentation text not null,
    gender text,
    region text,
    highest_education text,
    imd_band text,
    age_band text,
    num_of_prev_attempts integer not null default 0 check (num_of_prev_attempts >= 0),
    studied_credits integer check (studied_credits is null or studied_credits >= 0),
    disability boolean,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint learners_student_course_presentation_unique unique (id_student, code_module, code_presentation)
);

create table if not exists public.learner_features (
    id uuid primary key default gen_random_uuid(),
    learner_id uuid not null references public.learners(id) on delete cascade,
    as_of_date date not null,
    features jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    constraint learner_features_learner_date_unique unique (learner_id, as_of_date)
);

create table if not exists public.predictions (
    id uuid primary key default gen_random_uuid(),
    learner_id uuid not null references public.learners(id) on delete cascade,
    model_version text not null,
    risk_probability numeric(6,5) not null check (risk_probability between 0 and 1),
    risk_category text not null check (risk_category in ('low', 'medium', 'high')),
    created_at timestamptz not null default now()
);

create table if not exists public.risk_explanations (
    id uuid primary key default gen_random_uuid(),
    prediction_id uuid not null references public.predictions(id) on delete cascade,
    feature_name text not null,
    feature_value jsonb,
    contribution numeric not null,
    created_at timestamptz not null default now(),
    constraint risk_explanations_prediction_feature_unique unique (prediction_id, feature_name)
);

create table if not exists public.recommendations (
    id uuid primary key default gen_random_uuid(),
    learner_id uuid not null references public.learners(id) on delete cascade,
    prediction_id uuid references public.predictions(id) on delete set null,
    action text not null,
    reason text not null,
    status text not null default 'pending' check (status in ('pending', 'in_progress', 'completed', 'dismissed')),
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists public.dataset_uploads (
    id uuid primary key default gen_random_uuid(),
    filename text not null,
    status text not null default 'uploaded' check (status in ('uploaded', 'processing', 'processed', 'failed')),
    uploaded_at timestamptz not null default now(),
    error_summary text
);

create table if not exists public.profiles (
    id uuid primary key references auth.users(id) on delete cascade,
    role text not null default 'educator' check (role in ('admin', 'educator', 'analyst')),
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create index if not exists learners_module_presentation_idx on public.learners (code_module, code_presentation);
create index if not exists learner_features_learner_date_idx on public.learner_features (learner_id, as_of_date desc);
create index if not exists predictions_risk_created_idx on public.predictions (risk_category, created_at desc);
create index if not exists predictions_learner_created_idx on public.predictions (learner_id, created_at desc);
create index if not exists risk_explanations_prediction_idx on public.risk_explanations (prediction_id);
create index if not exists recommendations_status_created_idx on public.recommendations (status, created_at desc);
create index if not exists recommendations_learner_idx on public.recommendations (learner_id);
create index if not exists dataset_uploads_status_idx on public.dataset_uploads (status, uploaded_at desc);

alter table public.learners enable row level security;
alter table public.learner_features enable row level security;
alter table public.predictions enable row level security;
alter table public.risk_explanations enable row level security;
alter table public.recommendations enable row level security;
alter table public.dataset_uploads enable row level security;
alter table public.profiles enable row level security;

-- Signed-in users can read only their profile; profile changes stay server-side.
create policy profiles_select_own on public.profiles
    for select to authenticated using (auth.uid() = id);
