"use strict";

const { chromium } = require("playwright");
const { TOTP } = require("totp-generator");

const DEFAULT_BASE_URL = "https://schulnetz.lu.ch/bbzw";

const cleanVal = (val) => {
  if (val === null || val === undefined) return "---";
  const s = String(val).trim();
  if (
    !s ||
    s === "--" ||
    s === "NOTE HIDDEN" ||
    s === "HIDDEN" ||
    s === "Note HIDDEN"
  ) {
    return "---";
  }
  return s;
};

const ignoredLabels = [
  "kurs",
  "prüfungsgruppe",
  "datum",
  "thema",
  "bewertung",
  "gewichtung",
  "klassenschnitt",
  "einzelprüfungen",
  "bestätigt",
  "bestätigen",
];

function parseRows(rawRows) {
  const structuredData = [];
  let currentSubject = null;

  for (const row of rawRows) {
    const col0 = (row[0] || "").trim();
    const col1 = (row[1] || "").trim();

    if (col0.toLowerCase().includes("durchschnitt")) {
      if (currentSubject) {
        currentSubject.average = cleanVal(row[1]);
      }
      continue;
    }

    const isDate = /^\d{1,2}\.\d{1,2}\.\d{2,4}$/.test(col1);
    if (!col0 && isDate) {
      if (currentSubject) {
        const rawNote = row[3] || "";

        const pointsMatch = rawNote.match(/punkte:\s*([\d.,]+)/i);
        const gotPoints = pointsMatch
          ? pointsMatch[1].replace(",", ".")
          : "---";

        const noteMatch = rawNote.match(/^([\d.,]+)/);
        const note = noteMatch ? noteMatch[1].replace(",", ".") : cleanVal(row[3]);

        const classAvgRaw = cleanVal(row[5]);
        const classAvgMatch = classAvgRaw.match(/([\d.,]+)/);
        const classAverage = classAvgMatch
          ? classAvgMatch[1].replace(",", ".")
          : classAvgRaw;

        currentSubject.exams.push({
          date: col1 || "---",
          name: cleanVal(row[2]),
          note,
          weight: cleanVal(row[4]),
          gotPoints,
          maxPoints: "---",
          classAverage,
        });
      }
      continue;
    }

    const isIgnored = ignoredLabels.some((label) =>
      col0.toLowerCase().startsWith(label),
    );

    if (col0 && !isIgnored && !isDate) {
      currentSubject = {
        subject: col0,
        average: cleanVal(row[1]),
        exams: [],
      };
      structuredData.push(currentSubject);
    }
  }

  return structuredData;
}

/**
 * Logs into Schulnetz using the provided credentials and scrapes the grades page.
 * @param {{email: string, password: string, totpSecret: string, baseUrl?: string}} credentials
 * @returns {Promise<{subjects: Array, updatedAt: string}>}
 */
async function scrape(credentials) {
  const { email, password, totpSecret, baseUrl } = credentials;

  if (!email || !password || !totpSecret) {
    throw new Error("Missing credentials: email, password and totpSecret are required");
  }

  const url = baseUrl || DEFAULT_BASE_URL;
  const { otp } = TOTP.generate(totpSecret);

  const browser = await chromium.launch({
    headless: true,
    chromiumSandbox: false,
    args: ["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"],
  });

  try {
    const page = await browser.newPage();
    page.setDefaultTimeout(30000);

    await page.goto(url);

    await page
      .getByRole("textbox", { name: "Enter your email, phone, or" })
      .fill(email);
    await page
      .getByRole("textbox", { name: "Enter your email, phone, or" })
      .press("Enter");

    await page
      .getByRole("textbox", { name: "Enter the password for" })
      .fill(password);
    await page
      .getByRole("textbox", { name: "Enter the password for" })
      .press("Enter");

    await page.getByRole("textbox", { name: "Enter code" }).click();
    await page.getByRole("textbox", { name: "Enter code" }).fill(otp);
    await page.getByRole("button", { name: "Verify" }).click();
    await page.getByRole("button", { name: "Verify" }).click();

    // "Stay signed in?" prompt may appear on first login.
    const yesButton = page.getByRole("button", { name: "Yes" });
    try {
      await yesButton.waitFor({ state: "visible", timeout: 10000 });
      await yesButton.click();
    } catch {
      // Not shown — session was already remembered.
    }

    await page.getByRole("link", { name: "Noten" }).click();

    const tableSelector =
      "table.mdl-data-table.mdl-js-data-table.mdl-table--listtable";
    await page.waitForSelector(tableSelector);

    const rawRows = await page.$eval(tableSelector, (table) => {
      const rows = Array.from(table.querySelectorAll("tbody tr, tr"));
      return rows
        .map((row) =>
          Array.from(row.querySelectorAll("td, th")).map(
            (cell) => cell.textContent?.trim() || "",
          ),
        )
        .filter((row) => row.length > 0 && row.some((cell) => cell !== ""));
    });

    const subjects = parseRows(rawRows);

    return {
      subjects,
      updatedAt: new Date().toISOString(),
    };
  } finally {
    await browser.close();
  }
}

module.exports = { scrape, parseRows };
