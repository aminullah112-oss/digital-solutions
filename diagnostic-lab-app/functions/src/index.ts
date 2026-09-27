import { onDocumentWritten } from "firebase-functions/v2/firestore";
import { onRequest } from "firebase-functions/v2/https";
import { initializeApp } from "firebase-admin/app";
import { getFirestore } from "firebase-admin/firestore";
import { getMessaging } from "firebase-admin/messaging";

initializeApp();
const db = getFirestore();

/**
 * Maps a Booking.status transition (see Enums.kt BookingStatus) to the notification shown
 * in-app and pushed via FCM. Statuses not listed here (PENDING_PAYMENT, cancellations,
 * rejections) don't generate a push — those are surfaced directly in the booking screen
 * instead.
 */
const STATUS_NOTIFICATION: Record<string, { type: string; title: string; body: (b: FirebaseFirestore.DocumentData) => string }> = {
  CONFIRMED: { type: "BOOKING_CONFIRMED", title: "Booking confirmed", body: (b) => `Your booking for ${b.scheduledDate} is confirmed.` },
  PHLEBOTOMIST_ASSIGNED: { type: "PHLEBOTOMIST_ASSIGNED", title: "Phlebotomist assigned", body: () => "A phlebotomist has been assigned to your booking." },
  PHLEBOTOMIST_ON_THE_WAY: { type: "PHLEBOTOMIST_ON_THE_WAY", title: "On the way", body: () => "Your phlebotomist is on the way." },
  ARRIVED: { type: "PHLEBOTOMIST_ARRIVED", title: "Arrived", body: () => "Your phlebotomist has arrived." },
  SAMPLE_COLLECTED: { type: "SAMPLE_COLLECTED", title: "Sample collected", body: () => "Your sample has been collected." },
  RECEIVED_AT_LAB: { type: "SAMPLE_RECEIVED_AT_LAB", title: "Received at lab", body: () => "Your sample has reached the lab." },
  PROCESSING: { type: "SAMPLE_PROCESSING", title: "Processing", body: () => "Your sample is being processed." },
  REPORT_READY: { type: "REPORT_READY", title: "Report ready", body: () => "Your report is ready." },
  REPORT_DELIVERED: { type: "REPORT_DELIVERED", title: "Report delivered", body: () => "Your report has been delivered." },
};

export const onBookingStatusChange = onDocumentWritten("bookings/{bookingId}", async (event) => {
  const before = event.data?.before.data();
  const after = event.data?.after.data();
  if (!after) return; // booking deleted
  if (before && before.status === after.status) return; // no status change

  const mapping = STATUS_NOTIFICATION[after.status];
  if (!mapping) return;

  const ownerUid: string | undefined = after.patientAccountOwnerUserId;
  if (!ownerUid) return;

  await db.collection("users").doc(ownerUid).collection("notifications").add({
    type: mapping.type,
    title: mapping.title,
    body: mapping.body(after),
    read: false,
    createdAtMillis: Date.now(),
  });

  const userDoc = await db.collection("users").doc(ownerUid).get();
  const token = userDoc.data()?.fcmToken;
  if (token) {
    await getMessaging()
      .send({ token, notification: { title: mapping.title, body: mapping.body(after) } })
      .catch((err) => console.error("FCM send failed for", ownerUid, err));
  }
});

/**
 * Recomputes the admin dashboard's precomputed stats doc on every booking write. A full
 * collection scan per write is the simplest correct implementation and is fine at this
 * business's current scale (handfuls of bookings/day) — if that changes, switch to
 * incrementing counters per status transition instead of rescanning everything.
 */
