-- ChurnShield Phase 3: private, owner-scoped dataset records.
-- Apply only after reviewing migration 004 and this migration together.
-- Existing uploads and learners remain unowned (owner_id/dataset_id NULL);
-- ownership is intentionally not guessed or backfilled here.

begin;

-- Fail with actionable diagnostics before altering a pre-existing schema.
-- IF NOT EXISTS below is for replay tolerance, not schema reconciliation.
do $$
declare
    dataset_name_type text;
    owner_id_type text;
    owner_id_nullable text;
    dataset_id_type text;
    dataset_id_nullable text;
    dataset_uploads_oid oid := to_regclass('public.dataset_uploads');
    learners_oid oid := to_regclass('public.learners');
    auth_users_oid oid := to_regclass('auth.users');
    invalid_dataset_name boolean;
    has_external_id boolean;
    has_legacy_id boolean;
    source_identifier_column text;
    duplicate_source_groups boolean;
begin
    if to_regclass('public.dataset_uploads') is null
       or to_regclass('public.learners') is null
       or to_regclass('public.learner_features') is null
       or to_regclass('public.predictions') is null
       or to_regclass('public.risk_explanations') is null
       or to_regclass('public.recommendations') is null
       or to_regclass('public.profiles') is null
       or to_regclass('auth.users') is null then
        raise exception 'Migration 005 requires migrations 001-003 and the Supabase Auth schema';
    end if;

    if not exists (
        select 1 from information_schema.columns
        where table_schema = 'public' and table_name = 'dataset_uploads'
          and column_name = 'id' and data_type = 'uuid' and is_nullable = 'NO'
    ) or not exists (
        select 1 from information_schema.columns
        where table_schema = 'public' and table_name = 'dataset_uploads'
          and column_name = 'filename' and data_type in ('text', 'character varying')
          and is_nullable = 'NO'
    ) or not exists (
        select 1 from information_schema.columns
        where table_schema = 'public' and table_name = 'dataset_uploads'
          and column_name = 'status' and data_type in ('text', 'character varying')
          and is_nullable = 'NO'
    ) or not exists (
        select 1 from information_schema.columns
        where table_schema = 'public' and table_name = 'dataset_uploads'
          and column_name = 'uploaded_at' and data_type = 'timestamp with time zone'
          and is_nullable = 'NO'
    ) then
        raise exception 'Migration 005 requires dataset_uploads.id uuid, non-null text filename/status, and non-null timestamptz uploaded_at';
    end if;

    if not exists (
        select 1 from information_schema.columns
        where table_schema = 'public' and table_name = 'profiles'
          and column_name = 'id' and data_type = 'uuid' and is_nullable = 'NO'
    ) or not exists (
        select 1 from information_schema.columns
        where table_schema = 'public' and table_name = 'profiles'
          and column_name = 'role' and data_type in ('text', 'character varying')
    ) or not exists (
        select 1 from information_schema.columns
        where table_schema = 'public' and table_name = 'profiles'
          and column_name = 'approval_status' and data_type in ('text', 'character varying')
    ) then
        raise exception 'Migration 005 requires the profiles approval schema from migration 003';
    end if;

    select exists (
        select 1 from information_schema.columns
        where table_schema = 'public' and table_name = 'learners'
          and column_name = 'external_learner_id'
    ), exists (
        select 1 from information_schema.columns
        where table_schema = 'public' and table_name = 'learners'
          and column_name = 'id_student'
    ) into has_external_id, has_legacy_id;
    if has_external_id = has_legacy_id then
        raise exception 'Migration 005 requires exactly one learner source-id column; manually reconcile external_learner_id/id_student';
    end if;
    source_identifier_column := case when has_external_id
        then 'external_learner_id' else 'id_student' end;
    if not exists (
        select 1 from information_schema.columns
        where table_schema = 'public' and table_name = 'learners'
          and column_name = source_identifier_column
          and data_type in ('text', 'character varying') and is_nullable = 'NO'
    ) or (
        select count(*) from information_schema.columns
        where table_schema = 'public' and table_name = 'learners'
          and column_name in ('code_module', 'code_presentation')
          and data_type in ('text', 'character varying') and is_nullable = 'NO'
    ) <> 2 then
        raise exception 'Migration 005 requires non-null text learner source, code_module, and code_presentation columns';
    end if;

    select data_type, is_nullable into dataset_id_type, dataset_id_nullable
    from information_schema.columns
    where table_schema = 'public' and table_name = 'learners'
      and column_name = 'dataset_id';

    -- Detect source-key duplicates before the first DDL or filename backfill.
    -- If dataset_id already exists, keep its dataset-scoped interpretation.
    if dataset_id_type is null then
        execute format(
            'select exists (
                select 1 from public.learners
                group by %I, code_module, code_presentation
                having count(*) > 1
            )', source_identifier_column
        ) into duplicate_source_groups;
    else
        execute format(
            'select exists (
                select 1 from public.learners
                group by dataset_id, %I, code_module, code_presentation
                having count(*) > 1
            )', source_identifier_column
        ) into duplicate_source_groups;
    end if;
    if duplicate_source_groups then
        raise exception 'Learner source keys contain duplicate groups; review before migration 005';
    end if;

    -- If earlier/manual work already added these fields, reject incompatible
    -- definitions instead of letting ADD COLUMN IF NOT EXISTS silently accept them.
    select data_type into dataset_name_type
    from information_schema.columns
    where table_schema = 'public' and table_name = 'dataset_uploads'
      and column_name = 'dataset_name';
    if dataset_name_type is not null
       and dataset_name_type not in ('text', 'character varying') then
        raise exception 'Existing dataset_uploads.dataset_name must be text before migration 005';
    end if;

    select data_type, is_nullable into owner_id_type, owner_id_nullable
    from information_schema.columns
    where table_schema = 'public' and table_name = 'dataset_uploads'
      and column_name = 'owner_id';
    if owner_id_type is not null and owner_id_type <> 'uuid' then
        raise exception 'Existing dataset_uploads.owner_id must be uuid before migration 005';
    end if;
    if owner_id_nullable is not null and owner_id_nullable <> 'YES' then
        raise exception 'Existing dataset_uploads.owner_id must remain nullable to preserve unassigned historical uploads';
    end if;
    if owner_id_type is not null and not exists (
        select 1 from pg_constraint c
        where c.conrelid = dataset_uploads_oid
          and c.contype = 'f'
          and c.confrelid = auth_users_oid
          and c.conkey = array[(
              select a.attnum from pg_attribute a
              where a.attrelid = dataset_uploads_oid and a.attname = 'owner_id'
          )]::smallint[]
          and c.confkey = array[(
              select a.attnum from pg_attribute a
              where a.attrelid = auth_users_oid and a.attname = 'id'
          )]::smallint[]
          and c.confdeltype = 'c'
          and c.convalidated
    ) then
        raise exception 'Existing dataset_uploads.owner_id must reference auth.users(id) with ON DELETE CASCADE';
    end if;

    if dataset_id_type is not null and dataset_id_type <> 'uuid' then
        raise exception 'Existing learners.dataset_id must be uuid before migration 005';
    end if;
    if dataset_id_nullable is not null and dataset_id_nullable <> 'YES' then
        raise exception 'Existing learners.dataset_id must remain nullable to preserve unassigned historical learners';
    end if;
    if dataset_id_type is not null and not exists (
        select 1 from pg_constraint c
        where c.conrelid = learners_oid
          and c.contype = 'f'
          and c.confrelid = dataset_uploads_oid
          and c.conkey = array[(
              select a.attnum from pg_attribute a
              where a.attrelid = learners_oid and a.attname = 'dataset_id'
          )]::smallint[]
          and c.confkey = array[(
              select a.attnum from pg_attribute a
              where a.attrelid = dataset_uploads_oid and a.attname = 'id'
          )]::smallint[]
          and c.confdeltype = 'c'
          and c.convalidated
    ) then
        raise exception 'Existing learners.dataset_id must reference dataset_uploads(id) with ON DELETE CASCADE';
    end if;

    if exists (
        select 1
        from (values
            ('file_size_bytes', 'bigint'),
            ('row_count', 'bigint'),
            ('validation_results', 'jsonb'),
            ('descriptive_compatible', 'boolean'),
            ('prediction_compatible', 'boolean'),
            ('processing_progress', 'smallint'),
            ('processed_at', 'timestamp with time zone'),
            ('updated_at', 'timestamp with time zone')
        ) as expected(column_name, data_type)
        join information_schema.columns actual
          on actual.table_schema = 'public'
         and actual.table_name = 'dataset_uploads'
         and actual.column_name = expected.column_name
        where actual.data_type <> expected.data_type
    ) then
        raise exception 'Existing dataset_uploads processing metadata has an incompatible type; reconcile it before migration 005';
    end if;

    if exists (
        select 1 from public.dataset_uploads
        where filename is null or length(btrim(filename::text)) = 0
           or status::text not in ('uploaded', 'validated', 'processing', 'processed', 'failed')
    ) then
        raise exception 'Dataset uploads contain a blank filename or unsupported status; review rows before migration 005';
    end if;

    if dataset_name_type is not null then
        execute 'select exists (
            select 1 from public.dataset_uploads
            where (dataset_name is null and length(btrim(filename::text)) = 0)
               or (dataset_name is not null and length(btrim(dataset_name::text)) = 0)
        )' into invalid_dataset_name;
        if invalid_dataset_name then
            raise exception 'Dataset names cannot be derived from blank filenames or existing blank names; review before migration 005';
        end if;
    end if;
