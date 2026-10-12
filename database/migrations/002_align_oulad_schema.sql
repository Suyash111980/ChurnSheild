
-- ChurnShield migration 002
-- Align the existing learners table with OULAD.
-- Preserve existing UUIDs and the id_student source identifier column.

begin;

create extension if not exists pgcrypto;

-- 1. Add OULAD learner profile fields without dropping existing columns.
alter table public.learners
    add column if not exists gender text,
    add column if not exists region text,
    add column if not exists highest_education text,
    add column if not exists imd_band text,
    add column if not exists age_band text,
    add column if not exists num_of_prev_attempts integer not null default 0,
    add column if not exists studied_credits integer,
    add column if not exists disability boolean,
    add column if not exists updated_at timestamptz not null default now();

-- Keep the existing unique constraint:
-- (id_student, code_module, code_presentation)

-- 2. Learner features recorded at a prediction cutoff date.
create table if not exists public.learner_features (
    id uuid primary key default gen_random_uuid(),
    learner_id uuid not null
        references public.learners(id) on delete cascade,
    as_of_date date not null,
    features jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    constraint learner_features_learner_date_unique
        unique (learner_id, as_of_date)
);

-- 3. Model predictions.
create table if not exists public.predictions (
    id uuid primary key default gen_random_uuid(),
    learner_id uuid not null
        references public.learners(id) on delete cascade,
    model_version text not null,
    risk_probability numeric(6,5) not null
        check (risk_probability between 0 and 1),
    risk_category text not null
        check (risk_category in ('low', 'medium', 'high')),
    created_at timestamptz not null default now()
);

-- 4. Explanations for individual predictions.
create table if not exists public.risk_explanations (
    id uuid primary key default gen_random_uuid(),
    prediction_id uuid not null
        references public.predictions(id) on delete cascade,
    feature_name text not null,
    feature_value jsonb,
    contribution numeric not null,
    created_at timestamptz not null default now(),
    constraint risk_explanations_prediction_feature_unique
        unique (prediction_id, feature_name)
);

-- 5. Retention recommendations and their workflow status.
create table if not exists public.recommendations (
    id uuid primary key default gen_random_uuid(),
    learner_id uuid not null
        references public.learners(id) on delete cascade,
    prediction_id uuid
        references public.predictions(id) on delete set null,
    action text not null,
    reason text not null,
    status text not null default 'pending'
        check (status in (
            'pending', 'in_progress', 'completed', 'dismissed'
        )),
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

-- 6. Dataset upload and processing history.
create table if not exists public.dataset_uploads (
    id uuid primary key default gen_random_uuid(),
    filename text not null,
    status text not null default 'uploaded'
        check (status in (
            'uploaded', 'processing', 'processed', 'failed'
        )),
    uploaded_at timestamptz not null default now(),
    error_summary text
);

-- 7. User profiles linked to Supabase Auth.
create table if not exists public.profiles (
    id uuid primary key
        references auth.users(id) on delete cascade,
    role text not null default 'educator'
        check (role in ('admin', 'educator', 'analyst')),
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

-- 8. Indexes for common dashboard queries.
create index if not exists learners_module_presentation_idx
    on public.learners (code_module, code_presentation);

create index if not exists learner_features_learner_date_idx
    on public.learner_features (learner_id, as_of_date desc);

create index if not exists predictions_risk_created_idx
    on public.predictions (risk_category, created_at desc);

create index if not exists predictions_learner_created_idx
    on public.predictions (learner_id, created_at desc);

create index if not exists risk_explanations_prediction_idx
    on public.risk_explanations (prediction_id);

create index if not exists recommendations_status_created_idx
    on public.recommendations (status, created_at desc);

create index if not exists recommendations_learner_idx
    on public.recommendations (learner_id);

create index if not exists dataset_uploads_status_idx
    on public.dataset_uploads (status, uploaded_at desc);

-- 9. Enable row-level security.
alter table public.learners enable row level security;
alter table public.learner_features enable row level security;
alter table public.predictions enable row level security;
alter table public.risk_explanations enable row level security;
alter table public.recommendations enable row level security;
alter table public.dataset_uploads enable row level security;
alter table public.profiles enable row level security;

-- Only users may read their own profile.
-- The conditional prevents errors if this policy already exists.
do $$
begin
    if not exists (
        select 1
        from pg_policies
        where schemaname = 'public'
          and tablename = 'profiles'
          and policyname = 'profiles_select_own'
    ) then
        create policy profiles_select_own
            on public.profiles
            for select
            to authenticated
            using (auth.uid() = id);
    end if;
end
$$;

commit;
