# Padel Club

## Overview

A small backend for a padel club of a few hundred members. In Assignment 1 it was one Flask app with one SQLite database. In Assignment 2 it is being split into two services, one per feature domain, each with its own database:

- **bookings** (`services/bookings/`): members register and log in, see the club's four courts, check a court's schedule for a day, book a 60 or 90 minute slot between 08:00 and 23:00, and cancel their own bookings. Double-bookings are rejected.
- **ladder** (`services/ladder/`): members join the ladder under a nickname, record doubles matches they played in, and climb a leaderboard ranked by Elo rating (everyone starts at 1000).

Login lives in the bookings service. It returns a signed token, and the browser sends it to both services in the `Authorization: Bearer <token>` header. Both services check the token with the same `TOKEN_SECRET`, so the ladder knows who is logged in without calling bookings.

One request crosses between the services. When a member joins the ladder, the ladder calls `GET /auth/me` on bookings with the member's own token, to check the account exists and to get the username (used as the nickname if none is given). The ladder finds bookings through `BOOKINGS_URL` and waits at most `BOOKINGS_TIMEOUT_S` seconds. If bookings is down or too slow, joining returns `503` with a message to try again, and everything else in the ladder keeps working. See ADR-6.

```
services/
  bookings/   app.py, padel/auth, padel/bookings, migrations/, tests/, openapi.yaml, Dockerfile, requirements.txt
  ladder/     app.py, padel/ladder, padel/auth (token check only), migrations/, tests/, openapi.yaml, Dockerfile, requirements.txt
ui/                   the static web page: index.html, app.js, style.css, config.js
db/init.sql           creates the two local databases and their logins
docker-compose.yml    the whole system on one machine
.github/workflows/    ci.yml: the checks every push and pull request must pass
ruff.toml             lint settings for both services
```

Each service keeps its data in its own SQL Server database (`bookings` or `ladder`) and logs in with its own user, which cannot open the other database.

## Run with Docker Compose

You need Docker Desktop. On an Apple-chip Mac, SQL Server runs through Rosetta (Settings → General → "Use Rosetta for x86_64/amd64 emulation", on by default).

First make your `.env` file. It holds the passwords and is ignored by Git:

```bash
cp .env.example .env
echo "Pw1-$(openssl rand -hex 16)"    # run three times: one password each for MSSQL_SA, BOOKINGS_DB, LADDER_DB
openssl rand -hex 32                  # for TOKEN_SECRET
```

Paste the values into `.env`, then start everything:

```bash
docker compose up --build
```

This starts SQL Server, runs `db/init.sql` once it is ready (it creates the databases and logins, and is safe to run again), then starts the two services. Each service applies its own migrations when it starts. Open the UI at <http://localhost:8080>. The bookings service is on `localhost:8001` and the ladder on `localhost:8002`; check them with `curl localhost:8001/health` and `curl localhost:8002/health`.

`docker compose down` stops everything and keeps the data. `docker compose down -v` also deletes the database volume, so only use it when you want to start from empty.

Never commit a real secret. Real values only live in the local `.env` file (ignored by Git) or in GitHub Actions secrets.

## Run one service without Docker

Requires Python 3.12+ and a running SQL Server (for example `docker compose up -d db db-init`).

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r services/bookings/requirements-dev.txt -r services/ladder/requirements-dev.txt
set -a && source .env && set +a      # load the passwords from .env into this terminal

cd services/bookings
DATABASE_URL="mssql://bookings_user:$BOOKINGS_DB_PASSWORD@localhost:1433/bookings" PORT=8001 python app.py
```

## Database migrations

Each service has a `migrations/` folder with numbered SQL files (`001_init.sql`, `002_...`). On start, the service runs the files it has not run before, in order, and records each one in its `schema_migrations` table. A second start applies nothing. Each file runs in one transaction, so a failing migration changes nothing. Applied files are never edited; a fix goes in a new file.

## Configuration

Each service reads:

| Variable       | Default | Purpose |
|----------------|---------|---------|
| `PORT`         | `8000`  | Port the service listens on (binds to 0.0.0.0) |
| `DATABASE_URL` | none, required, secret | The service's own database, as `mssql://user:password@host:1433/database` |
| `TOKEN_SECRET` | none, required, secret | Signs and checks login tokens. Must be the same in both services |
| `CORS_ORIGIN`  | `http://localhost:8080` | The UI's origin, the only website allowed to call the service from a browser |
| `GIT_SHA`      | `dev` | The commit the image was built from, shown by `/health`. Set at build time with `--build-arg GIT_SHA=<sha>` |

