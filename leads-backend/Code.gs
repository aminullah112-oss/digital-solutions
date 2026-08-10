/**
 * Lead intake backend for the digital-solutions portfolio contact form.
 *
 * Setup: see README.md "Lead Capture Backend Setup". In short —
 * paste this whole file into Extensions > Apps Script on a Google Sheet
 * with a "Leads" tab, then deploy it as a Web App (Execute as: Me,
 * Who has access: Anyone) and put the resulting URL into
 * LEADS_ENDPOINT in js/main.js.
 *
 * Expected "Leads" sheet header row (exact order):
 * Timestamp | Name | Company | City | Priority | Phone | Email | Interest | Message | Status | Notes
 */

var NOTIFY_EMAIL = 'aminullah112@gmail.com';
var SHEET_NAME = 'Leads';

function doPost(e) {
  var sheet = SpreadsheetApp.getActiveSpreadsheet().getSheetByName(SHEET_NAME)
    || SpreadsheetApp.getActiveSpreadsheet().getActiveSheet();

  var p = e.parameter || {};
  var name = (p.name || '').trim();
  var company = (p.company || '').trim();
  var city = (p.city || '').trim();
  var phone = (p.phone || '').trim();
  var email = (p.email || '').trim();
  var interest = (p.interest || '').trim();
  var message = (p.message || '').trim();

  // Basic server-side gate — reject empty submissions (e.g. bots hitting the endpoint directly).
  if (!name || !phone || !email) {
    return ContentService.createTextOutput(JSON.stringify({ result: 'error', message: 'Missing required fields' }))
      .setMimeType(ContentService.MimeType.JSON);
  }

  var isChennai = /chennai/i.test(city);

  sheet.appendRow([
    new Date(),
    name,
    company,
    city,
    isChennai ? '🔥 Chennai' : '',
    phone,
    email,
    interest,
    message,
    'New',
    ''
  ]);

  try {
    MailApp.sendEmail({
      to: NOTIFY_EMAIL,
      subject: (isChennai ? '🔥 [Chennai Lead] ' : '[New Lead] ') + name + (interest ? ' — ' + interest : ''),
      body:
        'New inquiry from the portfolio site:\n\n' +
        'Name: ' + name + '\n' +
        'Company: ' + company + '\n' +
        'City: ' + city + '\n' +
        'Phone: ' + phone + '\n' +
        'Email: ' + email + '\n' +
        'Interest: ' + interest + '\n\n' +
        'Message:\n' + message
    });
  } catch (err) {
    // Don't let a notification failure block the lead from being recorded.
  }

  return ContentService.createTextOutput(JSON.stringify({ result: 'success' }))
    .setMimeType(ContentService.MimeType.JSON);
}
