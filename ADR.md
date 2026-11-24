# Architecture Decision Records

Decisions are added here as they are made. Each entry uses this format:

```
## [N]. <Title>
Date: YYYY-MM-DD
Status: Decided
Context: 1-3 sentences, what forced this decision
Decision: 1-2 sentences, what you chose
Alternatives considered: at least one real alternative, and why you rejected it
Consequences: 1-2 sentences, what this costs or enables later
```

## 1. Use Flask as the backend web framework
Date: 2026-09-28

Status: Decided

Context: The padel club app needs an HTTP layer for two domains (Court Bookings and Match Ladder), running as a single process with SQLite for a club of a few hundred members. The brief asks for a justified framework choice and warns against tools the app does not need.

Decision: Use Flask, started with `python app.py`, because it is a single dependency with explicit routing and a built-in test client, so every part of the request handling is code I write and can explain.

Alternatives considered: FastAPI. It gives automatic request validation (Pydantic) and generated API docs, but it needs extra packages (fastapi, uvicorn, and httpx for testing), and its main strengths, async concurrency and auto-docs, are not needed for a small single-process app. Django was not considered seriously because its ORM, admin and project structure are far more than two small domains need.

Consequences: The app stays small, with one framework dependency and a test client that runs without starting a server. The cost is that input validation is written by hand, and Flask's built-in server is only a development server, so a production WSGI server may be needed when the app is deployed in Assignment 2.

## 2. Split the code into auth, bookings and ladder modules that share nothing but user ids
Date: 2026-09-29

Status: Decided

Context: The app has two feature domains, Court Bookings and Match Ladder, and the professor made authentication mandatory. In Assignment 2 the app will be split into services, so each domain needs a clear boundary now, even though everything still runs in one process.

Decision: Each domain is its own Python package under `padel/` (`auth/`, `bookings/`, `ladder/`) and owns its own tables in its own `schema.py`. Bookings and ladder never import each other's code or read each other's tables; from auth they only use the logged-in user's id, a plain integer, and auth's login check.

Alternatives considered: A single `models.py` and `routes.py` for the whole app. It would be quicker to start, but bookings and ladder code would mix together, and splitting them later would mean untangling shared files and queries. Putting auth inside one of the two domains was also rejected, because both domains need logged-in users.

Consequences: Each package can later become its own service by moving its folder and its tables, with `padel/db.py` as the only shared piece. The cost is some repetition, and checks such as "does this user exist" must be done in code instead of by the database.

## 3. Give each domain its own tables with no foreign keys across domains
Date: 2026-09-29

Status: Decided

Context: The schema needs five tables: `users` (auth), `courts` and `bookings` (bookings), and `players` and `matches` (ladder). Bookings and matches both refer to users, and the way they refer to them decides how hard the later split into services will be.

Decision: Foreign keys are used only inside a domain (`bookings.court_id` → `courts.id`, and the four match player columns → `players.user_id`). References to users from other domains (`bookings.user_id`, `players.user_id`, `matches.recorded_by`) are plain integers without a FOREIGN KEY. Matches are doubles, so `matches` has four player columns (`team_a_p1`, `team_a_p2`, `team_b_p1`, `team_b_p2`) and a `winner` of 'A' or 'B'. Times are stored as ISO text such as "2026-10-01 18:00".

Alternatives considered: Foreign keys from `bookings` and `players` to `users`. The database would guarantee every user id is valid, but it would tie both domains to the auth tables, so they could not move to a separate database later. A `match_players` join table (one row per player per match) was also rejected, because a padel match always has exactly four players and four columns are simpler to query and explain.

Consequences: Each domain's tables can be moved to their own database without breaking constraints. The cost is that the code must check that user ids are valid, and a deleted user can leave old bookings or matches pointing to an id that no longer exists.

## 4. Test the business rules directly against a real SQLite file, and the routes only for status codes and login
Date: 2026-10-01

Status: Decided

Context: The brief asks for at least 70% coverage of the core business logic of both domains. The rules that matter most are in each domain's `service.py` (booking overlaps, opening hours, Elo maths, who may cancel or record a match), while the routes only translate HTTP into those calls.

Decision: Most tests call the `service.py` functions directly, using a fresh SQLite file per test in pytest's `tmp_path` instead of mocking the database, and pass in a fixed `now` so date rules do not depend on the day the tests run. Route tests use Flask's test client and only check what the routes add: login required (401) and the status codes 201, 400, 404 and 409.

Alternatives considered: Testing everything through the HTTP routes. It would reach the same lines, but a failing test would not show which rule broke, and every rule would need a login first. Mocking the database was also rejected, because many rules (overlaps, uniqueness, CHECK constraints) live in SQL and a mock would not run that SQL.

Consequences: Coverage is about 99% and each rule has a test named after it, so a failure points straight at the broken rule. Left thinner: the `python app.py` start-up lines, and two members booking the same slot at the exact same moment, which these single-request tests cannot reproduce.

## 5. Do not build a web frontend; ship a JSON API only
Date: 2026-10-03

Status: Superseded by [6]

Context: Club members will eventually want pages to book courts and see the leaderboard, but the assignment had one week, and the grade rests on the two backend domains, their tests and the design records. The choice was made on 2026-09-29, before the routes were written, and is recorded here now that both domains are finished.

Decision: The app is a JSON API only. There are no HTML pages, templates, CSS or JavaScript; the features are used with curl, as shown in the README, or through Flask's test client.

Alternatives considered: Simple HTML pages with Flask templates (a login page, a booking page and a leaderboard page). They would make the app easier to demo, but they would add around 6-8 template files, form handling and more routes to test, taking time away from the booking rules, the Elo logic and their tests.

