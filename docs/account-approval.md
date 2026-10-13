# Account approval and first Admin bootstrap

## Deployment

Apply `database/migrations/003_account_approval.sql` through the project's reviewed Supabase migration process after reviewing the SQL. This migration adds a nullable `profiles.approval_status`, constrains non-null values to `pending`, `approved`, or `denied`, and installs an Auth-user insert trigger. The trigger creates a profile with role `educator` and status `pending` for a new Auth user. If a profile with the same ID already exists, it leaves that profile unchanged; it does not read user metadata.

The migration deliberately has no default and does not update existing profile rows. Existing profiles therefore have `approval_status = NULL` after deployment and are blocked by backend authorization until an operator reviews and explicitly classifies them. Existing Auth users without profiles are not backfilled. The pending-users endpoint lists only rows explicitly marked `pending`.

Before any manual existing-user updates, inventory Auth users and profiles, verify each person's identity through the approved organization process, and record the role decision. To place one reviewed existing account into the approval queue, use its verified Auth UUID in a controlled SQL session:

```sql
insert into public.profiles (id, role, approval_status)
select id, 'educator', 'pending'
from auth.users
where id = 'REPLACE-WITH-VERIFIED-AUTH-UUID'
on conflict (id) do update
set approval_status = 'pending',
    updated_at = now();
```

This preserves any existing database role until an Admin approves the account and explicitly assigns its application role. Execute the statement separately for each reviewed account; do not run it as a bulk backfill.

## First Admin bootstrap

There is intentionally no public Admin-creation endpoint. After deploying the migration:

1. Have the designated initial administrator create an account through the normal Supabase signup flow and complete any required email confirmation.
2. Verify the person's identity and exact Auth email/UUID through the organization's approved process and Supabase Auth console.
3. As a trusted database operator, run the following one-time guarded statement in the Supabase SQL editor, replacing the placeholder with the verified email. It promotes only that user's pending profile and refuses to run if an approved Admin already exists.

```sql
do $$
declare
    target_id uuid;
begin
    perform pg_advisory_xact_lock(hashtext('churnshield-first-admin-bootstrap'));

    if exists (
        select 1 from public.profiles
        where role = 'admin' and approval_status = 'approved'
    ) then
        raise exception 'An approved Admin already exists';
    end if;

    select id into target_id
    from auth.users
    where lower(email) = lower('REPLACE-WITH-VERIFIED-ADMIN-EMAIL');

    if target_id is null then
        raise exception 'No Auth user matches the verified email';
    end if;

    update public.profiles
    set role = 'admin', approval_status = 'approved', updated_at = now()
    where id = target_id and approval_status = 'pending';

    if not found then
        raise exception 'The verified user has no pending profile';
    end if;
end
$$;
```

4. Confirm the single expected profile is approved with role `admin`, then sign in through the application. That Admin can review later pending accounts at **Account approvals**.

Keep this procedure restricted to a trusted operator and do not put the SQL editor credentials or service keys in source control or frontend configuration.

## Role values

The approval API accepts application roles and stores their existing database equivalents:

| Application role | `profiles.role` |
| --- | --- |
| Admin (`admin`) | `admin` |
| Retention Manager (`retention_manager`) | `educator` |
| Analyst (`data_analyst`) | `analyst` |

Denied users retain their current database role, but backend authorization rejects them because their approval status is not `approved`.
