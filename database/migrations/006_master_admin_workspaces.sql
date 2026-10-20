-- ChurnShield Master Admin approval and isolated Admin workspaces.
-- Historical dataset/learner rows are intentionally left unassigned.
begin;

alter table public.profiles
    add column if not exists requested_role text;
alter table public.profiles
    drop constraint if exists profiles_requested_role_check;
alter table public.profiles
    add constraint profiles_requested_role_check
        check (requested_role is null or requested_role = 'admin');
create index if not exists profiles_admin_request_status_idx
    on public.profiles (approval_status, created_at)
    where requested_role = 'admin';

create or replace function public.create_pending_profile_for_new_auth_user()
returns trigger language plpgsql security definer set search_path = '' as $$
begin
    -- requested_role is only an approval request. Public metadata never sets role/status.
    insert into public.profiles (id, role, approval_status, requested_role)
    values (
        new.id,
        'educator',
        'pending',
        case when new.raw_user_meta_data ->> 'requested_role' = 'admin' then 'admin' else null end
    )
    on conflict (id) do nothing;
    return new;
end;
$$;
revoke all on function public.create_pending_profile_for_new_auth_user() from public, anon, authenticated;
grant execute on function public.create_pending_profile_for_new_auth_user() to supabase_auth_admin;

create table if not exists public.workspaces (
    id uuid primary key default gen_random_uuid(),
    admin_user_id uuid not null unique references public.profiles(id) on delete cascade,
    status text not null default 'active' check (status in ('active', 'suspended')),
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);
alter table public.workspaces enable row level security;
revoke all on public.workspaces from anon, authenticated;
grant select on public.workspaces to authenticated;
grant select, insert, update on public.workspaces to service_role;
drop policy if exists workspaces_select_owner on public.workspaces;
create policy workspaces_select_owner on public.workspaces
    for select to authenticated using (
        admin_user_id = (select auth.uid()) and status = 'active' and exists (
            select 1 from public.profiles p
             where p.id = (select auth.uid()) and p.role = 'admin'
               and p.approval_status = 'approved'
        )
    );

alter table public.dataset_uploads
    add column if not exists workspace_id uuid references public.workspaces(id) on delete cascade;
create index if not exists dataset_uploads_workspace_uploaded_idx
    on public.dataset_uploads (workspace_id, uploaded_at desc);
create unique index if not exists dataset_uploads_id_workspace_unique
    on public.dataset_uploads (id, workspace_id);

-- Approval and workspace assignment happen atomically and are repeat-safe.
create or replace function public.master_review_admin_request(
    target_user_id uuid,
    decision text
) returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
declare
    target public.profiles%rowtype;
    assigned_workspace public.workspaces%rowtype;
begin
    if decision is null or decision not in ('approve', 'reject') then
        raise exception 'invalid_decision';
    end if;
    select * into target from public.profiles
      where id = target_user_id for update;
    if not found or target.requested_role is distinct from 'admin' then
        raise exception 'admin_request_not_found';
    end if;
    if decision = 'approve' then
        if target.approval_status = 'denied' then
            raise exception 'request_already_rejected';
        end if;
        update public.profiles
           set role = 'admin', approval_status = 'approved', updated_at = now()
         where id = target_user_id;
        insert into public.workspaces(admin_user_id)
        values (target_user_id)
        on conflict (admin_user_id) do nothing;
        select * into assigned_workspace from public.workspaces where admin_user_id = target_user_id;
    else
        if target.approval_status = 'approved' then
            raise exception 'request_already_approved';
        end if;
        update public.profiles
           set approval_status = 'denied', updated_at = now()
         where id = target_user_id;
    end if;
    return jsonb_build_object(
        'id', target_user_id,
        'role', case when decision = 'approve' then 'admin' else target.role end,
        'approval_status', case when decision = 'approve' then 'approved' else 'denied' end,
        'workspace_id', case when decision = 'approve' then assigned_workspace.id else null end
    );
end;
$$;
revoke all on function public.master_review_admin_request(uuid, text) from public, anon, authenticated;
grant execute on function public.master_review_admin_request(uuid, text) to service_role;

-- Never accept a workspace chosen by the browser. It must match the uploader's
-- unique workspace and approved Admin profile.
create or replace function public.validate_dataset_workspace()
returns trigger language plpgsql security invoker set search_path = '' as $$
begin
    if new.owner_id is null or new.workspace_id is null then
        raise exception 'owner and workspace are required';
    end if;
    if not exists (
        select 1 from public.workspaces w join public.profiles p on p.id = w.admin_user_id
         where w.id = new.workspace_id and w.admin_user_id = new.owner_id
           and w.status = 'active' and p.role = 'admin' and p.approval_status = 'approved'
    ) then
        raise exception 'workspace does not belong to an approved Admin';
    end if;
    return new;
end;
$$;
revoke all on function public.validate_dataset_workspace() from public, anon, authenticated;
drop trigger if exists dataset_upload_validate_workspace on public.dataset_uploads;
create trigger dataset_upload_validate_workspace
    before insert or update of owner_id, workspace_id on public.dataset_uploads
    for each row execute function public.validate_dataset_workspace();

