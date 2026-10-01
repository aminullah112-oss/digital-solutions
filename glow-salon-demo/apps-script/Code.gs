/**
 * Booking logger for the Glow Salon demo (ARR Digital).
 *
 * Setup:
 *  1. Create a Google Sheet. Rename the first tab to "Bookings".
 *  2. Put this header row in row 1 (exact order):
 *     Timestamp | Name | Phone | Service | Price | Date | Time | Status
 *  3. Extensions > Apps Script, paste this file, set NOTIFY_EMAIL below.
 *  4. Deploy > New deployment > Web app. Execute as: Me. Who has access: Anyone.
 *  5. Copy the web-app URL into SHEET_ENDPOINT in glow-salon-demo/index.html.
 *
 * Slot availability stays in the page for the demo. In a real client build,
 * doGet() below can return booked slots so the page blocks them for every visitor.
 */
var SHEET_NAME = 'Bookings';
var NOTIFY_EMAIL = 'aminullah112@gmail.com';

// Stop spreadsheet formula injection: cells starting with = + - @ are prefixed with '
function safe_(v, max) {
  v = String(v == null ? '' : v).trim().slice(0, max || 80);
  return /^[=+\-@]/.test(v) ? "'" + v : v;
}

function doPost(e) {
  var p = e.parameter || {};
  var name = safe_(p.name, 60), phone = safe_(p.phone, 15), service = safe_(p.service, 40);
  var date = safe_(p.date, 10), time = safe_(p.time, 5);
  var price = Number(p.price) || 0;

  if (!name || !/^91[6-9]\d{9}$/.test(phone) || !service || !/^\d{4}-\d{2}-\d{2}$/.test(date) || !/^\d{2}:\d{2}$/.test(time)) {
    return json_({ result: 'error', message: 'Invalid booking' });
  }

  var lock = LockService.getScriptLock();
  lock.waitLock(10000);
  try {
    var sheet = SpreadsheetApp.getActiveSpreadsheet().getSheetByName(SHEET_NAME)
      || SpreadsheetApp.getActiveSpreadsheet().getActiveSheet();

    // reject double-booking of the same slot
    var rows = sheet.getDataRange().getValues();
    for (var i = 1; i < rows.length; i++) {
      var d = rows[i][5] instanceof Date
        ? Utilities.formatDate(rows[i][5], Session.getScriptTimeZone(), 'yyyy-MM-dd') : String(rows[i][5]);
      if (d === date && String(rows[i][6]) === time && rows[i][7] !== 'Cancelled') {
        return json_({ result: 'error', message: 'Slot already booked' });
      }
    }

    sheet.appendRow([new Date(), name, phone, service, price, date, time, 'Confirmed']);
  } finally {
    lock.releaseLock();
  }

  try {
    MailApp.sendEmail({
      to: NOTIFY_EMAIL,
      subject: '[New booking] ' + name + ' — ' + service + ' ' + date + ' ' + time,
      body: 'Name: ' + name + '\nPhone: +' + phone + '\nService: ' + service + '\nWhen: ' + date + ' ' + time
    });
  } catch (err) { /* email quota or permission issue should not block the booking */ }

  return json_({ result: 'ok' });
}

// Optional: lets the page ask which slots are already taken (?date=YYYY-MM-DD)
function doGet(e) {
  var date = (e.parameter && e.parameter.date) || '';
  var sheet = SpreadsheetApp.getActiveSpreadsheet().getSheetByName(SHEET_NAME);
  var taken = [];
  if (sheet) {
    var rows = sheet.getDataRange().getValues();
    for (var i = 1; i < rows.length; i++) {
      var d = rows[i][5] instanceof Date
        ? Utilities.formatDate(rows[i][5], Session.getScriptTimeZone(), 'yyyy-MM-dd') : String(rows[i][5]);
      if (d === date && rows[i][7] !== 'Cancelled') taken.push(String(rows[i][6]));
    }
  }
  return json_({ date: date, taken: taken });
}

function json_(o) {
  return ContentService.createTextOutput(JSON.stringify(o)).setMimeType(ContentService.MimeType.JSON);
}
