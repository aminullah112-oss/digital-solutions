// Paste the deployed Google Apps Script Web App URL here (see README:
// "Lead Capture Backend Setup"). Leave blank and the form tells visitors to
// email directly instead of failing silently.
export const LEADS_ENDPOINT = '';

export const CONTACT_EMAIL = 'aminullah112@gmail.com';
export const GITHUB_URL = 'https://github.com/aminullah112-oss';

export async function submitLead(formData) {
  if (!LEADS_ENDPOINT) {
    throw new Error('LEADS_ENDPOINT_MISSING');
  }
  await fetch(LEADS_ENDPOINT, { method: 'POST', mode: 'no-cors', body: formData });
}
