-- MANUAL REVIEW PROPOSAL ONLY. Do not execute before reviewing the deployed
-- migration history, table definition, existing rows, privileges, and RLS.
-- Intended to run after migrations 001-007 have been verified as deployed.
--
-- Generated recommendation identity is (prediction_id, rule_id). A prediction
-- identifies a saved learner/model prediction; its learner FK carries the
-- dataset association. New application writes must provide both values.
-- Existing recommendations retain NULL rule_id: no backfill, deletion, or
-- automatic reconciliation is performed. PostgreSQL's ordinary UNIQUE NULL
-- semantics allow these historical rows to remain unchanged while preventing
-- duplicate non-null generated keys. Old rows with NULL rule_id therefore do
-- not conflict with newly generated recommendations.

begin;

-- Fail before altering anything if the expected base schema is absent or has
-- incompatible identifier types/relationships.
do $$
declare
    recommendations_oid oid := to_regclass('public.recommendations');
    predictions_oid oid := to_regclass('public.predictions');
    learners_oid oid := to_regclass('public.learners');
    prediction_type text;
    learner_type text;
    predictions_id_type text;
    learners_id_type text;
    has_prediction_fk boolean;
    has_learner_fk boolean;
begin
    if recommendations_oid is null then
        raise exception 'Required table public.recommendations does not exist';
    end if;
    if predictions_oid is null then
        raise exception 'Required table public.predictions does not exist';
    end if;
    if learners_oid is null then
        raise exception 'Required table public.learners does not exist';
    end if;

    select data_type into prediction_type
      from information_schema.columns
     where table_schema = 'public' and table_name = 'recommendations'
       and column_name = 'prediction_id';
    select data_type into learner_type
      from information_schema.columns
     where table_schema = 'public' and table_name = 'recommendations'
       and column_name = 'learner_id';
    select data_type into predictions_id_type
      from information_schema.columns
     where table_schema = 'public' and table_name = 'predictions'
       and column_name = 'id';
    select data_type into learners_id_type
      from information_schema.columns
     where table_schema = 'public' and table_name = 'learners'
       and column_name = 'id';

    if prediction_type is distinct from 'uuid'
       or predictions_id_type is distinct from 'uuid' then
        raise exception 'Expected recommendations.prediction_id and predictions.id to exist as uuid columns';
    end if;
    if learner_type is distinct from 'uuid'
       or learners_id_type is distinct from 'uuid' then
        raise exception 'Expected recommendations.learner_id and learners.id to exist as uuid columns';
    end if;

    select exists (
        select 1 from pg_constraint c
        where c.conrelid = recommendations_oid and c.contype = 'f'
          and c.confrelid = predictions_oid
          and c.conkey = array[(select a.attnum from pg_attribute a
                                where a.attrelid = recommendations_oid
                                  and a.attname = 'prediction_id')]::smallint[]
          and c.confkey = array[(select a.attnum from pg_attribute a
                                 where a.attrelid = predictions_oid
                                   and a.attname = 'id')]::smallint[]
    ) into has_prediction_fk;
    select exists (
        select 1 from pg_constraint c
        where c.conrelid = recommendations_oid and c.contype = 'f'
          and c.confrelid = learners_oid
          and c.conkey = array[(select a.attnum from pg_attribute a
                                where a.attrelid = recommendations_oid
                                  and a.attname = 'learner_id')]::smallint[]
          and c.confkey = array[(select a.attnum from pg_attribute a
                                 where a.attrelid = learners_oid
                                   and a.attname = 'id')]::smallint[]
    ) into has_learner_fk;

    if has_prediction_fk is distinct from true then
        raise exception 'Required foreign key recommendations.prediction_id -> predictions.id is missing';
    end if;
    if has_learner_fk is distinct from true then
        raise exception 'Required foreign key recommendations.learner_id -> learners.id is missing';
    end if;
end;
$$;

alter table public.recommendations
    add column if not exists rule_id text;

do $$
declare
    rule_id_type text;
    rule_id_nullable text;
    duplicate_groups bigint;
    existing_index oid := to_regclass('public.recommendations_prediction_rule_unique');
    recommendations_oid oid := 'public.recommendations'::regclass;
    index_table_oid oid;
    index_is_unique boolean;
    index_is_valid boolean;
    index_is_ready boolean;
    index_is_partial boolean;
    index_has_included_columns boolean;
    index_nulls_not_distinct boolean;
    indexed_columns text[];
begin
    select data_type, is_nullable into rule_id_type, rule_id_nullable
    from information_schema.columns
    where table_schema = 'public'
      and table_name = 'recommendations'
      and column_name = 'rule_id';

    if rule_id_type is distinct from 'text' then
        raise exception 'Migration proposal requires recommendations.rule_id to be text';
    end if;
    if rule_id_nullable is distinct from 'YES' then
        raise exception 'Migration proposal requires nullable recommendations.rule_id; existing column was not altered';
    end if;

    select count(*) into duplicate_groups
    from (
        select prediction_id, rule_id
        from public.recommendations
        where prediction_id is not null and rule_id is not null
        group by prediction_id, rule_id
        having count(*) > 1
    ) duplicate_keys;

    if duplicate_groups > 0 then
        raise exception 'Recommendations contain % duplicate non-null prediction/rule key groups; review them manually before adding idempotency', duplicate_groups;
    end if;

    if existing_index is not null then
        if current_setting('server_version_num')::integer < 150000 then
            raise exception 'Cannot verify ordinary NULL-distinct index semantics; PostgreSQL 15 or newer is required for this proposal';
        end if;

        select i.indrelid,
               i.indisunique,
               i.indisvalid,
               i.indisready,
               i.indpred is not null,
               i.indnatts <> i.indnkeyatts,
               i.indnullsnotdistinct,
               array(
                   select a.attname::text
                   from unnest(i.indkey) with ordinality as key(attnum, ordinality)
                   join pg_attribute a
                     on a.attrelid = i.indrelid and a.attnum = key.attnum
                   where key.ordinality <= i.indnkeyatts
                   order by key.ordinality
               )
          into index_table_oid, index_is_unique, index_is_valid, index_is_ready,
               index_is_partial, index_has_included_columns,
               index_nulls_not_distinct, indexed_columns
          from pg_index i
         where i.indexrelid = existing_index;

        if index_table_oid is distinct from recommendations_oid
           or index_is_unique is distinct from true
           or index_is_valid is distinct from true
           or index_is_ready is distinct from true
           or index_is_partial is distinct from false
           or index_has_included_columns is distinct from false
           or index_nulls_not_distinct is distinct from false
           or indexed_columns is distinct from array['prediction_id', 'rule_id']::text[] then
            raise exception 'recommendations_prediction_rule_unique exists with an unexpected definition; review the index manually';
        end if;
    end if;
end;
$$;

-- Unconditional index is intentional: the current Supabase client supplies
-- the conflict columns but cannot supply a partial-index predicate. NULL key
-- values remain distinct under ordinary PostgreSQL unique-index semantics.
create unique index if not exists recommendations_prediction_rule_unique
    on public.recommendations (prediction_id, rule_id);

commit;
