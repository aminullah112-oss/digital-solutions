// All copy and structured data below is ported directly from the existing site
// (aminullah112-oss.github.io/digital-solutions) — no invented clients, numbers,
// certifications, or projects. Wording is tightened for this new layout, facts unchanged.

export const nav = [
  { n: '01', label: 'About', href: '#about' },
  { n: '02', label: 'Engineering', href: '#engineering' },
  { n: '03', label: 'Digital Solutions', href: '#solutions' },
  { n: '04', label: 'Products', href: '#products' },
  { n: '05', label: 'Expertise', href: '#expertise' },
  { n: '06', label: 'Contact', href: '#contact' },
];

export const hero = {
  status: 'Available for new projects',
  headline: 'I build digital products that solve real problems.',
  sub: '15+ years of engineering, testing and QMS discipline — now applied to software, automation and digital products.',
  stats: [
    { value: 15, suffix: '+', label: 'Years in Engineering' },
    { value: 12, suffix: '', label: 'Digital Products Shipped' },
    { value: 5, suffix: '', label: 'Industries Served' },
  ],
};

export const about = {
  kicker: 'Who I Am',
  title: 'One engineer, two ways to help your business',
  body: "Fifteen years of protection, testing, and QMS discipline from audit-grade industrial programs — now applied to building fast, reliable digital products for clients outside engineering too. Most engineers stop at the drawing. Most developers never set foot on a panel floor. I do both — which means when I build a tool, it's shaped by someone who has actually run the ATP, filled out the SCAR, and sat through the audit.",
  credentials: [
    '15+ years in protection, testing & MV/HV systems',
    'AS9100 / ISO 9001 QMS documentation background',
    'Audit-grade QC discipline from high-compliance industrial test programs',
    'Self-taught full-stack builder — Python, Flask, React, n8n',
  ],
  tracks: [
    {
      id: 'engineering',
      title: 'Engineering Track',
      body: 'Estimation, configurator, and commissioning tools for LV/MV panel builders and EPC contractors across the GCC — sold as ProtectionGrid, my flagship product line.',
    },
    {
      id: 'digital',
      title: 'Digital Solutions Track',
      body: 'ERPs, booking systems, AI content pipelines, and compliance documentation systems, built for small businesses and teams outside engineering.',
    },
  ],
};

export const engineering = {
  kicker: 'Engineering',
  title: 'Built from the panel floor.',
  body: "Fifteen years running ATPs, FATs, and audits on LV/MV/HV systems — the same discipline now shapes every tool I ship.",
  capabilities: [
    { label: 'Protection & Automation', group: 'domain' },
    { label: 'MV / HV Systems', group: 'domain' },
    { label: 'LV Control Panels', group: 'domain' },
    { label: 'Testing & Commissioning', group: 'domain' },
    { label: 'ATP / FAT', group: 'domain' },
    { label: 'ETAP', group: 'tool' },
    { label: 'EPLAN P8', group: 'tool' },
    { label: 'AutoCAD Electrical', group: 'tool' },
    { label: 'NI DAQmx', group: 'tool' },
    { label: 'NI FlexLogger', group: 'tool' },
    { label: 'AS9100', group: 'qms' },
    { label: 'ISO 9001', group: 'qms' },
    { label: 'QMS Documentation', group: 'qms' },
  ],
};

export const protectionGrid = {
  kicker: 'Flagship Product Line',
  title: 'ProtectionGrid',
  subtitle: "Engineering tools built by someone who's actually run the ATP.",
  body: 'A focused product line for GCC LV/MV panel builders, commissioning engineers, and EPC contractors — estimation, configuration, and testing tools grounded in 15 years of real panel-floor and QMS experience.',
  products: [
    {
      id: 'estimation-tool',
      name: 'LV Control Panel Estimation Tool',
      status: 'Commercial',
      body: 'Costing & estimation tool for LV control panel builds, built from years of real quotation and BOM experience.',
    },
    {
      id: 'genset-configurator',
      name: 'Genset Product Configurator',
      status: 'Delivered',
      body: 'Excel-based configurator that turns genset specs into accurate proposals in minutes instead of hours.',
    },
    {
      id: 'atp-fat-pack',
      name: 'ATP/FAT Excel Tool Pack',
      status: 'Live',
      meta: '5 Tools',
      body: 'A pack of five acceptance and factory test tools for commissioning engineers, distributed on Gumroad.',
    },
    {
      id: 'commissioning-toolkit',
      name: 'Commissioning & Testing Essentials Toolkit',
      status: 'In Build',
      body: 'Checklists, report templates, calculators, SOPs, AI prompts, and a project tracker for commissioning teams.',
    },
    {
      id: 'content-pipeline',
      name: 'Automated Content Pipeline',
      status: 'Live',
      body: 'n8n workflow: Google Sheets → Claude API → Telegram approval → auto-posted to LinkedIn, feeding a 100% organic community.',
    },
    {
      id: 'ptn-community',
      name: 'Protection & Test Engineers Network',
      status: 'Active',
      body: 'A LinkedIn community built and grown around ProtectionGrid content — the distribution channel behind the product line.',
    },
  ],
};