end;
$$;

alter table public.dataset_uploads
    add column if not exists owner_id uuid references auth.users(id) on delete cascade,
    add column if not exists dataset_name text,
    add column if not exists file_size_bytes bigint,
    add column if not exists row_count bigint,
    add column if not exists validation_results jsonb not null default '{}'::jsonb,
    add column if not exists descriptive_compatible boolean not null default false,
    add column if not exists prediction_compatible boolean not null default false,
    add column if not exists processing_progress smallint not null default 0,
    add column if not exists processed_at timestamptz,
    add column if not exists updated_at timestamptz not null default now();

update public.dataset_uploads
set dataset_name = filename
where dataset_name is null;

alter table public.dataset_uploads
    alter column dataset_name set not null,
    drop constraint if exists dataset_uploads_status_check,
    add constraint dataset_uploads_status_check
        check (status in ('uploaded', 'validated', 'processing', 'processed', 'failed')),
    add constraint dataset_uploads_file_size_nonnegative
        check (file_size_bytes is null or file_size_bytes >= 0),
    add constraint dataset_uploads_row_count_nonnegative
        check (row_count is null or row_count >= 0),
    add constraint dataset_uploads_progress_range
        check (processing_progress between 0 and 100);

-- The deployed schema uses external_learner_id. Older local installations
-- created by migrations 001/002 may still have id_student. Normalize that
-- legacy column without creating a second source-identifier column.
do $$
declare
    has_external_id boolean;
    has_legacy_id boolean;
