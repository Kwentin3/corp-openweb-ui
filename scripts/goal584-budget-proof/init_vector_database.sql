-- Fresh disposable PostgreSQL only; native WebUI owns its vector tables.
-- Financial tables remain in goal584, and WebUI metadata remains in SQLite.
CREATE DATABASE goal584_vectors;
