BEGIN;

ALTER TABLE public.users
    ADD COLUMN IF NOT EXISTS session_version INTEGER NOT NULL DEFAULT 0;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'public'
            AND table_name = 'audit_events'
            AND column_name = 'user_id'
    ) THEN
        LOCK TABLE public.audit_events IN ACCESS EXCLUSIVE MODE;

        IF EXISTS (SELECT 1 FROM public.audit_events WHERE user_id IS NOT NULL) THEN
            RAISE EXCEPTION 'audit_events.user_id contains data. Review it before dropping it.';
        END IF;

        ALTER TABLE public.audit_events DROP COLUMN user_id;
    END IF;
END;
$$;

COMMIT;