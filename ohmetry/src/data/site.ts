/**
 * Values only the site owner can supply. The toolkit page stays out of search
 * results (noindex) and shows no form until both URLs are set.
 */
export const site = {
  toolkitName: "Electrical Engineer's Toolkit",
  /** Gumroad product URL, e.g. https://yourname.gumroad.com/l/toolkit */
  gumroadUrl: '',
  /** POST endpoint of the email service (Buttondown, ConvertKit, Formspree, ...). Receives a field named "email". */
  emailFormAction: '',
};

export const toolkitReady = Boolean(site.gumroadUrl && site.emailFormAction);