The ladder service also reads:

| Variable             | Default | Purpose |
|----------------------|---------|---------|
| `BOOKINGS_URL`       | `http://bookings:8000` | Base URL of the bookings service |
| `BOOKINGS_TIMEOUT_S` | `3` | Seconds to wait for bookings before joining fails with `503` |

A service refuses to start if `DATABASE_URL` or `TOKEN_SECRET` is missing.

## The UI

`ui/` is a plain HTML, CSS and JavaScript page with no framework and no build step. Compose serves the folder as it is with the stock `nginx:1.30.0-alpine` image on port 8080, so the UI is not one of the two service containers. The page runs in the browser and calls both services itself: bookings for login, courts and bookings, the ladder for everything under `/ladder`. Each service accepts browser calls only from `CORS_ORIGIN`, which is `http://localhost:8080` locally.

The page reads the two service URLs from `ui/config.js`. The committed file points at `localhost:8001` and `localhost:8002`; the deploy pipeline writes a new `config.js` with the Azure URLs, so no URL is written into `app.js`. The login token is kept in the browser's `sessionStorage`, so closing the tab logs you out.

If one service is down, only its half of the page shows "not reachable right now"; the other half keeps working. Every call from the page gives up after 10 seconds.

## API

Each service describes its API in `openapi.yaml` (OpenAPI 3.0): `services/bookings/openapi.yaml` and `services/ladder/openapi.yaml`. A test in each service fails if the document and the real routes ever differ.

All requests and responses are JSON. Every route except `/health`, `/auth/register` and `/auth/login` needs a valid token in the `Authorization: Bearer <token>` header, otherwise it returns `401`. Routes under `/auth`, `/courts` and `/bookings` are on the bookings service; routes under `/ladder` are on the ladder service.

| Method | Path | Body | What it does |
|--------|------|------|--------------|
| GET    | `/health` | | `200 {"status": "ok", "db": "ok", "version": "<git sha>"}` if the service can read and write its own database, otherwise `503` with `"error"` |
| POST   | `/auth/register` | `{"username", "password"}` | Create an account |
| POST   | `/auth/login` | `{"username", "password"}` | Log in, returns `{"id", "username", "token"}` |
| GET    | `/auth/me` | | The logged-in user, or `404` if the account no longer exists. The ladder also calls this |
| GET    | `/courts` | | List courts |
| GET    | `/courts/<id>/bookings?day=YYYY-MM-DD` | | A court's bookings for one day |
| POST   | `/bookings` | `{"court_id", "start_time": "YYYY-MM-DD HH:MM", "duration_minutes": 60 or 90}` | Book a court |
| GET    | `/bookings/mine` | | My bookings |
| DELETE | `/bookings/<id>` | | Cancel my booking |
| POST   | `/ladder/join` | `{"nickname"}` (optional) | Join the ladder. Calls bookings; `503` if bookings does not answer |
| GET    | `/ladder/me` | | My rating and matches played |
| POST   | `/ladder/matches` | `{"team_a": [id, id], "team_b": [id, id], "winner": "A" or "B"}` | Record a match I played in |
| GET    | `/ladder/leaderboard` | | Everyone, ranked by rating |

Errors come back as `{"error": "..."}` with `400` (broken rule), `401` (not logged in or wrong password), `404` (not found), `409` (court already booked) or `503` (joining the ladder while bookings is not answering).

### Example with curl

```bash
curl -X POST localhost:8001/auth/register -H "Content-Type: application/json" \
     -d '{"username": "nika", "password": "secret123"}'
TOKEN=$(curl -s -X POST localhost:8001/auth/login -H "Content-Type: application/json" \
     -d '{"username": "nika", "password": "secret123"}' | python3 -c 'import sys, json; print(json.load(sys.stdin)["token"])')
curl -X POST localhost:8001/bookings -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
     -d '{"court_id": 1, "start_time": "2030-06-01 18:00", "duration_minutes": 90}'
curl -X POST localhost:8002/ladder/join -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
     -d '{"nickname": "nika"}'
```