begin
    select exists (
        select 1 from information_schema.columns
        where table_schema = 'public' and table_name = 'learners'
          and column_name = 'external_learner_id'
    ) into has_external_id;
    select exists (
        select 1 from information_schema.columns
        where table_schema = 'public' and table_name = 'learners'
          and column_name = 'id_student'
    ) into has_legacy_id;

    if has_external_id and has_legacy_id then
        raise exception 'Both learner source-id columns exist; manually reconcile the schema before migration 005';
    end if;
    if not has_external_id and has_legacy_id then
        alter table public.learners rename column id_student to external_learner_id;
        has_external_id := true;
    end if;
    if not has_external_id then
        raise exception 'Migration 005 requires public.learners.external_learner_id (or legacy id_student)';
    end if;
    if (
        select count(*) from information_schema.columns
        where table_schema = 'public' and table_name = 'learners'
          and column_name in ('external_learner_id', 'code_module', 'code_presentation')
          and data_type in ('text', 'character varying')
          and is_nullable = 'NO'
    ) <> 3 then
        raise exception 'Migration 005 requires non-null text external_learner_id, code_module, and code_presentation columns';
    end if;
end;
$$;

-- Preserve old records with NULL ownership; reject new unowned dataset rows.
create or replace function public.require_dataset_owner_for_new_upload()
returns trigger
language plpgsql
security invoker
set search_path = ''
as $$
begin
    if new.owner_id is null then
        raise exception 'owner_id is required for new dataset uploads';
    end if;
    if new.dataset_name is null or length(btrim(new.dataset_name)) = 0 then
        raise exception 'dataset_name is required for new dataset uploads';
    end if;
    return new;