Consequences: All the time went into the two domains, auth and tests (110 tests, 99% coverage), and the API is ready for any frontend or for other services to call when the app is split up later. The cost is that a real member cannot use the app without a separate frontend, which would be the next thing to build.

## 6. Split into a bookings service that owns login and a ladder service, with one server-side call when a member joins
Date: 2026-11-17

Status: Decided

Context: Assignment 2 allows exactly two service containers, one per domain, but ADR-2 had three modules: auth, bookings and ladder. Each service now has its own database, so ADR-3's "check user ids in code" must happen over HTTP, and at least one user-visible flow must cross the seam on the server and survive the other service being down.

Decision: The seam from ADR-2 held: bookings and ladder share nothing but user ids, auth moved into the bookings service, and the ladder only checks login tokens with the shared `TOKEN_SECRET`. The one server-side crossing is `POST /ladder/join`: the ladder calls `GET /auth/me` on bookings with the member's own token (3 second timeout, `BOOKINGS_TIMEOUT_S`) to confirm the account and get the username, and answers `503` with "try again in a minute" if bookings fails; everything else, including a static UI in `ui/` calling both services from the browser (which replaces ADR-5), needs no call between services.

Alternatives considered: Auth as its own service was rejected, because only two containers are allowed and every request would have to ask it who is logged in, which signed tokens avoid. Doing the join flow in the browser (fetch the username from bookings, send it to the ladder) was rejected, because the ladder would have to trust a username the browser sent. Degrading instead of failing (let the member join unchecked while bookings is down) was rejected, because the ladder would store players nobody verified, and joining happens once and is easy to retry; retrying inside the ladder was rejected too, since it makes the member wait longer for the same answer.

Consequences: Only joining depends on bookings; the leaderboard, `/ladder/me` and recording matches keep working with bookings stopped. The costs: the nickname is a copy that does not follow later account changes, a cold bookings container on Azure may make the first join fail (the member has usually just logged in, so bookings is awake), and the timeout covers connecting and reading but not the name lookup, so in compose a stopped bookings takes about 4 seconds to fail.

## 7. Start each service's SQL Server database from numbered migrations run by my own runner, and recover from a bad migration by moving forward
Date: 2026-11-18

Status: Decided

Context: The single SQLite file of Assignment 1 had to become one SQL Server database per service, and from now on the schema must change in place without losing rows. Splitting the data also breaks the last link ADR-3 kept: `bookings.user_id`, `players.user_id` and `matches.recorded_by` now point at a `users` table in another database, so not even a same-database check is possible.

Decision: Each service has a `migrations/` folder of numbered SQL files (`001_init.sql` is the SQLite schema ported to SQL Server, with `INT IDENTITY` ids and `DATETIME2` times instead of ADR-3's ISO text, while the API still sends text). `padel/migrate.py` runs the files it has not run yet at startup, each in one transaction together with its row in `schema_migrations`; applied files are never edited and a fix is always a new file. No rows were moved, because the Assignment 1 database only ever held local test data; the user id links are checked in code instead: user ids only come from signed tokens, joining the ladder confirms the account with bookings (ADR-6), and the four players of a match must already be on the ladder (a foreign key inside the ladder database).

Alternatives considered: Alembic was rejected, because it needs SQLAlchemy and its own revision files on top of the raw SQL the services already use, while the runner is about 60 lines I can explain. Copying the Assignment 1 rows into the new databases with a one-off script (keeping the ids with `IDENTITY_INSERT`) was rejected because there were no real members to keep; it is what I would do if there were. Down-migrations were rejected as well, since an untested undo script is riskier in production than a reviewed fix.

Consequences: A migration that fails rolls back completely, the container does not start, and the post-deploy health check fails the pipeline; the recovery is to redeploy the previous image tag, then fix the migration in a new file. A migration that runs but damages data is fixed with a new migration, or as a last resort by restoring the Azure SQL database to a point in time from its automatic backups. Lost for good: if a member's account disappeared, their ladder rows would stay behind as orphans, which is acceptable because no route deletes accounts.

## 8. Deploy from GitHub Actions with OIDC to scale-to-zero Container Apps and free serverless databases, and wait out cold starts with retries
Date: 2026-11-24

Status: Decided

Context: The system must run on Azure in my Azure for Students subscription, which has a fixed credit and no card, and every change to `main` must reach Azure through the pipeline only. Keeping it almost free means everything sleeps when idle, so the first request after a quiet period finds both the container and its database asleep, and the database refuses connections (error 40613, or pymssql's 20002/20003) for about a minute while it resumes.

Decision: `deploy.yml` runs all of CI on the commit, pushes SHA-tagged images to GHCR, signs in to Azure as a managed identity with OIDC (Contributor on the resource group only), and points both Container Apps (0 to 1 replicas) at the new images, with the database URL and `TOKEN_SECRET` as Container Apps secrets; it passes only when both `/health` checks report the new SHA. Each service retries a "not ready" connection with growing waits for about two minutes at startup (where the migrations run) and twice per request, and the UI shows "starting up, try again" for the 503 Azure gives meanwhile.

Alternatives considered: Azure Container Registry was rejected, because even the Basic tier costs credit every day while GHCR is free; the cost is that the two image packages must be public, which is fine since they hold only the code that is already public. A service principal with a client secret in GitHub was rejected, because IE accounts cannot create one and a stored secret can leak, while OIDC tokens last minutes and only work from `main` of this repository. Keeping one replica always running (`--min-replicas 1`) and a database that never pauses were rejected because they would use up the credit without real users; the price is a slow first request.

Consequences: An idle system costs almost nothing, and no Azure password exists anywhere. The cost: after an hour of no use, the first request waits about a minute and may get a 503 once, and a broken deploy is caught by the health check but not rolled back by itself; the fix is to revert the commit on `main`, which redeploys the previous code.
