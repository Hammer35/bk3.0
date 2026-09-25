# Production deployment

The production stack uses an immutable application image, external PostgreSQL,
internal Valkey, and Caddy for automatic HTTPS.

## Required external inputs

1. A public DNS record for `APP_DOMAIN` pointing to the server.
2. Ports 80 and 443 open for Caddy ACME validation.
3. PostgreSQL reachable only from the deployment server.
4. A versioned registry image in `BOOSTKLIENT_IMAGE`.
5. A long random `DJANGO_SECRET_KEY`, a distinct database password, and a GigaChat authorization key.

Copy `.env.production.example` to `.env.production`, replace placeholders, and
keep that file outside Git.

## Release procedure

1. Build and push a versioned image; do not deploy `latest`.
2. Validate: `docker compose --env-file .env.production -f compose.production.yaml config`
3. Start: `docker compose --env-file .env.production -f compose.production.yaml up -d`
4. Verify `https://APP_DOMAIN/health/ready/`, login, and onboarding.

The `migrate` service applies migrations and collects static files before web,
worker, beat, and Caddy start. PostgreSQL is intentionally external.

The image includes the Russian Trusted Root CA required by GigaChat. Keep TLS
verification enabled; set `GIGACHAT_CA_BUNDLE_FILE` only when your API project
requires a different trusted CA bundle.