end;
$$;

revoke all on function public.require_dataset_owner_for_new_upload()
    from public, anon, authenticated;
drop trigger if exists dataset_upload_require_owner on public.dataset_uploads;
create trigger dataset_upload_require_owner
    before insert on public.dataset_uploads
    for each row execute function public.require_dataset_owner_for_new_upload();

alter table public.learners
    add column if not exists dataset_id uuid
        references public.dataset_uploads(id) on delete cascade;

do $$
declare
    duplicate_groups bigint;
begin
    select count(*) into duplicate_groups
    from (
        select dataset_id, external_learner_id, code_module, code_presentation
        from public.learners
        group by dataset_id, external_learner_id, code_module, code_presentation
        having count(*) > 1
    ) duplicates;
    if duplicate_groups > 0 then
        raise exception 'Learner source keys contain % duplicate dataset groups; review before migration 005', duplicate_groups;
    end if;
end;
$$;

-- The old composite uniqueness was global and prevented identical OULAD keys
-- from existing in separate user datasets. NULL dataset_id is retained only
-- for legacy records; it is not treated as belonging to any user.
-- Drop only a unique constraint over the old global source key, regardless
-- of its generated/name-specific identifier. Other unique constraints stay.
do $$
declare
    old_constraint record;
begin
    for old_constraint in
        select c.conname
        from pg_constraint c
        where c.conrelid = 'public.learners'::regclass
          and c.contype = 'u'
          and (
              select array_agg(a.attname::text order by a.attname::text)
              from unnest(c.conkey) as key(attnum)
              join pg_attribute a on a.attrelid = c.conrelid and a.attnum = key.attnum
          ) = array['code_module', 'code_presentation', 'external_learner_id']::text[]
    loop
        execute format('alter table public.learners drop constraint %I', old_constraint.conname);
    end loop;
end;
$$;

do $$
declare
    existing_constraint record;
    constraint_exists boolean;
begin
    select c.conname,
           (
               select array_agg(a.attname::text order by a.attname::text)
               from unnest(c.conkey) as key(attnum)
               join pg_attribute a on a.attrelid = c.conrelid and a.attnum = key.attnum
           ) as column_names
      into existing_constraint
      from pg_constraint c
     where c.conrelid = 'public.learners'::regclass
       and c.conname = 'learners_dataset_source_unique'
       and c.contype = 'u';
    constraint_exists := found;

    if constraint_exists then
        if existing_constraint.column_names <> array[
            'code_module', 'code_presentation', 'dataset_id', 'external_learner_id'
        ]::text[] then
            raise exception 'learners_dataset_source_unique exists with unexpected columns';
        end if;
    end if;
    if not constraint_exists then
        alter table public.learners
            add constraint learners_dataset_source_unique
            unique (dataset_id, external_learner_id, code_module, code_presentation);
    end if;
end;
$$;

-- Preserve global uniqueness for legacy, unassigned rows. New imports always
-- have a dataset_id; the dataset-scoped constraint permits identical source
-- identifiers in different datasets. NULL dataset IDs remain non-owned.
create unique index if not exists learners_legacy_source_unique
    on public.learners (external_learner_id, code_module, code_presentation)
    where dataset_id is null;

create index if not exists dataset_uploads_owner_uploaded_idx
    on public.dataset_uploads (owner_id, uploaded_at desc);
