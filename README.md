# Chat_With_Codebase

## Upstash Redis Storage

This project now stores ingestion-generated JSON artifacts in Upstash Redis instead of local `data/<repo>/...` JSON files.

Environment variables:

- `UPSTASH_REDIS_REST_URL`
- `UPSTASH_REDIS_REST_TOKEN`

Use `.env.example` as a template for local development.