drop policy if exists dataset_uploads_select_owner on public.dataset_uploads;
create policy dataset_uploads_select_owner on public.dataset_uploads
    for select to authenticated using (
        workspace_id is not null and owner_id = (select auth.uid()) and exists (
            select 1 from public.workspaces w join public.profiles p on p.id = w.admin_user_id
             where w.id = dataset_uploads.workspace_id and w.admin_user_id = (select auth.uid())
               and w.status = 'active'
               and p.approval_status = 'approved' and p.role = 'admin'
        )
    );

drop policy if exists dataset_uploads_insert_owner on public.dataset_uploads;
create policy dataset_uploads_insert_owner on public.dataset_uploads
    for insert to authenticated with check (
        owner_id = (select auth.uid())
        and workspace_id is not null
        and exists (
            select 1 from public.workspaces w
            join public.profiles p on p.id = w.admin_user_id
            where w.id = dataset_uploads.workspace_id
              and w.admin_user_id = (select auth.uid())
              and w.status = 'active'
              and p.role = 'admin'
              and p.approval_status = 'approved'
        )
    );

drop policy if exists dataset_uploads_update_owner on public.dataset_uploads;
create policy dataset_uploads_update_owner on public.dataset_uploads
    for update to authenticated
    using (
        owner_id = (select auth.uid())
        and workspace_id is not null
        and exists (
            select 1 from public.workspaces w
            join public.profiles p on p.id = w.admin_user_id
            where w.id = dataset_uploads.workspace_id
              and w.admin_user_id = (select auth.uid())
              and w.status = 'active'
              and p.role = 'admin'
              and p.approval_status = 'approved'
        )
    )
    with check (
        owner_id = (select auth.uid())
        and workspace_id is not null
        and exists (
            select 1 from public.workspaces w
            join public.profiles p on p.id = w.admin_user_id
            where w.id = dataset_uploads.workspace_id
              and w.admin_user_id = (select auth.uid())
              and w.status = 'active'
              and p.role = 'admin'
              and p.approval_status = 'approved'
        )
    );

-- The dataset's owner/workspace pair is the authorization boundary for every
-- dependent row. This replaces 005's owner-only checks with the same active
-- workspace rule used for dataset uploads.
drop policy if exists learners_select_dataset_owner on public.learners;
create policy learners_select_dataset_owner on public.learners
    for select to authenticated using (
        dataset_id is not null and exists (
            select 1 from public.dataset_uploads d
            join public.workspaces w on w.id = d.workspace_id
            join public.profiles p on p.id = w.admin_user_id
            where d.id = learners.dataset_id
              and d.owner_id = (select auth.uid())
              and w.admin_user_id = (select auth.uid())
              and w.status = 'active'
              and p.role = 'admin'
              and p.approval_status = 'approved'
        )
    );

drop policy if exists learner_features_select_dataset_owner on public.learner_features;
create policy learner_features_select_dataset_owner on public.learner_features
    for select to authenticated using (
        exists (
            select 1 from public.learners l
            join public.dataset_uploads d on d.id = l.dataset_id
            join public.workspaces w on w.id = d.workspace_id
            join public.profiles p on p.id = w.admin_user_id
            where l.id = learner_features.learner_id
              and d.owner_id = (select auth.uid())
              and w.admin_user_id = (select auth.uid())
              and w.status = 'active'
              and p.role = 'admin'
              and p.approval_status = 'approved'
        )
    );

drop policy if exists predictions_select_dataset_owner on public.predictions;
create policy predictions_select_dataset_owner on public.predictions
    for select to authenticated using (
        exists (
            select 1 from public.learners l
            join public.dataset_uploads d on d.id = l.dataset_id
            join public.workspaces w on w.id = d.workspace_id
            join public.profiles p on p.id = w.admin_user_id
            where l.id = predictions.learner_id
              and d.owner_id = (select auth.uid())
              and w.admin_user_id = (select auth.uid())
              and w.status = 'active'
              and p.role = 'admin'
              and p.approval_status = 'approved'
        )
    );

drop policy if exists risk_explanations_select_dataset_owner on public.risk_explanations;
create policy risk_explanations_select_dataset_owner on public.risk_explanations
    for select to authenticated using (
        exists (
            select 1 from public.predictions prediction
            join public.learners learner on learner.id = prediction.learner_id
            join public.dataset_uploads dataset on dataset.id = learner.dataset_id
            join public.workspaces w on w.id = dataset.workspace_id
            join public.profiles p on p.id = w.admin_user_id
            where prediction.id = risk_explanations.prediction_id
              and dataset.owner_id = (select auth.uid())
              and w.admin_user_id = (select auth.uid())
              and w.status = 'active'
              and p.role = 'admin'
              and p.approval_status = 'approved'
        )
    );

drop policy if exists recommendations_select_dataset_owner on public.recommendations;
create policy recommendations_select_dataset_owner on public.recommendations
    for select to authenticated using (
        exists (
            select 1 from public.learners l
            join public.dataset_uploads d on d.id = l.dataset_id
            join public.workspaces w on w.id = d.workspace_id
            join public.profiles p on p.id = w.admin_user_id
            where l.id = recommendations.learner_id
              and d.owner_id = (select auth.uid())
              and w.admin_user_id = (select auth.uid())
              and w.status = 'active'
              and p.role = 'admin'
              and p.approval_status = 'approved'
        )
    );

commit;
