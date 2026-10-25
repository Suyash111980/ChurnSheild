-- Master Admin request history, safe requester display data, and review audit.
-- Apply only after verifying migrations 001-006 and auth.users compatibility.
begin;

alter table public.profiles
    add column if not exists reviewed_at timestamptz,
    add column if not exists reviewed_by uuid references public.profiles(id) on delete set null,
    add column if not exists rejection_reason text;

create table if not exists public.admin_request_audit (
    id uuid primary key default gen_random_uuid(),
    request_user_id uuid references public.profiles(id) on delete set null,
    actor_user_id uuid references public.profiles(id) on delete set null,
    action text not null check (action in ('submitted', 'approved', 'rejected')),
    target_display_name text not null default 'Unknown user',
    target_email text,
    actor_display_name text,
    actor_email text,
    rejection_reason text,
    created_at timestamptz not null default now()
);
create index if not exists admin_request_audit_created_idx
    on public.admin_request_audit (created_at desc, id desc);
alter table public.admin_request_audit enable row level security;
revoke all on public.admin_request_audit from public, anon, authenticated;
grant select, insert on public.admin_request_audit to service_role;

create or replace function public.record_admin_request_submission()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
declare
    auth_user auth.users%rowtype;
    display_name text;
begin
    if new.requested_role is distinct from 'admin' then
        return new;
    end if;

    select * into auth_user from auth.users where id = new.id;
    display_name := coalesce(
        nullif(btrim(auth_user.raw_user_meta_data ->> 'full_name'), ''),
        nullif(btrim(auth_user.raw_user_meta_data ->> 'name'), ''),
        nullif(btrim(auth_user.raw_user_meta_data ->> 'display_name'), ''),
        nullif(btrim(auth_user.raw_user_meta_data ->> 'username'), ''),
        nullif(btrim(auth_user.email), ''),
        'Unknown user'
    );
    insert into public.admin_request_audit (
        request_user_id, action, target_display_name, target_email,
        actor_display_name, actor_email, created_at
    ) values (
        new.id, 'submitted', display_name, auth_user.email,
        display_name, auth_user.email, new.created_at
    ) on conflict do nothing;
    return new;
end;
$$;
revoke all on function public.record_admin_request_submission() from public, anon, authenticated;
drop trigger if exists admin_request_submission_audit on public.profiles;
create trigger admin_request_submission_audit
    after insert on public.profiles
    for each row when (new.requested_role = 'admin')
    execute function public.record_admin_request_submission();

-- Existing admin requests predate audit storage. Their profile creation time
-- is the request timestamp established by migration 006's Auth trigger.
insert into public.admin_request_audit (
    request_user_id, action, target_display_name, target_email,
    actor_display_name, actor_email, created_at
)
select
    p.id,
    'submitted',
    coalesce(
        nullif(btrim(u.raw_user_meta_data ->> 'full_name'), ''),
        nullif(btrim(u.raw_user_meta_data ->> 'name'), ''),
        nullif(btrim(u.raw_user_meta_data ->> 'display_name'), ''),
        nullif(btrim(u.raw_user_meta_data ->> 'username'), ''),
        nullif(btrim(u.email), ''),
        'Unknown user'
    ),
    u.email,
    coalesce(
        nullif(btrim(u.raw_user_meta_data ->> 'full_name'), ''),
        nullif(btrim(u.raw_user_meta_data ->> 'name'), ''),
        nullif(btrim(u.raw_user_meta_data ->> 'display_name'), ''),
        nullif(btrim(u.raw_user_meta_data ->> 'username'), ''),
        nullif(btrim(u.email), ''),
        'Unknown user'
    ),
    u.email,
    p.created_at
from public.profiles p
left join auth.users u on u.id = p.id
where p.requested_role = 'admin'
  and not exists (
      select 1 from public.admin_request_audit a
       where a.request_user_id = p.id and a.action = 'submitted'
  );

-- Join profiles to Auth only inside a narrowly granted service-role RPC. The
-- function returns an allow-listed name/email projection, never Auth metadata.
create or replace function public.master_list_admin_requests(
    status_filter text default 'pending',
    search_query text default null,
    date_from date default null,
    date_to date default null,
    sort_by text default 'newest',
    page_limit integer default 20,
    page_offset integer default 0
) returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
declare
    result jsonb;
