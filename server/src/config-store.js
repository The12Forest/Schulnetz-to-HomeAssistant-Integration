"use strict";

const fs = require("fs");
const path = require("path");

const DATA_DIR = process.env.DATA_DIR || "/app/data";
const CONFIG_FILE = path.join(DATA_DIR, "config.json");

function envCredentials() {
  const email = process.env.SCHULNETZ_EMAIL || "";
  const password = process.env.SCHULNETZ_PASSWORD || "";
  const totpSecret = process.env.SCHULNETZ_TOTP_SECRET || "";
  if (email && password && totpSecret) {
    return { email, password, totpSecret, source: "env" };
  }
  return null;
}

function readStored() {
  try {
    const raw = fs.readFileSync(CONFIG_FILE, "utf-8");
    const data = JSON.parse(raw);
    if (data.email && data.password && data.totpSecret) {
      return { ...data, source: "stored" };
    }
  } catch {
    // no stored config yet
  }
  return null;
}

function writeStored(credentials) {
  fs.mkdirSync(DATA_DIR, { recursive: true });
  const payload = {
    email: credentials.email,
    password: credentials.password,
    totpSecret: credentials.totpSecret,
    updatedAt: new Date().toISOString(),
  };
  fs.writeFileSync(CONFIG_FILE, JSON.stringify(payload, null, 2), {
    encoding: "utf-8",
    mode: 0o600,
  });
}

/**
 * Resolve the effective credentials. Env vars always win; otherwise fall back
 * to the persisted config written via POST /api/config (survives restarts).
 */
function getCredentials() {
  return envCredentials() || readStored();
}

function setCredentials(credentials) {
  writeStored(credentials);
}

function hasConfig() {
  return getCredentials() !== null;
}

function configStatus() {
  const env = envCredentials();
  const stored = readStored();
  return {
    configured: Boolean(env || stored),
    source: env ? "env" : stored ? "stored" : null,
    email: env ? env.email : stored ? stored.email : null,
  };
}

module.exports = { getCredentials, setCredentials, hasConfig, configStatus };