There is no logout route. Tokens are not stored on the server, so a client logs out by forgetting its token. Tokens expire after 12 hours.

## Health, logs and partial failure

`GET /health` on each service opens its own database, reads a row and writes one that is rolled back straight away. It answers `200` if that works and `503` if not, within about 5 seconds. It never calls the other service, so the ladder stays healthy while bookings is down.

Each service writes one log line per request to stdout, for example `INFO padel.requests POST /ladder/join 201 50ms`. See them with `docker compose logs -f ladder`.

To see a partial failure, stop one service with `docker compose stop bookings`. The ladder keeps serving the leaderboard, `/ladder/me` and new matches; only `POST /ladder/join` answers `503` with a message to try again. `docker compose start bookings` brings it back.

## Tests & Coverage

The tests run against a real SQL Server. Each run creates its own test database (`bookings_test` or `ladder_test`), wipes it and runs the migrations into it, so never point `TEST_DATABASE_URL` at a database with real data. With the compose SQL Server running (`docker compose up -d db`):

```bash
set -a && source .env && set +a
cd services/bookings && TEST_DATABASE_URL="mssql://sa:$MSSQL_SA_PASSWORD@localhost:1433/bookings_test" pytest --cov=padel --cov=app
cd services/ladder   && TEST_DATABASE_URL="mssql://sa:$MSSQL_SA_PASSWORD@localhost:1433/ladder_test"   pytest --cov=padel --cov=app
```

The ladder's tests replace the bookings service with a small fake HTTP server (`BookingsStub` in `services/ladder/tests/conftest.py`). It can answer normally, answer 404 or 500, answer too slowly, or be switched off, so the tests cover every way the call to bookings can fail.

