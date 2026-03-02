-- Create separate database for SuperTokens
-- This runs on first postgres container startup
-- (assethost database is created by POSTGRES_DB env var)

-- Create supertokens database
CREATE DATABASE supertokens;

-- Grant permissions to default postgres user
GRANT ALL PRIVILEGES ON DATABASE supertokens TO postgres;