export const recalcDashboardStats = onDocumentWritten("bookings/{bookingId}", async () => {
  const [bookingsSnap, patientsSnap, labsSnap, complaintsSnap] = await Promise.all([
    db.collection("bookings").get(),
    db.collection("patients").get(),
    db.collection("laboratories").where("active", "==", true).get(),
    db.collection("complaints").where("status", "in", ["OPEN", "ASSIGNED", "IN_PROGRESS"]).get(),
  ]);

  const todayStr = new Date().toISOString().slice(0, 10);
  const sevenDaysAgoMillis = Date.now() - 7 * 24 * 60 * 60 * 1000;

  let todaysBookings = 0, pendingCollections = 0, samplesInTransit = 0,
    reportsPending = 0, reportsCompleted = 0, totalRevenue = 0;

  bookingsSnap.forEach((doc) => {
    const b = doc.data();
    if (b.scheduledDate === todayStr) todaysBookings++;
    if (["CONFIRMED", "PHLEBOTOMIST_ASSIGNED", "PHLEBOTOMIST_ON_THE_WAY", "ARRIVED"].includes(b.status)) pendingCollections++;
    if (["SAMPLE_COLLECTED", "SAMPLE_IN_TRANSIT"].includes(b.status)) samplesInTransit++;
    if (["RECEIVED_AT_LAB", "PROCESSING"].includes(b.status)) reportsPending++;
    if (["REPORT_READY", "REPORT_DELIVERED"].includes(b.status)) reportsCompleted++;
    if (b.status !== "CANCELLED_BY_PATIENT" && b.status !== "CANCELLED_BY_LAB") totalRevenue += b.totalAmount || 0;
  });

  let newPatientsLast7Days = 0;
  patientsSnap.forEach((doc) => {
    const createdAtMillis = doc.data().createdAtMillis;
    if (typeof createdAtMillis === "number" && createdAtMillis >= sevenDaysAgoMillis) newPatientsLast7Days++;
  });

  await db.collection("stats").doc("dashboard").set({
    totalPatients: patientsSnap.size,
    newPatientsLast7Days,
    totalBookings: bookingsSnap.size,
    todaysBookings,
    pendingCollections,
    samplesInTransit,
    reportsPending,
    reportsCompleted,
    totalRevenue,
    openComplaints: complaintsSnap.size,
    activeLabs: labsSnap.size,
    updatedAtMillis: Date.now(),
  });
});

const LABS = [
  { id: "LAB-1", name: "Sunrise Diagnostics", city: "Chennai", address: "12 Anna Salai, Chennai", phone: "+91 44 2000 1001", openTime: "07:00", closeTime: "20:00", estimatedReportHours: 24, rating: 4.6 },
  { id: "LAB-2", name: "Apex Pathlabs", city: "Chennai", address: "45 T Nagar Main Rd, Chennai", phone: "+91 44 2000 1002", openTime: "06:30", closeTime: "21:00", estimatedReportHours: 12, rating: 4.4 },
  { id: "LAB-3", name: "MedCore Diagnostics", city: "Coimbatore", address: "8 RS Puram, Coimbatore", phone: "+91 422 200 1003", openTime: "07:00", closeTime: "19:00", estimatedReportHours: 24, rating: 4.3 },
  { id: "LAB-4", name: "Wellness Point Labs", city: "Madurai", address: "22 KK Nagar, Madurai", phone: "+91 452 200 1004", openTime: "07:30", closeTime: "20:30", estimatedReportHours: 48, rating: 4.1 },
  { id: "LAB-5", name: "Precision Diagnostics", city: "Chennai", address: "3 Velachery Main Rd, Chennai", phone: "+91 44 2000 1005", openTime: "00:00", closeTime: "23:59", estimatedReportHours: 6, rating: 4.8 },
];

