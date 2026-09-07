"use strict";

const fs = require("fs");
const path = require("path");

const DATA_DIR = process.env.DATA_DIR || "/app/data";
const CONFIG_FILE = path.join(DATA_DIR, "config.json");

const SCHOOL_BASE_URL = "https://schulnetz.lu.ch";
const DEFAULT_SCHOOL = "bbzw";

function buildSchoolUrl(school) {
  return `${SCHOOL_BASE_URL}/${school}`;
}

function envCredentials() {
  const email = process.env.SCHULNETZ_EMAIL || "";
  const password = process.env.SCHULNETZ_PASSWORD || "";
  const totp_secret = process.env.SCHULNETZ_TOTP_SECRET || "";
  if (email && password && totp_secret) {
    return { email, password, totp_secret, source: "env" };
  }
  return null;
}

function envBaseUrl() {
  if (process.env.SCHULNETZ_URL) {
    return process.env.SCHULNETZ_URL;
  }
  if (process.env.SCHULNETZ_SCHOOL) {
    return buildSchoolUrl(process.env.SCHULNETZ_SCHOOL);
  }
  return null;
}

function readStored() {
  try {
    const raw = fs.readFileSync(CONFIG_FILE, "utf-8");
    const data = JSON.parse(raw);
    if (data.email && data.password && data.totp_secret) {
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
    totp_secret: credentials.totp_secret,
    school: credentials.school || null,
    custom_url: credentials.custom_url || null,
    updatedAt: new Date().toISOString(),
  };
  fs.writeFileSync(CONFIG_FILE, JSON.stringify(payload, null, 2), {
    encoding: "utf-8",
    mode: 0o600,
  });
}

/**
 * Resolve the effective base URL. Precedence:
 *   1. env SCHULNETZ_URL (full URL)
 *   2. env SCHULNETZ_SCHOOL (code)
 *   3. stored custom_url
 *   4. stored school (code)
 *   5. default school (bbzw)
 */
function resolveBaseUrl() {
  const fromEnv = envBaseUrl();
  if (fromEnv) {
    return fromEnv;
  }
  const stored = readStored();
  if (stored && stored.custom_url) {
    return stored.custom_url;
  }
  if (stored && stored.school) {
    return buildSchoolUrl(stored.school);
  }
  return buildSchoolUrl(DEFAULT_SCHOOL);
}

/**
 * Resolve the effective config. Env vars always win; otherwise fall back to the
 * persisted config written via POST /api/config (survives restarts).
 */
function getCredentials() {
  const env = envCredentials();
  const stored = readStored();
  const creds = env || stored;
  if (!creds) {
    return null;
  }
  return {
    email: creds.email,
    password: creds.password,
    totp_secret: creds.totp_secret,
    baseUrl: resolveBaseUrl(),
    source: creds.source,
  };
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
    school: env
      ? process.env.SCHULNETZ_SCHOOL || null
      : stored
        ? stored.school || null
        : null,
    baseUrl: resolveBaseUrl(),
  };
}

module.exports = {
  getCredentials,
  setCredentials,
  hasConfig,
  configStatus,
  resolveBaseUrl,
};
