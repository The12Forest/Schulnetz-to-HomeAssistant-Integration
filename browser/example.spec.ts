import { test, expect } from '@playwright/test';
import { TOTP } from "totp-generator";
import * as fs from "node:fs/promises";
import * as path from "node:path";

let username = process.env.username
let password = process.env.password
let totptoken = process.env.totpgentoken


test('test', async ({ page }) => {
  const { otp, expires } = await TOTP.generate(totptoken);
  await page.goto("https://schulnetz.lu.ch/bbzw");
  await page
    .getByRole("textbox", { name: "Enter your email, phone, or" })
    .fill(username);
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
  await page.getByRole("button", { name: "Yes" }).click();
  await page.getByRole("link", { name: " Noten" }).click();
  // 1. Selector for the target table
  // 1. Selector for the target table
  const tableSelector =
    "table.mdl-data-table.mdl-js-data-table.mdl-table--listtable";

  // Ensure table is attached before evaluating
  await page.waitForSelector(tableSelector);

  // 2. Extract raw cell matrices in one fast browser-side pass
  const rawRows: string[][] = await page.$eval(tableSelector, (table) => {
    const rows = Array.from(table.querySelectorAll("tbody tr, tr"));
    return rows
      .map((row) =>
        Array.from(row.querySelectorAll("td, th")).map(
          (cell) => cell.textContent?.trim() || "",
        ),
      )
      .filter((row) => row.length > 0 && row.some((cell) => cell !== ""));
  });

  // 3. Dynamic parser for varying subjects, grades, exams, and class averages
  interface Exam {
    name: string;
    date: string;
    note: string;
    weight: string;
    gotPoints: string;
    maxPoints: string;
    classAverage: string;
  }

  interface SubjectRecord {
    subject: string;
    average: string;
    exams: Exam[];
  }

  const cleanVal = (val: unknown): string => {
    if (val === null || val === undefined) return "---";
    const s = String(val).trim();
    if (
      !s ||
      s === "--" ||
      s === "NOTE HIDDEN" ||
      s === "HIDDEN" ||
      s === "Note HIDDEN"
    )
      return "---";
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

  const structuredData: SubjectRecord[] = [];
  let currentSubject: SubjectRecord | null = null;

  for (const row of rawRows) {
    const col0 = (row[0] || "").trim();
    const col1 = (row[1] || "").trim();

    // Check for "Aktueller Durchschnitt" row
    if (col0.toLowerCase().includes("durchschnitt")) {
      if (currentSubject) {
        currentSubject.average = cleanVal(row[1]);
      }
      continue;
    }

    // Check for Exam row: col0 is empty, col1 is a valid Date (e.g. 14.09.2026)
    const isDate = /^\d{1,2}\.\d{1,2}\.\d{2,4}$/.test(col1);
    if (!col0 && isDate) {
      if (currentSubject) {
        const rawNote = row[3] || "";

        // Extract points (e.g., "Punkte: 13.5")
        const pointsMatch = rawNote.match(/punkte:\s*([\d.,]+)/i);
        const gotPoints = pointsMatch
          ? pointsMatch[1].replace(",", ".")
          : "---";

        // Extract grade value
        const noteMatch = rawNote.match(/^([\d.,]+)/);
        const note = noteMatch
          ? noteMatch[1].replace(",", ".")
          : cleanVal(row[3]);

        // Extract class average (column index 5)
        const classAvgRaw = cleanVal(row[5]);
        const classAvgMatch = classAvgRaw.match(/([\d.,]+)/);
        const classAverage = classAvgMatch
          ? classAvgMatch[1].replace(",", ".")
          : classAvgRaw;

        currentSubject.exams.push({
          date: col1 || "---",
          name: cleanVal(row[2]),
          note: note,
          weight: cleanVal(row[4]),
          gotPoints: gotPoints,
          maxPoints: "---",
          classAverage: classAverage,
        });
      }
      continue;
    }

    // Check for new Subject row
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

  // 4. Save the structured JSON
  const filePath = path.join(__dirname, "table-data.json");
  await fs.writeFile(
    filePath,
    JSON.stringify(structuredData, null, 2),
    "utf-8",
  );

  console.log(`Saved ${structuredData.length} subjects to ${filePath}`);
  // await browser.close();
});