create index if not exists learners_dataset_course_idx
    on public.learners (dataset_id, code_module, code_presentation, created_at desc);
create index if not exists learner_features_learner_snapshot_idx
    on public.learner_features (learner_id, as_of_date desc, created_at desc);
create index if not exists recommendations_learner_created_idx
    on public.recommendations (learner_id, created_at desc);

-- Preserve every existing output column name, type, and position from 004.
-- Preserve the existing view columns and order from 004; append any missing
-- canonical source-id and dataset fields required by the backend.
do $$
declare
    output_columns text;
begin
    select string_agg(
        case c.column_name
            when 'latest_prediction_id' then 'latest.id as latest_prediction_id'
            when 'latest_model_version' then 'latest.model_version as latest_model_version'
            when 'latest_risk_probability' then 'latest.risk_probability as latest_risk_probability'
            when 'latest_risk_category' then 'latest.risk_category as latest_risk_category'
            when 'latest_prediction_created_at' then 'latest.created_at as latest_prediction_created_at'
            when 'id_student' then 'learner.external_learner_id as id_student'
            else format('learner.%I', c.column_name)
        end,
        ', ' order by c.ordinal_position
    ) into output_columns
    from information_schema.columns c
    where c.table_schema = 'public'
      and c.table_name = 'learners_latest_prediction'
      and c.column_name <> 'dataset_id';

    if output_columns is null then
        raise exception 'Migration 005 requires migration 004 view public.learners_latest_prediction';
    end if;

    if not exists (
        select 1 from information_schema.columns
        where table_schema = 'public' and table_name = 'learners_latest_prediction'
          and column_name = 'external_learner_id'
    ) then
        output_columns := output_columns || ', learner.external_learner_id as external_learner_id';
    end if;
    output_columns := output_columns || ', learner.dataset_id';

    execute format(
        'create or replace view public.learners_latest_prediction with (security_invoker = true) as
         select %s
         from public.learners as learner
         left join lateral (
             select prediction.id, prediction.model_version,
                    prediction.risk_probability, prediction.risk_category,
                    prediction.created_at
             from public.predictions as prediction
             where prediction.learner_id = learner.id
             order by prediction.created_at desc, prediction.id desc
             limit 1
         ) as latest on true',
        output_columns
    );
end;
$$;

create or replace view public.learner_latest_feature_snapshot
with (security_invoker = true)
as
select distinct on (feature.learner_id)
    feature.learner_id,
    feature.as_of_date,
    feature.features,
    feature.created_at as feature_created_at,
    learner.dataset_id
from public.learner_features as feature
join public.learners as learner on learner.id = feature.learner_id
order by feature.learner_id, feature.as_of_date desc, feature.created_at desc, feature.id desc;

create or replace view public.learner_latest_recommendation
with (security_invoker = true)
as
select distinct on (recommendation.learner_id)
    recommendation.id,
    recommendation.learner_id,
    recommendation.prediction_id,
    recommendation.action,
    recommendation.reason,
    recommendation.status,
    recommendation.created_at,
    recommendation.updated_at,
    learner.dataset_id
from public.recommendations as recommendation
join public.learners as learner on learner.id = recommendation.learner_id
order by recommendation.learner_id, recommendation.created_at desc, recommendation.id desc;

grant select on public.learners_latest_prediction to authenticated, service_role;
grant select on public.learner_latest_feature_snapshot to authenticated, service_role;
grant select on public.learner_latest_recommendation to authenticated, service_role;

create or replace view public.dataset_dashboard_summary
with (security_invoker = true)
as
select
    dataset.id as dataset_id,
    count(learner.id)::bigint as total_learner_records,
    count(distinct (learner.code_module, learner.code_presentation))
        filter (where learner.id is not null)::bigint as course_presentation_count,
    count(latest.latest_prediction_id)::bigint as learners_with_prediction,
    count(*) filter (where latest.latest_risk_category = 'low')::bigint as low_risk_count,
    count(*) filter (where latest.latest_risk_category = 'medium')::bigint as medium_risk_count,
    count(*) filter (where latest.latest_risk_category = 'high')::bigint as high_risk_count
