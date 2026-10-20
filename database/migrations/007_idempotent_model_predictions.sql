-- Keep one current prediction per learner and model version.
-- Reprocessing a dataset upserts this row instead of accumulating duplicates.
-- Review any existing duplicates before applying; this migration deliberately
-- does not delete or merge prediction history.

begin;

do $$
declare
    duplicate_groups bigint;
begin
    if not exists (
        select 1 from information_schema.columns
        where table_schema = 'public' and table_name = 'predictions'
          and column_name = 'learner_id'
    ) or not exists (
        select 1 from information_schema.columns
        where table_schema = 'public' and table_name = 'predictions'
          and column_name = 'model_version'
    ) then
        raise exception 'Migration 007 requires predictions.learner_id and predictions.model_version';
    end if;
    if not exists (
        select 1 from information_schema.columns
        where table_schema = 'public' and table_name = 'predictions'
          and column_name = 'learner_id' and data_type = 'uuid'
    ) or not exists (
        select 1 from information_schema.columns
        where table_schema = 'public' and table_name = 'predictions'
          and column_name = 'model_version'
          and data_type in ('text', 'character varying')
    ) then
        raise exception 'Prediction idempotency key must be UUID learner_id plus text model_version';
    end if;
    if not exists (
        select 1 from information_schema.columns
        where table_schema = 'public' and table_name = 'predictions'
          and column_name = 'created_at'
    ) then
        raise exception 'Migration 007 requires predictions.created_at for deterministic latest-row ordering';
    end if;

    -- NULL values are distinct in an ordinary PostgreSQL unique index. Refuse
    -- to silently leave rows outside the idempotency key, then enforce the
    -- non-null contract used by migrations 001/002 and the inference writer.
    if exists (select 1 from public.predictions where learner_id is null) then
        raise exception 'Predictions contain NULL learner_id values; review them before migration 007';
    end if;
    if exists (select 1 from public.predictions where model_version is null) then
        raise exception 'Predictions contain NULL model_version values; review them before migration 007';
    end if;
    if exists (select 1 from public.predictions where created_at is null) then
        raise exception 'Predictions contain NULL created_at values; review them before migration 007';
    end if;

    select count(*) into duplicate_groups
    from (
        select learner_id, model_version
        from public.predictions
        group by learner_id, model_version
        having count(*) > 1
    ) duplicates;

    if duplicate_groups > 0 then
        raise exception 'Duplicate learner/model predictions exist (% groups); review and resolve them before migration 007', duplicate_groups;
    end if;
end;
$$;

alter table public.predictions
    alter column learner_id set not null,
    alter column model_version set not null,
    alter column created_at set not null;

do $$
declare
    existing_index oid := to_regclass('public.predictions_learner_model_unique');
    predictions_oid oid := to_regclass('public.predictions');
    index_table_oid oid;
    index_is_unique boolean;
    index_is_valid boolean;
    index_is_ready boolean;
    index_is_partial boolean;
    index_has_included_columns boolean;
    index_has_expressions boolean;
    indexed_columns text[];
begin
    if existing_index is not null then
        select i.indrelid,
               i.indisunique,
               i.indisvalid,
               i.indisready,
               i.indpred is not null,
               i.indnatts <> i.indnkeyatts,
               i.indexprs is not null,
               array(
                   select a.attname::text
                   from unnest(i.indkey) with ordinality as key(attnum, ordinality)
                   join pg_attribute a
                     on a.attrelid = i.indrelid and a.attnum = key.attnum
                   where key.ordinality <= i.indnkeyatts
                   order by key.ordinality
               )
          into index_table_oid, index_is_unique, index_is_valid, index_is_ready,
               index_is_partial, index_has_included_columns, index_has_expressions,
               indexed_columns
          from pg_index i
         where i.indexrelid = existing_index;

        if predictions_oid is null
           or index_table_oid is distinct from predictions_oid
           or index_is_unique is distinct from true
           or index_is_valid is distinct from true
           or index_is_ready is distinct from true
           or index_is_partial is distinct from false
           or index_has_included_columns is distinct from false
           or index_has_expressions is distinct from false
           or indexed_columns is distinct from array['learner_id', 'model_version']::text[] then
            raise exception 'predictions_learner_model_unique exists with an unexpected definition';
        end if;
    end if;
end;
$$;

create unique index if not exists predictions_learner_model_unique
    on public.predictions (learner_id, model_version);

commit;
