import { onDocumentWritten } from "firebase-functions/v2/firestore";
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
