SELECT 'CREATE DATABASE evolution OWNER app_user' WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'evolution')\gexec
