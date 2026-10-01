/**
 * Booking logger for the Glow Salon demo (ARR Digital).
 *
 * Sheet header row (row 1, exact order):
 *   Timestamp | Name | Phone | Service | Stylist | Price | Date | Time | Status
 *
 * Setup (also in README.md):
 *  1. Open the Sheet, Extensions > Apps Script, paste this file, set NOTIFY_EMAIL.
 *  2. Deploy > New deployment > type "Web app". Execute as: Me. Who has access: Anyone.
 *  3. Authorise when asked, copy the Web app URL (ends in /exec).
 *  4. Paste that URL into SHEET_ENDPOINT in glow-salon-demo/index.html.
 *
 * After you EDIT this script later, use Deploy > Manage deployments > edit (pencil)
 * > Version: New version > Deploy. The URL stays the same.
 */
var SHEET_NAME = 'Bookings';          // falls back to the first tab if this name is not found
var NOTIFY_EMAIL = 'aminullah112@gmail.com';

// Stops spreadsheet formula injection: cells starting with = + - @ get a leading '
function safe_(v, max) {
  v = String(v == null ? '' : v).trim().slice(0, max || 80);
  return /^[=+\-@]/.test(v) ? "'" + v : v;
}
function sheet_() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  return ss.getSheetByName(SHEET_NAME) || ss.getSheets()[0];
}
function day_(v) {
  return v instanceof Date ? Utilities.formatDate(v, Session.getScriptTimeZone(), 'yyyy-MM-dd') : String(v);
}
function time_(v) {
  return v instanceof Date ? Utilities.formatDate(v, Session.getScriptTimeZone(), 'HH:mm') : String(v);
}

function doPost(e) {
  var p = e.parameter || {};
  var name = safe_(p.name, 60), phone = safe_(p.phone, 15), service = safe_(p.service, 40);
  var stylist = safe_(p.stylist, 30), date = safe_(p.date, 10), time = safe_(p.time, 5);
  var price = Number(p.price) || 0;

  if (!name || !/^91[6-9]\d{9}$/.test(phone) || !service || !stylist ||
      !/^\d{4}-\d{2}-\d{2}$/.test(date) || !/^\d{2}:\d{2}$/.test(time)) {
    return json_({ result: 'error', message: 'Invalid booking' });
  }

  var lock = LockService.getScriptLock();
  lock.waitLock(10000);
  try {
    var sheet = sheet_();
    var rows = sheet.getDataRange().getValues();
    for (var i = 1; i < rows.length; i++) {            // reject double-booking of the same stylist + slot
      if (day_(rows[i][6]) === date && time_(rows[i][7]) === time &&
          String(rows[i][4]).toLowerCase() === stylist.toLowerCase() && rows[i][8] !== 'Cancelled') {
        return json_({ result: 'error', message: 'Slot already booked' });
      }
    }
    sheet.appendRow([new Date(), name, phone, service, stylist, price, date, time, 'Confirmed']);
  } finally {
    lock.releaseLock();
  }

  try {
    MailApp.sendEmail({
      to: NOTIFY_EMAIL,
      subject: '[New booking] ' + name + ' — ' + service + ' with ' + stylist + ', ' + date + ' ' + time,
      body: 'Name: ' + name + '\nPhone: +' + phone + '\nService: ' + service + '\nStylist: ' + stylist + '\nWhen: ' + date + ' ' + time
    });
  } catch (err) { /* email quota or permission problems must not block the booking */ }

  return json_({ result: 'ok' });
}

// The page calls this (?date=YYYY-MM-DD) to block slots booked by other visitors.
function doGet(e) {
  var date = (e.parameter && e.parameter.date) || '';
  var taken = [];
  var rows = sheet_().getDataRange().getValues();
  for (var i = 1; i < rows.length; i++) {
    if (day_(rows[i][6]) === date && rows[i][8] !== 'Cancelled') {
      taken.push({ stylist: String(rows[i][4]), time: time_(rows[i][7]) });
    }
  }
  return json_({ date: date, taken: taken });
}

function json_(o) {
  return ContentService.createTextOutput(JSON.stringify(o)).setMimeType(ContentService.MimeType.JSON);
}
