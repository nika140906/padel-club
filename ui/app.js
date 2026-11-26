// The Padel Club UI: plain JavaScript, no framework, no build step.
// The browser calls both services directly:
//   bookings: login, courts and bookings
//   ladder:   joining, matches and the leaderboard
// If one service is down, only its half of the page shows an error.

const { bookingsUrl, ladderUrl } = window.PADEL_CONFIG; // from config.js
const TIMEOUT_MS = 10000; // give up on a service after 10 seconds

// The login token from bookings, sent to both services. It lives in
// sessionStorage, so it is forgotten when the tab closes. There is no
// logout route: logging out just forgets the token.
let token = sessionStorage.getItem("padel-token");
let me = JSON.parse(sessionStorage.getItem("padel-user") || "null"); // {id, username}

const $ = (id) => document.getElementById(id);

// Thrown when a service gives no answer at all: stopped, too slow, or
// blocked by CORS. The browser does not say which, so neither can we.
class ServiceDown extends Error {}

// Call one service and return its JSON body.
async function api(baseUrl, path, { method = "GET", body } = {}) {
  const headers = {};
  if (token) headers.Authorization = `Bearer ${token}`;
  if (body !== undefined) headers["Content-Type"] = "application/json";

  let response;
  try {
    response = await fetch(baseUrl + path, {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
      signal: AbortSignal.timeout(TIMEOUT_MS), // every call has a timeout
    });
  } catch {
    throw new ServiceDown();
  }

  const data = await response.json().catch(() => ({}));
  if (response.status === 401 && token) {
    logOut("Your login has expired. Please log in again.");
  }
  if (!response.ok) {
    // On Azure, the first request after a quiet period wakes the container and
    // the database. Until they are ready, Azure itself answers 503 without our
    // {"error": ...} body, so explain that instead of showing a bare code.
    const fallback = response.status === 503
      ? "the service is starting up after being idle. Try again in a minute"
      : `request failed (${response.status})`;
    const error = new Error(data.error || fallback);
    error.status = response.status;
    throw error;
  }
  return data;
}

// Show a message above one panel ("login", "bookings" or "ladder").
function show(panel, text, kind = "error") {
  const element = $(`${panel}-message`);
  element.textContent = text;
  element.className = `message ${kind}`;
}

function explain(error, service) {
  if (error instanceof ServiceDown) {
    // On Azure an idle service is woken by the first request, and Azure holds
    // that request open until the service is ready, which takes longer than
    // TIMEOUT_MS. So a timeout usually means "waking up", not "broken".
    return `The ${service} service is not reachable right now. If nobody used it for a while, it is probably waking up, which takes up to a minute. The rest of the page still works. Try again in a minute.`;
  }
  // The service's own message, e.g. "court is already booked at that time".
  return error.message.charAt(0).toUpperCase() + error.message.slice(1);
}

// Text is always set with textContent, never as HTML, so a name can never inject code.
function listItem(text, button) {
  const item = document.createElement("li");
  const label = document.createElement("span");
  label.textContent = text;
  item.append(label);
  if (button) item.append(button);
  return item;
}

function emptyItem(text) {
  const item = listItem(text);
  item.className = "empty";
  return item;
}

function fillSelect(select, options) {
  const previous = select.value;
  select.replaceChildren(...options.map(({ value, text }) => new Option(text, value)));
  if (options.some((option) => String(option.value) === previous)) select.value = previous;
}

// ---------- Login (bookings service) ----------

function credentials() {
  return { username: $("username").value, password: $("password").value };
}

async function logIn() {
  try {
    const data = await api(bookingsUrl, "/auth/login", { method: "POST", body: credentials() });
    token = data.token;
    me = { id: data.id, username: data.username };
    sessionStorage.setItem("padel-token", token);
    sessionStorage.setItem("padel-user", JSON.stringify(me));
    $("password").value = "";
    showApp();
  } catch (error) {
    show("login", explain(error, "bookings"));
  }
}

$("login-form").addEventListener("submit", (event) => {
  event.preventDefault();
  logIn();
});

$("register").addEventListener("click", async () => {
  if (!$("login-form").reportValidity()) return;
  try {
    await api(bookingsUrl, "/auth/register", { method: "POST", body: credentials() });
    await logIn();
  } catch (error) {
    show("login", explain(error, "bookings"));
  }
});

function logOut(message = "") {
  token = null;
  me = null;
  sessionStorage.clear();
  $("app").hidden = true;
  $("who").hidden = true;
  $("login-panel").hidden = false;
  show("login", message);
}

$("logout").addEventListener("click", () => logOut());

function showApp() {
  $("login-panel").hidden = true;
  $("app").hidden = false;
  $("who").hidden = false;
  $("who-name").textContent = me.username;
  show("bookings", "");
  show("ladder", "");
  // Load each half on its own, so one service being down does not stop the other.
  loadBookings();
  loadLadder();
}

// ---------- Court bookings (bookings service) ----------

let courtNames = {}; // court id -> name

// Start times every half hour from 08:00 to 22:00. The service checks the real rules.
const startTimes = [];
for (let hour = 8; hour <= 22; hour++) {
  for (const minute of ["00", "30"]) {
    if (hour === 22 && minute === "30") break;
    startTimes.push(`${String(hour).padStart(2, "0")}:${minute}`);
  }
}
fillSelect($("start"), startTimes.map((time) => ({ value: time, text: time })));
$("start").value = "18:00";
$("day").value = new Date().toLocaleDateString("en-CA"); // today as YYYY-MM-DD