Latest result: bookings 115 tests, ladder 87 tests, both at 99% coverage (the only line missed in each is the `python app.py` start-up line). The business rules alone (each domain's `service.py`) are at 100%.

## Continuous integration

`.github/workflows/ci.yml` runs on every push to a branch and on every pull request. Each job is a separate check, and the run fails if any of them fails:

| Job | What it checks |
|---|---|
| Lint | `ruff check services`, with the settings in `ruff.toml` |
| Tests (bookings), Tests (ladder) | Each service's tests against its own SQL Server container, started fresh for the run. Fails below 70% coverage for the whole service, and again below 70% for its business rules (`padel/*/service.py`) alone |
| Validate API files | Both `openapi.yaml` files against the OpenAPI specification |
| Build image (bookings), Build image (ladder) | Each Dockerfile builds; the image is not pushed |
| Scan for secrets | gitleaks over every new commit in the push or pull request, not only the last one, so a secret removed in a later commit is still caught. Before pushing, `gitleaks git .` checks the whole history locally |

CI never connects to Azure. The test SQL Server gets a new random password on every run, hidden in the logs, so no password is written in the workflow. Checking `system.yaml` against `system.schema.json` will be added once the course publishes the schema.

Run the same lint and coverage checks locally (with the test database from above):

```bash
pip install ruff==0.17.3 && ruff check services
cd services/bookings && pytest --cov=padel --cov=app --cov-fail-under=70 && coverage report --include="padel/*/service.py" --fail-under=70
```

## System description

`system.yaml` describes the whole system in one file: the UI, both services, every environment variable each one reads, the ladder's call to bookings, and the Azure name of every resource. CI checks it against `system.schema.json`, the schema given by the course. Each service's `tests/test_system_yaml.py` checks that it still matches the code: the same environment variables with the same defaults, paths that exist, and a call to bookings that matches bookings' `openapi.yaml`.

## Azure setup (done once)

The system runs in my own Azure for Students subscription. It has no credit card, so it can never be charged: when the credit runs out, the resources stop. These are the commands I ran to set it up, in order. After this, only the deploy pipeline changes anything. No password appears here: they were made with `openssl` into `.env.azure` (ignored by Git) and piped straight into GitHub secrets.

**1. Subscription and region.** The subscription only allows five regions, so I listed them first:

```bash
az login                                   # picked "Azure for Students"
az account set --subscription "Azure for Students"
az policy assignment list --query "[].{name:displayName, params:parameters}" -o json
# allowed: belgiumcentral, switzerlandnorth, polandcentral, austriaeast, spaincentral
```

Everything except the UI storage is in **Poland Central**. Switzerland North refused new SQL servers for this subscription ("RegionDoesNotAllowProvisioning"), and of the other four regions only Poland Central offers the free SQL database. The services are in the same region as their databases, so each query stays inside one data centre. I checked both with:

```bash
sub=$(az account show --query id -o tsv)
az rest --method get --url "https://management.azure.com/subscriptions/$sub/providers/Microsoft.Sql/locations/polandcentral/capabilities?api-version=2023-08-01" --query "{status:status, reason:reason}"
```

**2. Providers and resource group.**

```bash
for ns in Microsoft.App Microsoft.OperationalInsights Microsoft.Sql Microsoft.Storage Microsoft.ManagedIdentity; do az provider register --namespace $ns; done
az group create --name rg-nchachia-ieu2024 --location switzerlandnorth -o table
```

**3. The UI: a Storage static website.** Its address, https://nchachiaieu2024ui.z1.web.core.windows.net, is the system's public URL and the only origin the services accept (`CORS_ORIGIN`).

```bash
az storage account create --name nchachiaieu2024ui --resource-group rg-nchachia-ieu2024 --location switzerlandnorth --sku Standard_LRS --kind StorageV2 --allow-blob-public-access false -o table
az storage account update --name nchachiaieu2024ui --resource-group rg-nchachia-ieu2024 --min-tls-version TLS1_2 -o none
az storage blob service-properties update --account-name nchachiaieu2024ui --static-website --index-document index.html
az storage account show --name nchachiaieu2024ui --resource-group rg-nchachia-ieu2024 --query primaryEndpoints.web -o tsv
```

**4. SQL server and the two serverless databases.** One server, one database per service, both serverless on the free offer: $0, and if the free monthly amount ran out they would pause instead of charging (`AutoPause`). The firewall rule `0.0.0.0` means "allow Azure services", so the Container Apps can connect.

The server is called `nchachia-ieu2024-sql2`, not `nchachia-ieu2024-sql`. My first attempt was in Switzerland North and was refused, but Azure kept a hidden record of it. For over 25 minutes every new try said the name "already exists in location switzerlandnorth", although no such server existed. So I gave it a new name, which still starts with the prefix.

```bash
set -a; source .env.azure; set +a          # loads the passwords without printing them
az sql server create --name nchachia-ieu2024-sql2 --resource-group rg-nchachia-ieu2024 --location polandcentral --admin-user padeladmin --admin-password "$AZURE_SQL_ADMIN_PASSWORD" --minimal-tls-version 1.2 -o table
az sql server firewall-rule create --resource-group rg-nchachia-ieu2024 --server nchachia-ieu2024-sql2 --name AllowAzureServices --start-ip-address 0.0.0.0 --end-ip-address 0.0.0.0 -o table
az sql db create --resource-group rg-nchachia-ieu2024 --server nchachia-ieu2024-sql2 --name nchachia-ieu2024-bookings-db --edition GeneralPurpose --compute-model Serverless --family Gen5 --capacity 1 --min-capacity 0.5 --backup-storage-redundancy Local --use-free-limit true --free-limit-exhaustion-behavior AutoPause -o table
az sql db create --resource-group rg-nchachia-ieu2024 --server nchachia-ieu2024-sql2 --name nchachia-ieu2024-ladder-db --edition GeneralPurpose --compute-model Serverless --family Gen5 --capacity 1 --min-capacity 0.5 --backup-storage-redundancy Local --use-free-limit true --free-limit-exhaustion-behavior AutoPause -o table
az sql db list --resource-group rg-nchachia-ieu2024 --server nchachia-ieu2024-sql2 --query "[?name!='master'].{name:name, free:useFreeLimit, whenUsedUp:freeLimitExhaustionBehavior}" -o table
```

Then one contained user per database, which exists only inside its own database and can run the migrations (`db_ddladmin`, `db_datareader`, `db_datawriter`). `sqlcmd` runs from the SQL Server Docker image. The firewall is opened to my own address only for this and closed again afterwards; a new rule can take up to five minutes to apply, and connections before that are refused.

```bash
my_ip=$(curl -s https://api.ipify.org)
az sql server firewall-rule create --resource-group rg-nchachia-ieu2024 --server nchachia-ieu2024-sql2 --name setup-from-my-mac --start-ip-address "$my_ip" --end-ip-address "$my_ip" -o none
# wait about five minutes
docker run --rm --platform linux/amd64 -e SQLCMDPASSWORD="$AZURE_SQL_ADMIN_PASSWORD" mcr.microsoft.com/mssql/server:2022-latest /opt/mssql-tools18/bin/sqlcmd -S tcp:nchachia-ieu2024-sql2.database.windows.net,1433 -U padeladmin -d nchachia-ieu2024-bookings-db -N -b -Q "CREATE USER bookings_user WITH PASSWORD = '$AZURE_BOOKINGS_DB_PASSWORD'; ALTER ROLE db_ddladmin ADD MEMBER bookings_user; ALTER ROLE db_datareader ADD MEMBER bookings_user; ALTER ROLE db_datawriter ADD MEMBER bookings_user;"
docker run --rm --platform linux/amd64 -e SQLCMDPASSWORD="$AZURE_SQL_ADMIN_PASSWORD" mcr.microsoft.com/mssql/server:2022-latest /opt/mssql-tools18/bin/sqlcmd -S tcp:nchachia-ieu2024-sql2.database.windows.net,1433 -U padeladmin -d nchachia-ieu2024-ladder-db -N -b -Q "CREATE USER ladder_user WITH PASSWORD = '$AZURE_LADDER_DB_PASSWORD'; ALTER ROLE db_ddladmin ADD MEMBER ladder_user; ALTER ROLE db_datareader ADD MEMBER ladder_user; ALTER ROLE db_datawriter ADD MEMBER ladder_user;"

# Check: each user gets into its own database, and is refused by the other one ("Login failed").
docker run --rm --platform linux/amd64 -e SQLCMDPASSWORD="$AZURE_BOOKINGS_DB_PASSWORD" mcr.microsoft.com/mssql/server:2022-latest /opt/mssql-tools18/bin/sqlcmd -S tcp:nchachia-ieu2024-sql2.database.windows.net,1433 -U bookings_user -d nchachia-ieu2024-bookings-db -N -b -Q "SELECT DB_NAME() AS my_database, USER_NAME() AS me"
docker run --rm --platform linux/amd64 -e SQLCMDPASSWORD="$AZURE_BOOKINGS_DB_PASSWORD" mcr.microsoft.com/mssql/server:2022-latest /opt/mssql-tools18/bin/sqlcmd -S tcp:nchachia-ieu2024-sql2.database.windows.net,1433 -U bookings_user -d nchachia-ieu2024-ladder-db -N -b -Q "SELECT 1"
docker run --rm --platform linux/amd64 -e SQLCMDPASSWORD="$AZURE_LADDER_DB_PASSWORD" mcr.microsoft.com/mssql/server:2022-latest /opt/mssql-tools18/bin/sqlcmd -S tcp:nchachia-ieu2024-sql2.database.windows.net,1433 -U ladder_user -d nchachia-ieu2024-ladder-db -N -b -Q "SELECT DB_NAME() AS my_database, USER_NAME() AS me"

az sql server firewall-rule delete --resource-group rg-nchachia-ieu2024 --server nchachia-ieu2024-sql2 --name setup-from-my-mac
```

**5. Container Apps.** Both start with Microsoft's placeholder image; the first deploy replaces it. They scale to zero when idle (`--min-replicas 0`). The database connection, `TOKEN_SECRET`, `CORS_ORIGIN` and `BOOKINGS_URL` are not set here: the deploy workflow sets them on every deploy, the secrets from GitHub secrets as Container Apps secrets.

```bash
az extension add --name containerapp --upgrade
az containerapp env create --name nchachia-ieu2024-env --resource-group rg-nchachia-ieu2024 --location polandcentral -o table
az containerapp create --name nchachia-ieu2024-bookings --resource-group rg-nchachia-ieu2024 --environment nchachia-ieu2024-env --image mcr.microsoft.com/k8se/quickstart:latest --target-port 8000 --ingress external --min-replicas 0 --max-replicas 1 --cpu 0.25 --memory 0.5Gi --query properties.configuration.ingress.fqdn -o tsv
az containerapp create --name nchachia-ieu2024-ladder --resource-group rg-nchachia-ieu2024 --environment nchachia-ieu2024-env --image mcr.microsoft.com/k8se/quickstart:latest --target-port 8000 --ingress external --min-replicas 0 --max-replicas 1 --cpu 0.25 --memory 0.5Gi --query properties.configuration.ingress.fqdn -o tsv
```

Their addresses:
- bookings: https://nchachia-ieu2024-bookings.salmonplant-4fba6716.polandcentral.azurecontainerapps.io
- ladder: https://nchachia-ieu2024-ladder.salmonplant-4fba6716.polandcentral.azurecontainerapps.io

**6. The pipeline's identity.** GitHub Actions signs in as this managed identity with OIDC, so no Azure password exists anywhere. It is Contributor on this resource group only. GitHub sends this repository's subject with numeric IDs, so both forms are registered. They are in single quotes so zsh cannot change them.

```bash
az identity create --name nchachia-ieu2024-github --resource-group rg-nchachia-ieu2024 --location polandcentral -o none
principal=$(az identity show --name nchachia-ieu2024-github --resource-group rg-nchachia-ieu2024 --query principalId -o tsv)
rg_id=$(az group show --name rg-nchachia-ieu2024 --query id -o tsv)
az role assignment create --assignee-object-id "$principal" --assignee-principal-type ServicePrincipal --role Contributor --scope "$rg_id" -o none
gh api repos/nika140906/padel-club/actions/oidc/customization/sub    # shows the subject format GitHub uses
az identity federated-credential create --name github-main --identity-name nchachia-ieu2024-github --resource-group rg-nchachia-ieu2024 --issuer https://token.actions.githubusercontent.com --audiences api://AzureADTokenExchange --subject 'repo:nika140906/padel-club:ref:refs/heads/main' -o none
az identity federated-credential create --name github-main-ids --identity-name nchachia-ieu2024-github --resource-group rg-nchachia-ieu2024 --issuer https://token.actions.githubusercontent.com --audiences api://AzureADTokenExchange --subject 'repo:nika140906@233967632/padel-club@1391312057:ref:refs/heads/main' -o none
az identity federated-credential list --identity-name nchachia-ieu2024-github --resource-group rg-nchachia-ieu2024 --query "[].subject" -o tsv
```

**7. GitHub secrets and variables.** Each value goes from `az`, `openssl` or `.env.azure` straight into GitHub through a pipe, so it is never shown or written to a tracked file.

```bash
# made once:  { echo "AZURE_SQL_ADMIN_PASSWORD=Pw1-$(openssl rand -hex 16)"; ... } > .env.azure
az identity show --name nchachia-ieu2024-github --resource-group rg-nchachia-ieu2024 --query clientId -o tsv | gh secret set AZURE_CLIENT_ID
az account show --query tenantId -o tsv | gh secret set AZURE_TENANT_ID
az account show --query id -o tsv | gh secret set AZURE_SUBSCRIPTION_ID
openssl rand -hex 32 | gh secret set TOKEN_SECRET
grep '^AZURE_BOOKINGS_DB_PASSWORD=' .env.azure | cut -d= -f2- | tr -d '\n' | gh secret set BOOKINGS_DB_PASSWORD
grep '^AZURE_LADDER_DB_PASSWORD=' .env.azure | cut -d= -f2- | tr -d '\n' | gh secret set LADDER_DB_PASSWORD
gh variable set PREFIX --body nchachia-ieu2024
gh variable set RESOURCE_GROUP --body rg-nchachia-ieu2024
gh variable set UI_STORAGE --body nchachiaieu2024ui
```

**9. Read access for the professors.**

```bash
az role assignment create --assignee amartini@faculty.ie.edu --role Reader --scope "$rg_id" -o none
az role assignment create --assignee bserra@faculty.ie.edu --role Reader --scope "$rg_id" -o none
```
