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
