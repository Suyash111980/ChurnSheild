-- Permit an authenticated Admin to delete only datasets in their active workspace.
-- Dependent learner, feature, prediction, explanation, and recommendation rows
-- are removed atomically by the ON DELETE CASCADE foreign keys established by
-- migrations 001 and 005. This migration is intentionally not auto-applied.
drop policy if exists dataset_uploads_delete_owner on public.dataset_uploads;
create policy dataset_uploads_delete_owner on public.dataset_uploads
    for delete to authenticated using (
        owner_id = (select auth.uid())
        and workspace_id is not null
        and status <> 'processing'
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
