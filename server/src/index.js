"use strict";

const http = require("http");

const { scrape } = require("./scraper");
const configStore = require("./config-store");
const stateStore = require("./state-store");

const PORT = parseInt(process.env.PORT || "80", 10);
const MIN_SCRAPE_INTERVAL_MS =
  parseInt(process.env.MIN_SCRAPE_INTERVAL_MS || "600000", 10);

let lastScrapeAt = 0;
let lastError = null;
let scrapeInProgress = false;

function sendJson(res, status, payload) {
  const body = JSON.stringify(payload);
  res.writeHead(status, {
    "Content-Type": "application/json",
    "Content-Length": Buffer.byteLength(body),
  });
  res.end(body);
}

function readBody(req) {
  return new Promise((resolve, reject) => {
    let data = "";
    req.on("data", (chunk) => {
      data += chunk;
      if (data.length > 1e6) {
        reject(new Error("Request body too large"));
        req.destroy();
      }
    });
    req.on("end", () => resolve(data));
    req.on("error", reject);
  });
}

function statusPayload() {
  const state = stateStore.readState();
  return {
    state: scrapeInProgress ? "running" : "idle",
    configured: configStore.hasConfig(),
    lastScrapeAt: lastScrapeAt ? new Date(lastScrapeAt).toISOString() : null,
    lastError,
    minScrapeIntervalMs: MIN_SCRAPE_INTERVAL_MS,
    nextAllowedAt: new Date(lastScrapeAt + MIN_SCRAPE_INTERVAL_MS).toISOString(),
    updatedAt: state ? state.updatedAt : null,
  };
}

async function handleScrape(res) {
  if (scrapeInProgress) {
    const state = stateStore.readState();
    return sendJson(res, 409, {
      error: "Scrape already in progress",
      ...(state ? state : {}),
    });
  }

  const now = Date.now();
  if (now - lastScrapeAt < MIN_SCRAPE_INTERVAL_MS) {
    const state = stateStore.readState();
    return sendJson(res, 429, {
      error: "Throttled: minimum scrape interval not elapsed",
      retryAfterMs: lastScrapeAt + MIN_SCRAPE_INTERVAL_MS - now,
      throttled: true,
      ...(state ? state : {}),
    });
  }

  const credentials = configStore.getCredentials();
  if (!credentials) {
    return sendJson(res, 400, {
      error: "No credentials configured. POST /api/config first.",
    });
  }

  scrapeInProgress = true;
  lastError = null;

  try {
    const state = await scrape(credentials);
    stateStore.writeState(state);
    lastScrapeAt = Date.now();
    return sendJson(res, 200, state);
  } catch (err) {
    lastError = String(err && err.message ? err.message : err);
    const cached = stateStore.readState();
    return sendJson(res, 502, {
      error: lastError,
      ...(cached ? { staleState: true, ...cached } : {}),
    });
  } finally {
    scrapeInProgress = false;
  }
}

const server = http.createServer(async (req, res) => {
  const { method } = req;
  const url = new URL(req.url, `http://${req.headers.host || "localhost"}`);

  try {
    if (method === "GET" && url.pathname === "/api/health") {
      return sendJson(res, 200, { status: "ok" });
    }

    if (method === "GET" && url.pathname === "/api/config") {
      return sendJson(res, 200, configStore.configStatus());
    }

    if (method === "POST" && url.pathname === "/api/config") {
      const body = await readBody(req);
      let parsed;
      try {
        parsed = JSON.parse(body || "{}");
      } catch {
        return sendJson(res, 400, { error: "Invalid JSON body" });
      }
      const { email, password, totpSecret } = parsed;
      if (!email || !password || !totpSecret) {
        return sendJson(res, 400, {
          error: "email, password and totpSecret are required",
        });
      }
      configStore.setCredentials({ email, password, totpSecret });
      return sendJson(res, 200, configStore.configStatus());
    }

    if (method === "GET" && url.pathname === "/api/status") {
      return sendJson(res, 200, statusPayload());
    }

    if (method === "GET" && url.pathname === "/api/state") {
      const state = stateStore.readState();
      if (!state) {
        return sendJson(res, 404, { error: "No state available yet" });
      }
      return sendJson(res, 200, state);
    }

    if (method === "POST" && url.pathname === "/api/scrape") {
      return await handleScrape(res);
    }

    return sendJson(res, 404, { error: "Not found" });
  } catch (err) {
    return sendJson(res, 500, {
      error: String(err && err.message ? err.message : err),
    });
  }
});

server.listen(PORT, "0.0.0.0", () => {
  console.log(`[schulnetz-server] listening on 0.0.0.0:${PORT}`);
});
