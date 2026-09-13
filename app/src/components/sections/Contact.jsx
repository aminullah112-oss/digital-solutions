import { useRef, useState } from 'react';
import { contactCopy } from '../../data/content';
import { CONTACT_EMAIL, LEADS_ENDPOINT, submitLead } from '../../lib/leads';
import { useReveal } from '../../lib/useReveal';

const inputClass =
  'w-full rounded-lg border border-graphite-border bg-graphite-900/70 px-4 py-3 text-sm text-ink-0 placeholder:text-ink-3 focus:border-cyan/60 focus:outline-none transition-colors duration-300';
const labelClass = 'font-mono-label text-[0.65rem] text-ink-2 mb-2 block';

export default function Contact() {
  const ref = useRef(null);
  const formRef = useRef(null);
  useReveal(ref);
  const [status, setStatus] = useState(null); // null | 'sending' | 'success' | 'error'
  const [errorMsg, setErrorMsg] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    const form = formRef.current;
    if (!form.checkValidity()) {
      form.reportValidity();
      return;
    }

    const data = new FormData(form);

    // Honeypot: real visitors never fill this hidden field.
    if (data.get('website')) {
      setStatus('success');
      form.reset();
      return;
    }

    if (!LEADS_ENDPOINT) {
      setStatus('error');
      setErrorMsg(`This form isn't connected yet — please email ${CONTACT_EMAIL} directly for now.`);
      return;
    }

    setStatus('sending');
    try {
      await submitLead(data);
      setStatus('success');
      form.reset();
    } catch {
      setStatus('error');
      setErrorMsg(`Something went wrong — please email ${CONTACT_EMAIL} directly.`);
    }
  };

  return (
    <section id="contact" ref={ref} className="relative py-28 md:py-36">
      <div className="max-w-3xl mx-auto px-5 sm:px-8">
        <div data-reveal className="rounded-2xl border border-graphite-border bg-graphite-900/60 backdrop-blur-md p-7 md:p-12">
          <h2 className="text-2xl md:text-3xl font-semibold text-ink-0">{contactCopy.title}</h2>
          <p className="mt-2 text-sm md:text-base text-ink-2">{contactCopy.sub}</p>

          <form ref={formRef} onSubmit={handleSubmit} noValidate className="mt-9 grid sm:grid-cols-2 gap-5">
            <div>
              <label htmlFor="lf-name" className={labelClass}>Full Name *</label>
              <input id="lf-name" name="name" type="text" required className={inputClass} />
            </div>
            <div>
              <label htmlFor="lf-company" className={labelClass}>Company / Business</label>
              <input id="lf-company" name="company" type="text" className={inputClass} />
            </div>
            <div>
              <label htmlFor="lf-city" className={labelClass}>City *</label>
              <input id="lf-city" name="city" type="text" required placeholder="e.g. Chennai" className={inputClass} />
            </div>
            <div>
              <label htmlFor="lf-phone" className={labelClass}>Phone / WhatsApp *</label>
              <input id="lf-phone" name="phone" type="tel" required className={inputClass} />
            </div>
            <div>
              <label htmlFor="lf-email" className={labelClass}>Email *</label>
              <input id="lf-email" name="email" type="email" required className={inputClass} />
            </div>
            <div>
              <label htmlFor="lf-interest" className={labelClass}>What do you need help with? *</label>
              <select id="lf-interest" name="interest" required defaultValue="" className={inputClass}>
                <option value="" disabled>Select one</option>
                {contactCopy.interests.map((opt) => (
                  <option key={opt} value={opt}>{opt}</option>
                ))}
              </select>
            </div>
            <div className="sm:col-span-2">
              <label htmlFor="lf-message" className={labelClass}>Tell me a bit more *</label>
              <textarea
                id="lf-message"
                name="message"
                rows={4}
                required
                placeholder="What's slow, broken, or missing right now?"
                className={inputClass}
              />
            </div>

            <div className="absolute -left-[9999px] w-px h-px overflow-hidden" aria-hidden="true">
              <label htmlFor="lf-website">Website</label>
              <input id="lf-website" name="website" type="text" tabIndex={-1} autoComplete="off" />
            </div>

            <div className="sm:col-span-2 flex items-start gap-3">
              <input id="lf-consent" name="consent" type="checkbox" required className="mt-1 accent-cyan" />
              <label htmlFor="lf-consent" className="text-sm text-ink-2">
                I agree to be contacted about this inquiry. *
              </label>
            </div>

            <div className="sm:col-span-2">
              <button
                type="submit"
                disabled={status === 'sending'}
                data-cursor="expand"
                className="font-mono-label text-xs text-graphite-950 bg-cyan px-7 py-4 rounded-full disabled:opacity-60 hover:brightness-110 transition-[filter] duration-300"
              >
                {status === 'sending' ? 'Sending…' : 'Send Inquiry'}
              </button>

              {status === 'success' && (
                <p className="mt-4 text-sm rounded-lg bg-[#4ade80]/10 border border-[#4ade80]/30 text-[#4ade80] px-4 py-3">
                  Thanks! I&rsquo;ve got your details and will follow up soon.
                </p>
              )}
              {status === 'error' && (
                <p className="mt-4 text-sm rounded-lg bg-red-500/10 border border-red-500/30 text-red-400 px-4 py-3">
                  {errorMsg}
                </p>
              )}
            </div>
          </form>
        </div>
      </div>
    </section>
  );
}