async function loadBookings() {
  try {
    const { courts } = await api(bookingsUrl, "/courts");
    courtNames = Object.fromEntries(courts.map((court) => [court.id, court.name]));
    fillSelect($("court"), courts.map((court) => ({ value: court.id, text: court.name })));
    await Promise.all([loadSchedule(), loadMyBookings()]);
  } catch (error) {
    show("bookings", explain(error, "bookings"));
  }
}

const timeOf = (dateTime) => dateTime.slice(11); // "2030-06-01 18:00" -> "18:00"

async function loadSchedule() {
  const { bookings } = await api(bookingsUrl, `/courts/${$("court").value}/bookings?day=${$("day").value}`);
  $("schedule").replaceChildren(
    ...(bookings.length
      ? bookings.map((b) => listItem(`${timeOf(b.start_time)}–${timeOf(b.end_time)}${b.user_id === me.id ? "  (you)" : ""}`))
      : [emptyItem("Free all day")])
  );
}

async function loadMyBookings() {
  const { bookings } = await api(bookingsUrl, "/bookings/mine");
  $("my-bookings").replaceChildren(
    ...(bookings.length
      ? bookings.map((b) => {
          const cancel = document.createElement("button");
          cancel.type = "button";
          cancel.className = "quiet";
          cancel.textContent = "Cancel";
          cancel.addEventListener("click", () => cancelBooking(b.id));
          return listItem(`${courtNames[b.court_id] || "Court " + b.court_id} · ${b.start_time}–${timeOf(b.end_time)}`, cancel);
        })
      : [emptyItem("No bookings yet")])
  );
}

for (const id of ["court", "day"]) {
  $(id).addEventListener("change", () => loadSchedule().catch((error) => show("bookings", explain(error, "bookings"))));
}

$("book-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  try {
    await api(bookingsUrl, "/bookings", {
      method: "POST",
      body: {
        court_id: Number($("court").value),
        start_time: `${$("day").value} ${$("start").value}`,
        duration_minutes: Number($("duration").value),
      },
    });
    await Promise.all([loadSchedule(), loadMyBookings()]);
    show("bookings", "Booked.", "ok");
  } catch (error) {
    show("bookings", explain(error, "bookings"));
  }
});

async function cancelBooking(bookingId) {
  try {
    await api(bookingsUrl, `/bookings/${bookingId}`, { method: "DELETE" });
    await Promise.all([loadSchedule(), loadMyBookings()]);
    show("bookings", "Booking cancelled.", "ok");
  } catch (error) {
    show("bookings", explain(error, "bookings"));
  }
}

// ---------- Match ladder (ladder service) ----------

async function loadLadder() {
  try {
    const [{ leaderboard }, player] = await Promise.all([
      api(ladderUrl, "/ladder/leaderboard"),
      // 404 here just means "not on the ladder yet".
      api(ladderUrl, "/ladder/me").catch((error) => {
        if (error.status === 404) return null;
        throw error;
      }),
    ]);

    $("me").textContent = player
      ? `You are ${player.nickname}: rating ${player.rating}, ${player.wins} of ${player.matches_played} matches won.`
      : "You are not on the ladder yet.";
    $("join-form").hidden = Boolean(player);

    $("leaderboard").replaceChildren(
      ...leaderboard.map((p) => {
        const row = document.createElement("tr");
        for (const value of [p.rank, p.nickname, p.rating, p.matches_played, p.wins]) {
          const cell = document.createElement("td");
          cell.textContent = value;
          row.append(cell);
        }
        return row;
      })
    );

    // A match needs four players on the ladder, and you must be one of them.
    $("match-form").hidden = !player || leaderboard.length < 4;
    if (player) {
      const players = [player, ...leaderboard.filter((p) => p.user_id !== player.user_id)];
      const options = players.map((p) => ({ value: p.user_id, text: p.nickname }));
      ["a1", "a2", "b1", "b2"].forEach((id, index) => {
        fillSelect($(id), options);
        if (!$(id).dataset.chosen && options[index]) $(id).value = options[index].value;
      });
    }
  } catch (error) {
    show("ladder", explain(error, "ladder"));
  }
}

// Remember that the member picked a player by hand, so a reload keeps it.
for (const id of ["a1", "a2", "b1", "b2"]) {
  $(id).addEventListener("change", () => ($(id).dataset.chosen = "yes"));
}

$("join-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  try {
    // The ladder asks bookings who we are. If bookings is down, this answers
    // 503 with its own "try again" message, which is shown as it is.
    const nickname = $("nickname").value.trim();
    const player = await api(ladderUrl, "/ladder/join", { method: "POST", body: nickname ? { nickname } : {} });
    await loadLadder();
    show("ladder", `You joined the ladder as ${player.nickname}.`, "ok");
  } catch (error) {
    show("ladder", explain(error, "ladder"));
  }
});

$("match-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const pick = (id) => Number($(id).value);
  try {
    const result = await api(ladderUrl, "/ladder/matches", {
      method: "POST",
      body: { team_a: [pick("a1"), pick("a2")], team_b: [pick("b1"), pick("b2")], winner: $("winner").value },
    });
    await loadLadder();
    const change = result.team_a_change;
    show("ladder", `Match saved. Team A ${change >= 0 ? "+" : ""}${change}, team B ${-change >= 0 ? "+" : ""}${-change}.`, "ok");
  } catch (error) {
    show("ladder", explain(error, "ladder"));
  }
});

// ---------- Start ----------

if (token && me) showApp();
