// All copy and structured data below reflects real work only — no invented clients,
// numbers, certifications, or projects. Positioning is scoped to digital products and
// solutions for small businesses; nothing here claims an engineering background.

export const nav = [
  { n: '01', label: 'About', href: '#about' },
  { n: '02', label: 'Services', href: '#products' },
  { n: '03', label: 'Case Studies', href: '#solutions' },
  { n: '04', label: 'Expertise', href: '#expertise' },
  { n: '05', label: 'Contact', href: '#contact' },
];

export const hero = {
  status: 'Available for new projects',
  headline: 'I build digital products that solve real problems.',
  sub: 'Small business systems, AI automation, and digital products — built fast, iterated honestly, and handed off clean.',
  stats: [
    { value: 7, suffix: '', label: 'Digital Products Shipped' },
    { value: 4, suffix: '', label: 'Industries Served' },
    { value: 11, suffix: '+', label: 'Tools in the Stack' },
  ],
};

export const about = {
  kicker: 'Who I Am',
  title: 'A builder who ships, not just plans',
  body: "I'm a self-taught full-stack builder — Python, Flask, React, n8n — who takes a business problem from a messy spreadsheet or a manual process to a working, documented system. No agency overhead and no account manager standing between you and the build: you work directly with the person shipping it.",
  perks: [
    'Direct access — you work with the person building it, not an account manager',
    'Documented, handover-ready systems — no black boxes only I can maintain',
    'Real iteration — I rebuild until it fits how you actually work',
    'Full-stack range — ERPs, automation, AI pipelines, and the site to sell it',
  ],
  process: [
    {
      id: 'understand',
      title: 'Understand',
      body: "I start with what's actually slow or manual — not a feature wishlist.",
    },
    {
      id: 'build',
      title: 'Build',
      body: 'Working software, not mockups. You see something real within days.',
    },
    {
      id: 'iterate',
      title: 'Iterate',
      body: 'Ship, get real feedback, adjust — until it fits how the team actually works.',
    },
  ],
};

export const solutionCategories = [
  {
    id: 'business',
    label: 'Small Business & Operations',
    pitch:
      'Replace spreadsheets and manual tracking with a real system — inventory, payroll, billing, or a full operations dashboard, built around how your team already works.',
    deliverables: ['Custom ERP & inventory systems', 'Payroll & billing systems', 'Booking & scheduling tools'],
  },
  {
    id: 'ai',
    label: 'AI & Automation',
    pitch:
      'Automate the repetitive parts of running a business — content, approvals, customer replies — so your team spends time on what actually needs a human.',
    deliverables: ['AI content & approval pipelines', 'WhatsApp / chat-based booking', 'Workflow automation (n8n)'],
  },
  {
    id: 'branding',
    label: 'Branding & Marketing',
    pitch:
      "A site and positioning that actually explain what you do, built fast — not a template with your logo pasted on.",
    deliverables: ['Marketing sites & landing pages', 'Product positioning', 'Launch-ready copy & design'],
  },
  {
    id: 'compliance',
    label: 'Compliance & Training Systems',
    pitch:
      "Turn scattered SOPs and training material into something your team will actually use — structured, searchable, and easy to hand off.",
    deliverables: ['SOP-to-video pipelines', 'Documentation systems', 'Training content workflows'],
  },
];

export const statusTone = {
  Delivered: 'delivered',
  Live: 'live',
  Active: 'live',
  Prototype: 'prototype',
};

