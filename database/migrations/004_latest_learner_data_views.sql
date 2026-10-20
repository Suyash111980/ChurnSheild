-- Read-optimized latest-record views for learner lists and early warning.
-- security_invoker keeps the underlying tables' RLS behavior in force.

create or replace view public.learners_latest_prediction
with (security_invoker = true)
as
select
    learner.*,
    latest.id as latest_prediction_id,
    latest.model_version as latest_model_version,
    latest.risk_probability as latest_risk_probability,
    latest.risk_category as latest_risk_category,
    latest.created_at as latest_prediction_created_at
from public.learners as learner
left join lateral (
    select prediction.id,
           prediction.model_version,
           prediction.risk_probability,
           prediction.risk_category,
           prediction.created_at
    from public.predictions as prediction
    where prediction.learner_id = learner.id
    order by prediction.created_at desc, prediction.id desc
    limit 1
) as latest on true;

create or replace view public.learner_latest_feature_snapshot
with (security_invoker = true)
as
select distinct on (feature.learner_id)
    feature.learner_id,
    feature.as_of_date,
    feature.features,
    feature.created_at as feature_created_at
from public.learner_features as feature
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
    recommendation.updated_at
from public.recommendations as recommendation
order by recommendation.learner_id, recommendation.created_at desc, recommendation.id desc;

grant select on public.learners_latest_prediction to authenticated, service_role;
grant select on public.learner_latest_feature_snapshot to authenticated, service_role;
grant select on public.learner_latest_recommendation to authenticated, service_role;
