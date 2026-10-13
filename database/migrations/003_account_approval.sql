
-- ChurnShield Phase 2: account approval
-- New profiles are created for new Auth users as pending educators.
-- Existing profile rows remain NULL and require an explicit review decision.

ALTER TABLE public.profiles
    ADD COLUMN IF NOT EXISTS approval_status text;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'profiles_approval_status_check'
          AND conrelid = 'public.profiles'::regclass
    ) THEN
        ALTER TABLE public.profiles
            ADD CONSTRAINT profiles_approval_status_check
            CHECK (
                approval_status IS NULL
                OR approval_status IN ('pending', 'approved', 'denied')
            );
    END IF;
END
$$;

CREATE OR REPLACE FUNCTION public.create_pending_profile_for_new_auth_user()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $$
BEGIN
    -- Never consume role or approval values from user metadata.
    INSERT INTO public.profiles (id, role, approval_status)
    VALUES (NEW.id, 'educator', 'pending')
    ON CONFLICT (id) DO NOTHING;

    RETURN NEW;
END;
$$;

REVOKE ALL ON FUNCTION
    public.create_pending_profile_for_new_auth_user()
    FROM PUBLIC, anon, authenticated;

GRANT EXECUTE ON FUNCTION
    public.create_pending_profile_for_new_auth_user()
    TO supabase_auth_admin;

DROP TRIGGER IF EXISTS on_auth_user_created_create_profile
    ON auth.users;

CREATE TRIGGER on_auth_user_created_create_profile
    AFTER INSERT ON auth.users
    FOR EACH ROW
    EXECUTE FUNCTION public.create_pending_profile_for_new_auth_user();