begin
    if status_filter is null or status_filter not in ('pending', 'approved', 'rejected') then
        raise exception 'invalid_request_status';
    end if;
    if sort_by is null or sort_by not in ('newest', 'oldest', 'reviewed') then
        raise exception 'invalid_request_sort';
    end if;
    if page_limit < 1 or page_limit > 100 or page_offset < 0 then
        raise exception 'invalid_request_page';
    end if;
    if date_from is not null and date_to is not null and date_from > date_to then
        raise exception 'invalid_request_date_range';
    end if;

    with request_rows as (
        select
            p.id,
            p.role,
            p.requested_role,
            case p.approval_status when 'denied' then 'rejected' else p.approval_status end as status,
            p.created_at,
            p.reviewed_at,
            p.reviewed_by,
            p.rejection_reason,
            u.email,
            coalesce(
                nullif(btrim(u.raw_user_meta_data ->> 'full_name'), ''),
                nullif(btrim(u.raw_user_meta_data ->> 'name'), ''),
                nullif(btrim(u.raw_user_meta_data ->> 'display_name'), ''),
                nullif(btrim(u.raw_user_meta_data ->> 'username'), ''),
                nullif(btrim(u.email), ''),
                'Unknown user'
            ) as display_name,
            reviewer.email as reviewer_email,
            coalesce(
                nullif(btrim(reviewer.raw_user_meta_data ->> 'full_name'), ''),
                nullif(btrim(reviewer.raw_user_meta_data ->> 'name'), ''),
                nullif(btrim(reviewer.raw_user_meta_data ->> 'display_name'), ''),
                nullif(btrim(reviewer.raw_user_meta_data ->> 'username'), ''),
                nullif(btrim(reviewer.email), ''),
                'Unknown user'
            ) as reviewer_name
        from public.profiles p
        left join auth.users u on u.id = p.id
        left join public.profiles reviewer_profile on reviewer_profile.id = p.reviewed_by
        left join auth.users reviewer on reviewer.id = reviewer_profile.id
        where p.requested_role = 'admin'
          and p.approval_status in ('pending', 'approved', 'denied')
    ), filtered as (
        select * from request_rows r
         where (search_query is null or btrim(search_query) = '' or
                r.display_name ilike '%' || btrim(search_query) || '%' or
                coalesce(r.email, '') ilike '%' || btrim(search_query) || '%')
           and (date_from is null or r.created_at >= date_from::timestamptz)
           and (date_to is null or r.created_at < (date_to + 1)::timestamptz)
    ), selected_status as (
        select * from filtered where status = status_filter
    ), page as (
        select * from selected_status
         order by
           case when sort_by = 'oldest' then created_at end asc nulls last,
           case when sort_by = 'reviewed' then reviewed_at end desc nulls last,
           case when sort_by = 'reviewed' then created_at end desc nulls last,
           case when sort_by = 'newest' then created_at end desc nulls last,
           id
         limit page_limit offset page_offset
    ), totals as (
        select
            count(*)::integer as total,
            count(*) filter (where status = 'pending')::integer as pending,
            count(*) filter (where status = 'approved')::integer as approved,
            count(*) filter (where status = 'rejected')::integer as rejected
        from filtered
    )
    select jsonb_build_object(
        'data', coalesce((
            select jsonb_agg(jsonb_build_object(
                'id', p.id,
                'display_name', p.display_name,
                'email', p.email,
                'status', p.status,
                'created_at', p.created_at,
                'reviewed_at', p.reviewed_at,
                'reviewer_name', p.reviewer_name,
                'reviewer_email', p.reviewer_email,
                'rejection_reason', p.rejection_reason
            ) order by
                case when sort_by = 'oldest' then p.created_at end asc nulls last,
                case when sort_by = 'reviewed' then p.reviewed_at end desc nulls last,
                case when sort_by = 'reviewed' then p.created_at end desc nulls last,
                case when sort_by = 'newest' then p.created_at end desc nulls last,
                p.id)
            from page p
        ), '[]'::jsonb),
        'counts', jsonb_build_object(
            'pending', totals.pending,
            'approved', totals.approved,
            'rejected', totals.rejected
        ),
        'count', (select count(*)::integer from selected_status),
        'total', totals.total,
        'limit', page_limit,
        'offset', page_offset,
        'has_more', page_offset + (select count(*)::integer from page) <
                    (select count(*)::integer from selected_status),
        'activity', coalesce((
            select jsonb_agg(jsonb_build_object(
                'action', events.action,
                'target_display_name', events.target_display_name,
                'target_email', events.target_email,
                'actor_display_name', events.actor_display_name,
                'actor_email', events.actor_email,
                'rejection_reason', events.rejection_reason,
                'created_at', events.created_at
            ) order by events.created_at desc, events.id desc)
            from (
                select * from public.admin_request_audit
                 order by created_at desc, id desc
                 limit 10
            ) events
        ), '[]'::jsonb)
    ) into result
    from totals;
    return result;
