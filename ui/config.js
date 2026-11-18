// Where the two services are, for running locally with docker compose.
// The deploy pipeline replaces this file with one holding the Azure URLs,
// so the URLs are configuration and never written into app.js.
window.PADEL_CONFIG = {
  bookingsUrl: "http://localhost:8001",
  ladderUrl: "http://localhost:8002",
};