const INVESTIGATIONS = [
  { id: "INV-001", name: "Complete Blood Count (CBC)", category: "General Health", sampleType: "Blood", prep: "No fasting required", turnaroundHours: 6, basePrice: 350.0 },
  { id: "INV-002", name: "C-Reactive Protein (CRP)", category: "Inflammation", sampleType: "Blood", prep: "No fasting required", turnaroundHours: 12, basePrice: 550.0 },
  { id: "INV-003", name: "Dengue NS1 Antigen", category: "Fever Panel", sampleType: "Blood", prep: "No fasting required", turnaroundHours: 6, basePrice: 900.0 },
  { id: "INV-004", name: "Malaria Parasite Test", category: "Fever Panel", sampleType: "Blood", prep: "No fasting required", turnaroundHours: 4, basePrice: 400.0 },
  { id: "INV-005", name: "Typhoid (Widal Test)", category: "Fever Panel", sampleType: "Blood", prep: "No fasting required", turnaroundHours: 12, basePrice: 300.0 },
  { id: "INV-006", name: "Liver Function Test (LFT)", category: "Organ Function", sampleType: "Blood", prep: "8 hours fasting recommended", turnaroundHours: 12, basePrice: 700.0 },
  { id: "INV-007", name: "Kidney Function Test (KFT)", category: "Organ Function", sampleType: "Blood", prep: "No fasting required", turnaroundHours: 12, basePrice: 650.0 },
  { id: "INV-008", name: "Fasting Blood Sugar", category: "Diabetes", sampleType: "Blood", prep: "8-10 hours fasting required", turnaroundHours: 4, basePrice: 150.0 },
  { id: "INV-009", name: "HbA1c", category: "Diabetes", sampleType: "Blood", prep: "No fasting required", turnaroundHours: 24, basePrice: 500.0 },
  { id: "INV-010", name: "Lipid Profile", category: "Heart Health", sampleType: "Blood", prep: "10-12 hours fasting required", turnaroundHours: 12, basePrice: 600.0 },
  { id: "INV-011", name: "Urine Routine Analysis", category: "General Health", sampleType: "Urine", prep: "First morning sample preferred", turnaroundHours: 6, basePrice: 200.0 },
  { id: "INV-012", name: "Thyroid Profile (TSH, T3, T4)", category: "Hormone", sampleType: "Blood", prep: "No fasting required", turnaroundHours: 24, basePrice: 750.0 },
  { id: "INV-013", name: "Vitamin D (25-OH)", category: "Vitamin", sampleType: "Blood", prep: "No fasting required", turnaroundHours: 48, basePrice: 1200.0 },
  { id: "INV-014", name: "Vitamin B12", category: "Vitamin", sampleType: "Blood", prep: "No fasting required", turnaroundHours: 48, basePrice: 900.0 },
  { id: "INV-015", name: "Erythrocyte Sedimentation Rate (ESR)", category: "Inflammation", sampleType: "Blood", prep: "No fasting required", turnaroundHours: 6, basePrice: 200.0 },
  { id: "INV-016", name: "Hemoglobin (Hb)", category: "General Health", sampleType: "Blood", prep: "No fasting required", turnaroundHours: 4, basePrice: 150.0 },
  { id: "INV-017", name: "Blood Culture", category: "Microbiology", sampleType: "Blood", prep: "Before starting antibiotics if possible", turnaroundHours: 72, basePrice: 1100.0 },
  { id: "INV-018", name: "Urine Culture & Sensitivity", category: "Microbiology", sampleType: "Urine", prep: "Mid-stream morning sample", turnaroundHours: 48, basePrice: 950.0 },
  { id: "INV-019", name: "Testosterone (Total)", category: "Hormone", sampleType: "Blood", prep: "Morning sample preferred", turnaroundHours: 24, basePrice: 1000.0 },
  { id: "INV-020", name: "COVID-19 RT-PCR", category: "Infectious Disease", sampleType: "Nasal/Throat Swab", prep: "No fasting required", turnaroundHours: 24, basePrice: 800.0 },
];

/**
 * One-time (safe to re-run — it just overwrites the same doc IDs) catalog seed, replicating
 * the labs/investigations/pricing the customer already reviewed in the demo app. Visit this
 * function's URL once in a browser after deploying to populate Firestore; there's no UI path
 * to seed this data since it's operator-managed catalog content, not something a patient or
 * even the admin role creates through the app itself yet.
 */
export const seedCatalog = onRequest(async (req, res) => {
  const batch = db.batch();

  LABS.forEach((lab) => {
    batch.set(db.collection("laboratories").doc(lab.id), {
      name: lab.name,
      city: lab.city,
      address: lab.address,
      phone: lab.phone,
      openTime: lab.openTime,
      closeTime: lab.closeTime,
      homeCollectionAvailable: true,
      estimatedReportHours: lab.estimatedReportHours,
      rating: lab.rating,
      active: true,
    });
  });

  INVESTIGATIONS.forEach((inv) => {
    batch.set(db.collection("investigations").doc(inv.id), {
      name: inv.name,
      description: `${inv.name} — routine diagnostic test.`,
      category: inv.category,
      sampleType: inv.sampleType,
      preparationInstructions: inv.prep,
      reportTurnaroundHours: inv.turnaroundHours,
    });
  });

  // Not every lab offers every test, and pricing varies slightly by lab — mirrors a real
  // marketplace and matches the ~80%-overlap pattern the demo data already used.
  LABS.forEach((lab, labIndex) => {
    INVESTIGATIONS.forEach((inv, invIndex) => {
      const offeredHere = (invIndex + labIndex) % 5 !== 4;
      if (!offeredHere) return;
      const priceVariance = 1.0 + (labIndex - 2) * 0.04;
      const price = Math.round((inv.basePrice * priceVariance) / 5.0) * 5.0;
      batch.set(db.collection("laboratories").doc(lab.id).collection("pricing").doc(inv.id), {
        price,
        homeCollectionAvailable: true,
      });
    });
  });

  await batch.commit();
  res.status(200).send(`Seeded ${LABS.length} labs and ${INVESTIGATIONS.length} investigations.`);
});