from public.dataset_uploads as dataset
left join public.learners as learner on learner.dataset_id = dataset.id
left join public.learners_latest_prediction as latest on latest.id = learner.id
group by dataset.id;

grant select on public.dataset_dashboard_summary to authenticated, service_role;

-- The backend uses a privileged server-side client, so these policies also
-- protect clients that access PostgREST directly with an authenticated token.
drop policy if exists dataset_uploads_select_owner on public.dataset_uploads;
create policy dataset_uploads_select_owner on public.dataset_uploads
    for select to authenticated
    using (owner_id = (select auth.uid()) and exists (
        select 1 from public.profiles p
        where p.id = (select auth.uid()) and p.approval_status = 'approved'
    ));

drop policy if exists dataset_uploads_insert_owner on public.dataset_uploads;
create policy dataset_uploads_insert_owner on public.dataset_uploads
    for insert to authenticated
    with check (owner_id = (select auth.uid()) and exists (
        select 1 from public.profiles p
        where p.id = (select auth.uid()) and p.approval_status = 'approved' and p.role = 'admin'
    ));

drop policy if exists dataset_uploads_update_owner on public.dataset_uploads;
create policy dataset_uploads_update_owner on public.dataset_uploads
    for update to authenticated
    using (owner_id = (select auth.uid()) and exists (
        select 1 from public.profiles p
        where p.id = (select auth.uid()) and p.approval_status = 'approved' and p.role = 'admin'
    ))
    with check (owner_id = (select auth.uid()) and exists (
        select 1 from public.profiles p
        where p.id = (select auth.uid()) and p.approval_status = 'approved' and p.role = 'admin'
    ));

drop policy if exists learners_select_dataset_owner on public.learners;
create policy learners_select_dataset_owner on public.learners
    for select to authenticated
    using (dataset_id is not null and exists (
        select 1 from public.dataset_uploads d
        join public.profiles p on p.id = (select auth.uid())
        where d.id = learners.dataset_id
          and d.owner_id = (select auth.uid())
          and p.approval_status = 'approved'
    ));

drop policy if exists learner_features_select_dataset_owner on public.learner_features;
create policy learner_features_select_dataset_owner on public.learner_features
    for select to authenticated
    using (exists (
        select 1 from public.learners l
        join public.dataset_uploads d on d.id = l.dataset_id
        join public.profiles p on p.id = (select auth.uid())
        where l.id = learner_features.learner_id
          and d.owner_id = (select auth.uid())
          and p.approval_status = 'approved'
    ));

drop policy if exists predictions_select_dataset_owner on public.predictions;
create policy predictions_select_dataset_owner on public.predictions
    for select to authenticated
    using (exists (
        select 1 from public.learners l
        join public.dataset_uploads d on d.id = l.dataset_id
        join public.profiles p on p.id = (select auth.uid())
        where l.id = predictions.learner_id
          and d.owner_id = (select auth.uid())
          and p.approval_status = 'approved'
    ));

drop policy if exists risk_explanations_select_dataset_owner on public.risk_explanations;
create policy risk_explanations_select_dataset_owner on public.risk_explanations
    for select to authenticated
    using (exists (
        select 1 from public.predictions prediction
        join public.learners learner on learner.id = prediction.learner_id
        join public.dataset_uploads dataset on dataset.id = learner.dataset_id
        join public.profiles profile on profile.id = (select auth.uid())
        where prediction.id = risk_explanations.prediction_id
          and dataset.owner_id = (select auth.uid())
          and profile.approval_status = 'approved'
    ));

drop policy if exists recommendations_select_dataset_owner on public.recommendations;
create policy recommendations_select_dataset_owner on public.recommendations
    for select to authenticated
    using (exists (
        select 1 from public.learners l
        join public.dataset_uploads d on d.id = l.dataset_id
        join public.profiles p on p.id = (select auth.uid())
        where l.id = recommendations.learner_id
          and d.owner_id = (select auth.uid())
          and p.approval_status = 'approved'
    ));

commit;