end;
$$;
revoke all on function public.master_list_admin_requests(text, text, date, date, text, integer, integer)
    from public, anon, authenticated;
grant execute on function public.master_list_admin_requests(text, text, date, date, text, integer, integer)
    to service_role;

-- Require a still-pending request and an approved Admin reviewer under the
-- server-side Master Admin gate. The row update, workspace creation, and audit
-- insert happen in one function transaction.
drop function if exists public.master_review_admin_request(uuid, text);
create function public.master_review_admin_request(
    target_user_id uuid,
    decision text,
    reviewer_user_id uuid,
    review_reason text default null
) returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
declare
    target public.profiles%rowtype;
    reviewer public.profiles%rowtype;
    target_auth auth.users%rowtype;
    reviewer_auth auth.users%rowtype;
    assigned_workspace public.workspaces%rowtype;
    target_name text;
    reviewer_name text;
    final_status text;
begin
    if decision is null or decision not in ('approve', 'reject') then
        raise exception 'invalid_decision';
    end if;
    if review_reason is not null and length(review_reason) > 1000 then
        raise exception 'rejection_reason_too_long';
    end if;

    select * into target from public.profiles where id = target_user_id for update;
    if not found or target.requested_role is distinct from 'admin' then
        raise exception 'admin_request_not_found';
    end if;
    if target.approval_status is distinct from 'pending' then
        raise exception 'request_already_reviewed';
    end if;

    select * into reviewer from public.profiles where id = reviewer_user_id for share;
    if not found or reviewer.role is distinct from 'admin' or reviewer.approval_status is distinct from 'approved' then
        raise exception 'reviewer_not_approved_admin';
    end if;

    select * into target_auth from auth.users where id = target_user_id;
    select * into reviewer_auth from auth.users where id = reviewer_user_id;
    target_name := coalesce(
        nullif(btrim(target_auth.raw_user_meta_data ->> 'full_name'), ''),
        nullif(btrim(target_auth.raw_user_meta_data ->> 'name'), ''),
        nullif(btrim(target_auth.raw_user_meta_data ->> 'display_name'), ''),
        nullif(btrim(target_auth.raw_user_meta_data ->> 'username'), ''),
        nullif(btrim(target_auth.email), ''),
        'Unknown user'
    );
    reviewer_name := coalesce(
        nullif(btrim(reviewer_auth.raw_user_meta_data ->> 'full_name'), ''),
        nullif(btrim(reviewer_auth.raw_user_meta_data ->> 'name'), ''),
        nullif(btrim(reviewer_auth.raw_user_meta_data ->> 'display_name'), ''),
        nullif(btrim(reviewer_auth.raw_user_meta_data ->> 'username'), ''),
        nullif(btrim(reviewer_auth.email), ''),
        'Unknown user'
    );

    final_status := case when decision = 'approve' then 'approved' else 'denied' end;
    update public.profiles
       set role = case when decision = 'approve' then 'admin' else role end,
           approval_status = final_status,
           reviewed_at = now(),
           reviewed_by = reviewer_user_id,
           rejection_reason = case when decision = 'reject' then nullif(btrim(review_reason), '') else null end,
           updated_at = now()
     where id = target_user_id;

    if decision = 'approve' then
        insert into public.workspaces(admin_user_id)
        values (target_user_id)
        on conflict (admin_user_id) do nothing;
        select * into assigned_workspace from public.workspaces where admin_user_id = target_user_id;
    end if;

    insert into public.admin_request_audit (
        request_user_id, actor_user_id, action,
        target_display_name, target_email, actor_display_name, actor_email,
        rejection_reason
    ) values (
        target_user_id, reviewer_user_id,
        case when decision = 'approve' then 'approved' else 'rejected' end,
        target_name, target_auth.email, reviewer_name, reviewer_auth.email,
        case when decision = 'reject' then nullif(btrim(review_reason), '') else null end
    );

    return jsonb_build_object(
        'id', target_user_id,
        'role', case when decision = 'approve' then 'admin' else target.role end,
        'approval_status', final_status,
        'reviewed_at', now(),
        'reviewed_by', reviewer_user_id,
        'workspace_id', case when decision = 'approve' then assigned_workspace.id else null end
    );
end;
$$;
revoke all on function public.master_review_admin_request(uuid, text, uuid, text)
    from public, anon, authenticated;
grant execute on function public.master_review_admin_request(uuid, text, uuid, text)
    to service_role;

commit;
