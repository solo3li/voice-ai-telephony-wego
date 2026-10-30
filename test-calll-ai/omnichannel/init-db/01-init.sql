-- Create Evolution API database alongside Chatwoot
SELECT 'CREATE DATABASE evolution_db'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'evolution_db')\gexec
