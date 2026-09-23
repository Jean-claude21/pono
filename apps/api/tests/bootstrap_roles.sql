-- Test database roles, mirroring production (research R-02).
-- pono_owner owns the schema and runs migrations; like the Neon owner role it bypasses RLS,
-- which the two SECURITY DEFINER lookups rely on. pono_app serves requests under RLS.
DO $$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'pono_owner') THEN
    CREATE ROLE pono_owner LOGIN BYPASSRLS PASSWORD 'pono_owner';
  END IF;
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'pono_app') THEN
    CREATE ROLE pono_app LOGIN PASSWORD 'pono_app' NOBYPASSRLS;
  END IF;
END
$$;

GRANT CREATE, USAGE ON SCHEMA public TO pono_owner;
GRANT USAGE ON SCHEMA public TO pono_app;
ALTER DATABASE pono_test OWNER TO pono_owner;
