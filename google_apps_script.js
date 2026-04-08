/**
 * ════════════════════════════════════════════════════════════
 *  Fast Education — Google Apps Script
 * ════════════════════════════════════════════════════════════
 *
 *  YOUR SHEET FORMAT:
 *  Row 1:  Dates (Fri, 3-Apr-2026, Mon, 6-Apr-2026, ...)
 *  Row 2:  Headers (Имя, Фамилия, Number, ..., Intro, 1, 2, 3...)
 *  Row 3+: Student data
 *
 *  Col C: Имя (First name)
 *  Col D: Фамилия (Last name)
 *  Col E: Phone number
 *  Col M+: Marks/grades (Intro, 1, 2, 3...)
 *
 *  Tabs: ATTENDANCE, Progress, BR10, BR20, etc.
 *  Skip: Group info, Contacts, Salary
 *
 *  SETUP:
 *  1. Extensions → Apps Script → paste this
 *  2. Change WEBHOOK_URL and WEBHOOK_SECRET below
 *  3. Triggers → + Add Trigger:
 *     - Function: onEditGrade
 *     - Event: From spreadsheet → On edit
 *  4. Add another trigger:
 *     - Function: retryFailed
 *     - Event: Time-driven → Every 5 minutes
 * ════════════════════════════════════════════════════════════
 */

// ━━━ SOZLAMALAR (O'ZGARTIRING) ━━━━━━━━━━━━━━━━━━━━━━━━━
var WEBHOOK_URL    = "http://45.130.148.53:5000/webhook/grade";  // ← PUT YOUR REAL SERVER IP HERE!
var WEBHOOK_SECRET = "change_this_secret_2024";
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

// Sheet structure
var HEADER_ROW       = 2;   // Row 2 = headers
var DATA_START_ROW   = 3;   // Row 3+ = students
var FIRST_NAME_COL   = 3;   // Col C = Имя
var LAST_NAME_COL    = 4;   // Col D = Фамилия
var PHONE_COL        = 5;   // Col E = Phone
var MARKS_START_COL  = 13;  // Col M = first mark column (Intro)

// Tabs to skip (non-grade sheets)
var SKIP_TABS = ["Group info", "Contacts", "Salary", "Summary", "Settings", "Template"];


// ─── MAIN TRIGGER ──────────────────────────────────────────
function onEditGrade(e) {
  try {
    if (!e || !e.range) return;

    var sheet = e.range.getSheet();
    var name  = sheet.getName();

    // Skip non-grade tabs
    if (SKIP_TABS.indexOf(name) !== -1) return;

    var row = e.range.getRow();
    var col = e.range.getColumn();

    // Skip header rows and non-mark columns
    if (row < DATA_START_ROW) return;
    if (col < MARKS_START_COL) return;

    // Handle bulk paste
    var numRows = e.range.getNumRows();
    var numCols = e.range.getNumColumns();

    if (numRows > 1 || numCols > 1) {
      handleBulk(e, sheet);
      return;
    }

    // Single cell edit
    var mark = e.value;
    if (!mark || mark.toString().trim() === "") return;

    processCell(sheet, row, col, mark.toString().trim());

  } catch (err) {
    Logger.log("ERROR: " + err.toString());
  }
}


// ─── PROCESS SINGLE CELL ──────────────────────────────────
function processCell(sheet, row, col, mark) {
  var firstName = sheet.getRange(row, FIRST_NAME_COL).getValue();
  var lastName  = sheet.getRange(row, LAST_NAME_COL).getValue();
  var phone     = sheet.getRange(row, PHONE_COL).getValue();

  if (!firstName && !lastName) return;
  if (!phone) return;

  // Get date from Row 1; fall back to Row 2 header label
  var dateRaw = sheet.getRange(1, col).getValue();
  if (!dateRaw || dateRaw.toString().trim() === "") {
    dateRaw = sheet.getRange(HEADER_ROW, col).getValue();
  }
  var dateStr = formatDate(dateRaw);

  var payload = {
    secret: WEBHOOK_SECRET,
    student_name: (firstName + " " + lastName).toString().trim(),
    phone: phone.toString().trim(),
    mark: mark,
    date: dateStr,
    sheet_name: sheet.getName()
  };

  sendWebhook(payload);
}


// ─── HANDLE BULK PASTE ────────────────────────────────────
function handleBulk(e, sheet) {
  var startRow  = e.range.getRow();
  var startCol  = e.range.getColumn();
  var numRows   = e.range.getNumRows();
  var numCols   = e.range.getNumColumns();
  var values    = e.range.getValues();

  for (var r = 0; r < numRows; r++) {
    var row = startRow + r;
    if (row < DATA_START_ROW) continue;

    for (var c = 0; c < numCols; c++) {
      var col = startCol + c;
      if (col < MARKS_START_COL) continue;

      var mark = values[r][c];
      if (!mark || mark.toString().trim() === "") continue;

      processCell(sheet, row, col, mark.toString().trim());
      Utilities.sleep(100);
    }
  }
}


// ─── FORMAT DATE ──────────────────────────────────────────
function formatDate(val) {
  if (!val) return "";
  if (val instanceof Date) {
    return Utilities.formatDate(val, Session.getScriptTimeZone(), "dd.MM.yyyy");
  }
  return val.toString().trim();
}


// ─── SEND WEBHOOK ─────────────────────────────────────────
function sendWebhook(payload) {
  try {
    var resp = UrlFetchApp.fetch(WEBHOOK_URL, {
      method: "post",
      contentType: "application/json",
      payload: JSON.stringify(payload),
      muteHttpExceptions: true,
      validateHttpsCertificates: false
    });

    if (resp.getResponseCode() === 200) {
      Logger.log("OK " + payload.student_name + " > " + payload.mark);
    } else {
      Logger.log("HTTP " + resp.getResponseCode());
      saveFailed(payload);
    }
  } catch (err) {
    Logger.log("ERR " + err.toString());
    saveFailed(payload);
  }
}


// ─── RETRY QUEUE ──────────────────────────────────────────
function saveFailed(payload) {
  var props = PropertiesService.getScriptProperties();
  var q = JSON.parse(props.getProperty("failed") || "[]");
  q.push(payload);
  if (q.length > 100) q = q.slice(-100);
  props.setProperty("failed", JSON.stringify(q));
}

// Time trigger: every 5 min
function retryFailed() {
  var props = PropertiesService.getScriptProperties();
  var q = JSON.parse(props.getProperty("failed") || "[]");
  if (q.length === 0) return;

  var remain = [];
  for (var i = 0; i < q.length; i++) {
    try {
      var resp = UrlFetchApp.fetch(WEBHOOK_URL, {
        method: "post",
        contentType: "application/json",
        payload: JSON.stringify(q[i]),
        muteHttpExceptions: true,
        validateHttpsCertificates: false
      });
      if (resp.getResponseCode() !== 200) remain.push(q[i]);
    } catch (e) {
      remain.push(q[i]);
    }
    Utilities.sleep(200);
  }
  props.setProperty("failed", JSON.stringify(remain));
}


// ─── TEST (manual run) ────────────────────────────────────
function testWebhook() {
  sendWebhook({
    secret: WEBHOOK_SECRET,
    student_name: "Test Student",
    phone: "998901234567",
    mark: "5",
    date: "01.04.2026",
    sheet_name: "ATTENDANCE"
  });
  Logger.log("Test sent!");
}