export const projects = [
  {
    id: 'sheets-erp',
    category: 'business',
    status: 'Delivered',
    name: 'Google Sheets ERP',
    body: "My first paying client engagement — a lightweight ERP built entirely in Google Sheets to run day-to-day operations for a friend's business.",
    stack: ['Google Sheets', 'Apps Script'],
  },
  {
    id: 'furniture-erp',
    category: 'business',
    status: 'Delivered',
    name: 'School Furniture Manufacturing ERP',
    body: 'Started as an Excel tracker, rebuilt as a Python/Tkinter/SQLite desktop app, then rebuilt again as a Flask PWA packaged into a single-file Android app — three iterations chasing what the client actually needed.',
    stack: ['Python', 'Tkinter', 'SQLite', 'Flask PWA'],
  },
  {
    id: 'payroll-billing',
    category: 'business',
    status: 'Delivered',
    name: 'Payroll & Billing System',
    body: 'A payroll and billing system built for a 300-person manpower contracting company, handling recurring billing cycles and staff payroll.',
    stack: ['Python', 'SQLite'],
  },
  {
    id: 'ai-content-pipeline',
    category: 'ai',
    status: 'Live',
    name: 'AI Content Pipeline',
    body: 'An n8n workflow that pulls content ideas from Google Sheets, drafts posts with the Claude API, routes them through Telegram for approval, and auto-publishes to LinkedIn.',
    stack: ['n8n', 'Claude API', 'Telegram'],
  },
  {
    id: 'salon-booking',
    category: 'ai',
    status: 'Prototype',
    name: 'WhatsApp Salon Booking SaaS',
    body: 'A prototype booking system that lets customers schedule salon appointments entirely through WhatsApp, built on a FastAPI/PostgreSQL/Redis stack.',
    stack: ['FastAPI', 'PostgreSQL', 'Redis'],
  },
  {
    id: 'mep-pitch',
    category: 'branding',
    status: 'Prototype',
    name: 'Contractor Website Pitch',
    body: 'A pitched website concept for a contracting business, positioning their services with the same clarity-first approach used across my own product marketing.',
    stack: ['Web Design', 'Positioning'],
  },
  {
    id: 'training-video-pipeline',
    category: 'compliance',
    status: 'Prototype',
    name: 'AI Training Video Pipeline',
    body: 'A Synthesia-based pipeline concept for turning written SOPs and training material into narrated video content at scale — built for teams that need to train, not just document.',
    stack: ['Synthesia', 'Content Pipeline'],
  },
];

export const expertise = {
  kicker: 'My Expertise',
  title: 'The stack behind the systems',
  groups: [
    {
      id: 'backend',
      label: 'Backend & Automation',
      skills: ['Python', 'Flask', 'FastAPI', 'n8n', 'PostgreSQL', 'Redis', 'SQLite'],
    },
    {
      id: 'product',
      label: 'Product & Frontend',
      skills: ['React', 'Tkinter', 'Plotly Dash', 'Excel / openpyxl'],
    },
  ],
};

export const process = {
  kicker: 'Why Work With Me',
  title: 'Real systems, shipped and documented',
  steps: [
    {
      n: '01',
      title: 'Proof, Not Promises',
      body: 'Seven real systems shipped for real businesses — this page is case studies, not concepts.',
    },
    {
      n: '02',
      title: 'Idea to Deployed Tool',
      body: 'Spreadsheets, desktop apps, PWAs, or full-stack apps — whichever gets your team a working tool fastest.',
    },
    {
      n: '03',
      title: 'Documentation & Handover',
      body: 'Every project ships with docs that make sense to the next person — no black-box systems only I can maintain.',
    },
    {
      n: '04',
      title: 'Fast, Honest Iteration',
      body: 'The school furniture ERP was rebuilt three times to fit the client, not to fit a portfolio screenshot.',
    },
  ],
};

export const cta = {
  headline: 'Have a problem worth automating?',
  body: "Tell me what's slow, repetitive, manual or difficult — and I'll tell you what's fixable.",
};

export const contactCopy = {
  title: 'Get in touch',
  sub: 'Based in Chennai or working with a Chennai team? Say so below — local engagements get priority scheduling.',
  // Derived from solutionCategories rather than duplicated, so a service's CTA can set
  // the exact same string the contact form expects for that category.
  interests: [...solutionCategories.map((c) => c.label), 'Not sure yet'],
};