export const statusTone = {
  Commercial: 'delivered',
  Delivered: 'delivered',
  Live: 'live',
  'In Build': 'build',
  Active: 'live',
  Prototype: 'prototype',
};

export const solutionCategories = [
  { id: 'business', label: 'Small Business & Operations' },
  { id: 'ai', label: 'AI & Automation' },
  { id: 'branding', label: 'Branding & Marketing' },
  { id: 'compliance', label: 'Compliance & Training Systems' },
];

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
    id: 'pg-marketing',
    category: 'branding',
    status: 'Delivered',
    name: 'ProtectionGrid Marketing One-Pager',
    body: 'A hand-coded HTML/CSS one-pager built as the core marketing asset for the ProtectionGrid product line.',
    stack: ['HTML', 'CSS'],
  },
  {
    id: 'community-growth',
    category: 'branding',
    status: 'Active',
    name: 'Community-Led Growth',
    body: 'Built and grew the "Protection and Test Engineers Network" on LinkedIn organically, using the automated content pipeline as the distribution engine.',
    stack: ['LinkedIn', 'Content Ops'],
  },
  {
    id: 'mep-pitch',
    category: 'branding',
    status: 'Prototype',
    name: 'MEP Contractor Website Pitch',
    body: 'A pitched website concept for an MEP contractor, positioning their services with the same clarity-first approach used across my own product marketing.',
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
  title: 'The stack behind both tracks',
  groups: [
    {
      id: 'engineering',
      label: 'Engineering',
      skills: [
        'ETAP',
        'EPLAN P8',
        'AutoCAD Electrical',
        'EPLAN ProPanel 3D',
        'NI FlexLogger',
        'NI DAQmx',
        'Protection & MV/HV Systems',
        'AS9100 / ISO 9001 QMS',
      ],
    },
    {
      id: 'software',
      label: 'Software',
      skills: [
        'Python',
        'Tkinter',
        'Flask',
        'Plotly Dash',
        'React',
        'n8n',
        'FastAPI',
        'PostgreSQL',
        'Redis',
        'SQLite',
        'Excel / openpyxl',
      ],
    },
  ],
};

export const process = {
  kicker: 'Why Work With Me',
  title: 'Engineering discipline, applied to software delivery',
  steps: [
    {
      n: '01',
      title: 'Domain Credibility',
      body: 'Fifteen years actually running panels, ATPs, and audits — not guessing at what your industry needs.',
    },
    {
      n: '02',
      title: 'Idea to Deployed Tool',
      body: 'I ship — spreadsheets, desktop apps, PWAs, or full-stack apps, whichever gets your team a working tool fastest.',
    },
    {
      n: '03',
      title: 'Documentation Rigor',
      body: 'AS9100/ISO-grade documentation habits mean what I build is traceable, auditable, and handover-ready.',
    },
    {
      n: '04',
      title: 'Fast, Honest Iteration',
      body: 'The school furniture ERP was rebuilt three times to fit the client, not to fit a portfolio screenshot.',
    },
  ],
};

export const rd = {
  title: 'Also in the Lab',
  items: [
    {
      title: 'NSE Swing Trading System',
      body: 'Python screener with Weinstein Stage 2 analysis, GitHub Actions scheduling, and a GitHub Pages dashboard.',
    },
    {
      title: 'Crypto Three-Signal System',
      body: 'EMA cross + RSI + volume confirmation for spot trading.',
    },
    {
      title: 'TASI / Tadawul Screener',
      body: 'In progress — extending the same screening logic to the Saudi market.',
    },
  ],
  note: 'These are personal systems-building practice, not offered as an advisory, signals, or trading service.',
};

export const cta = {
  headline: 'Have a problem worth automating?',
  body: "Tell me what's slow, repetitive, manual or difficult — and I'll tell you what's fixable.",
};

export const contactCopy = {
  title: 'Get in touch',
  sub: 'Based in Chennai or working with a Chennai team? Say so below — local engagements get priority scheduling.',
  interests: [
    'Engineering & Panel Estimation (ProtectionGrid)',
    'Small Business System / ERP',
    'AI & Automation',
    'Branding & Marketing',
    'Compliance & Training',
    'Not sure yet',
  ],
};
