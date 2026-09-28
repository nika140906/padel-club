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
