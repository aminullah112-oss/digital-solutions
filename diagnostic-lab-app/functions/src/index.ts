import { onDocumentWritten } from "firebase-functions/v2/firestore";
import { onCall, onRequest, HttpsError } from "firebase-functions/v2/https";
import { defineSecret } from "firebase-functions/params";
import { initializeApp } from "firebase-admin/app";
import { getFirestore, FieldValue } from "firebase-admin/firestore";
import { getMessaging } from "firebase-admin/messaging";
import * as crypto from "crypto";
import * as https from "https";

initializeApp();
const db = getFirestore();

const razorpayKeyId = defineSecret("RAZORPAY_KEY_ID");
const razorpayKeySecret = defineSecret("RAZORPAY_KEY_SECRET");

/** Minimal HTTPS client for the Razorpay Orders API — avoids depending on the Razorpay Node
 * SDK (or global fetch, whose typings vary by @types/node version) for what is otherwise a
 * single POST request. */
function razorpayRequest(path: string, keyId: string, keySecret: string, body: object): Promise<any> {
  return new Promise((resolve, reject) => {
    const payload = JSON.stringify(body);
    const auth = Buffer.from(`${keyId}:${keySecret}`).toString("base64");
    const req = https.request(
      {
        hostname: "api.razorpay.com",
        path,
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Authorization": `Basic ${auth}`,
          "Content-Length": Buffer.byteLength(payload),
        },
      },
      (res) => {
        let raw = "";
        res.on("data", (chunk) => (raw += chunk));
        res.on("end", () => {
          const status = res.statusCode ?? 0;
          let parsed: any;
          try {
            parsed = raw ? JSON.parse(raw) : {};
          } catch {
            parsed = { raw };
          }
          if (status >= 200 && status < 300) {
            resolve(parsed);
          } else {
            reject(new Error(`Razorpay API ${path} failed (${status}): ${raw}`));
          }
        });
      }
    );
    req.on("error", reject);
    req.write(payload);
    req.end();
  });
}

/**
 * Creates a Razorpay Order for a booking's total amount. Order creation has to happen
 * server-side with the account's secret key — the client only ever sees the public Key ID and
 * the resulting order_id, never the secret, and can't request an order for an amount of its
 * own choosing (the amount always comes from the booking doc, not from client input).
 */
export const createRazorpayOrder = onCall(
  { secrets: [razorpayKeyId, razorpayKeySecret] },
  async (request) => {
    const uid = request.auth?.uid;
    if (!uid) throw new HttpsError("unauthenticated", "Sign in required.");
    const bookingId = request.data?.bookingId;
    if (typeof bookingId !== "string" || !bookingId) {
      throw new HttpsError("invalid-argument", "bookingId is required.");
    }

    const bookingRef = db.collection("bookings").doc(bookingId);
    const booking = await bookingRef.get();
    if (!booking.exists) throw new HttpsError("not-found", "Booking not found.");
    const data = booking.data()!;
    if (data.patientAccountOwnerUserId !== uid) {
      throw new HttpsError("permission-denied", "This booking doesn't belong to you.");
    }
    if (data.status !== "PENDING_PAYMENT") {
      throw new HttpsError("failed-precondition", "This booking is no longer awaiting payment.");
    }

    const amountPaise = Math.round((data.totalAmount as number) * 100);
    const keyId = razorpayKeyId.value();
    const order = await razorpayRequest("/v1/orders", keyId, razorpayKeySecret.value(), {
      amount: amountPaise,
      currency: "INR",
      receipt: bookingId,
    });

    await bookingRef.update({
      payment: {
        method: "ONLINE",
        status: "PENDING",
        razorpayOrderId: order.id,
        timestampMillis: Date.now(),
      },
    });

    return { orderId: order.id as string, amountPaise, currency: "INR", keyId };
  }
);

/**
 * Verifies a completed Razorpay checkout server-side before trusting it. Razorpay signs
 * order_id + payment_id with the account's secret key (HMAC-SHA256) — recomputing that
 * signature here and comparing it is the only way to know a payment genuinely succeeded.
 * Trusting the client's own "it worked" callback instead would let a modified app mark any
 * booking paid without ever charging a card, so no Firestore write happens until this passes.
 */
export const verifyRazorpayPayment = onCall(
  { secrets: [razorpayKeySecret] },
  async (request) => {
    const uid = request.auth?.uid;
    if (!uid) throw new HttpsError("unauthenticated", "Sign in required.");
    const { bookingId, razorpayPaymentId, razorpayOrderId, razorpaySignature } = request.data ?? {};
    if (
      typeof bookingId !== "string" || typeof razorpayPaymentId !== "string" ||
      typeof razorpayOrderId !== "string" || typeof razorpaySignature !== "string"
    ) {
      throw new HttpsError("invalid-argument", "Missing payment verification fields.");
    }

    const bookingRef = db.collection("bookings").doc(bookingId);
    const booking = await bookingRef.get();
    if (!booking.exists) throw new HttpsError("not-found", "Booking not found.");
    const data = booking.data()!;
    if (data.patientAccountOwnerUserId !== uid) {
      throw new HttpsError("permission-denied", "This booking doesn't belong to you.");
    }
    // Binds the signature to THIS booking's own order, not just any order the same patient
    // might have created — otherwise a valid signature from an unrelated payment could be
    // replayed here to confirm a different booking for free.
    if (data.payment?.razorpayOrderId !== razorpayOrderId) {
      throw new HttpsError("failed-precondition", "This payment doesn't match this booking's order.");
    }

    const expectedSignature = crypto
      .createHmac("sha256", razorpayKeySecret.value())
      .update(`${razorpayOrderId}|${razorpayPaymentId}`)
      .digest("hex");
    const expected = Buffer.from(expectedSignature);
    const actual = Buffer.from(razorpaySignature);
    const isValid = expected.length === actual.length && crypto.timingSafeEqual(expected, actual);
    if (!isValid) {
      console.error("Razorpay signature mismatch for booking", bookingId);
      throw new HttpsError("permission-denied", "Payment verification failed.");
    }

    const now = Date.now();
    await bookingRef.update({
      status: "CONFIRMED",
      updatedAtMillis: now,
      payment: {
        method: "ONLINE",
        status: "SUCCESSFUL",
        razorpayOrderId,
        razorpayPaymentId,
        timestampMillis: now,
      },
    });
    await bookingRef.collection("trackingEvents").add({
      status: "CONFIRMED",
      timestampMillis: now,
      actorId: uid,
      actorRole: "PATIENT",
      notes: null,
    });

    return { success: true };
  }
);

/**
 * Lets a signed-in account self-register as a new, pending laboratory. This is the one case a
 * client is allowed to change its own role (PATIENT -> LABORATORY) — firestore.rules otherwise
 * permanently blocks that client-side (users/{uid}'s update rule requires role to stay
 * unchanged; see AuthRepository.kt's kdoc: staff roles are meant to be human/server-granted
 * only). Runs with the Admin SDK specifically to cross that boundary safely: the new
 * laboratories doc is created with active:false/onboardingStatus:'PENDING_APPROVAL', so it's
 * invisible to patients and to every other lab until reviewLaboratoryOnboarding approves it —
 * a self-registered entity shouldn't start collecting samples under the marketplace's name
 * unvetted.
 */
export const registerLaboratory = onCall(async (request) => {
  const uid = request.auth?.uid;
  if (!uid) throw new HttpsError("unauthenticated", "Sign in required.");

  const data = request.data ?? {};
  const name = typeof data.name === "string" ? data.name.trim() : "";
  const address = typeof data.address === "string" ? data.address.trim() : "";
  const city = typeof data.city === "string" ? data.city.trim() : "";
  const phone = typeof data.phone === "string" ? data.phone.trim() : "";
  const openTime = typeof data.openTime === "string" ? data.openTime.trim() : "";
  const closeTime = typeof data.closeTime === "string" ? data.closeTime.trim() : "";
  const homeCollectionAvailable = data.homeCollectionAvailable === true;
  const licenseNumber = typeof data.licenseNumber === "string" && data.licenseNumber.trim() ? data.licenseNumber.trim() : null;

  if (!name || !address || !city || !phone || !openTime || !closeTime) {
    throw new HttpsError("invalid-argument", "name, address, city, phone, openTime, and closeTime are required.");
  }

  const userRef = db.collection("users").doc(uid);
  const userSnap = await userRef.get();
  const currentRole = userSnap.exists ? userSnap.data()?.role : "PATIENT";
  if (currentRole && currentRole !== "PATIENT") {
    throw new HttpsError("failed-precondition", "This account already holds a staff role and can't register a lab.");
  }

  const labRef = db.collection("laboratories").doc();
  await labRef.set({
    name,
    address,
    city,
    phone,
    openTime,
    closeTime,
    homeCollectionAvailable,
    estimatedReportHours: 24,
    rating: null,
    active: false,
    onboardingStatus: "PENDING_APPROVAL",
    ownerUserId: uid,
    licenseNumber,
    registeredAtMillis: Date.now(),
  });

  // merge: true preserves mobileNumber (and fcmToken, if already set) already on this doc.
  await userRef.set({ role: "LABORATORY", linkedEntityId: labRef.id }, { merge: true });

  return { labId: labRef.id };
});

/**
 * A self-onboarded lab editing its own profile after registration. Deliberately excludes
 * active/onboardingStatus/ownerUserId/rejectionReason — those only ever change via
 * reviewLaboratoryOnboarding, so a lab can never approve itself by writing straight to its own
 * doc, even through this function.
 */
export const updateLaboratoryProfile = onCall(async (request) => {
  const uid = request.auth?.uid;
  if (!uid) throw new HttpsError("unauthenticated", "Sign in required.");
  const labId = request.data?.labId;
  if (typeof labId !== "string" || !labId) throw new HttpsError("invalid-argument", "labId is required.");

  const labRef = db.collection("laboratories").doc(labId);
  const labSnap = await labRef.get();
  if (!labSnap.exists) throw new HttpsError("not-found", "Laboratory not found.");

  const userSnap = await db.collection("users").doc(uid).get();
  const isAdminCaller = userSnap.data()?.role === "ADMIN";
  if (labSnap.data()?.ownerUserId !== uid && !isAdminCaller) {
    throw new HttpsError("permission-denied", "You don't own this laboratory.");
  }

  const data = request.data ?? {};
  const updates: Record<string, unknown> = {};
  for (const field of ["name", "address", "city", "phone", "openTime", "closeTime", "licenseNumber"]) {
    if (typeof data[field] === "string") updates[field] = data[field].trim();
  }
  if (typeof data.homeCollectionAvailable === "boolean") {
    updates.homeCollectionAvailable = data.homeCollectionAvailable;
  }
  if (Object.keys(updates).length === 0) {
    throw new HttpsError("invalid-argument", "No editable fields provided.");
  }
  await labRef.update(updates);
  return { updated: true };
});

/**
 * Admin-only approve/reject gate for a self-registered lab — the only path that can ever flip
 * laboratories.active/onboardingStatus, so neither a lab's own client nor updateLaboratoryProfile
 * above can self-approve.
 */
export const reviewLaboratoryOnboarding = onCall(async (request) => {
  const uid = request.auth?.uid;
  if (!uid) throw new HttpsError("unauthenticated", "Sign in required.");
  const userSnap = await db.collection("users").doc(uid).get();
  if (userSnap.data()?.role !== "ADMIN") throw new HttpsError("permission-denied", "Admin only.");

  const labId = request.data?.labId;
  const decision = request.data?.decision;
  if (typeof labId !== "string" || !labId) throw new HttpsError("invalid-argument", "labId is required.");
  if (decision !== "APPROVE" && decision !== "REJECT") {
    throw new HttpsError("invalid-argument", "decision must be APPROVE or REJECT.");
  }

  const reason = typeof request.data?.reason === "string" ? request.data.reason.trim() : null;
  await db.collection("laboratories").doc(labId).update({
    active: decision === "APPROVE",
    onboardingStatus: decision === "APPROVE" ? "ACTIVE" : "REJECTED",
    rejectionReason: decision === "REJECT" ? reason : null,
  });
  return { decision };
});

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
 * Auto-picks a phlebotomist for a booking that needs one. This used to run client-side
 * (any signed-in account querying `users where role==PHLEBOTOMIST` to pick one) — but that
 * requires every phlebotomist's user doc, including their phone number, to be listable by any
 * patient, which firestore.rules correctly refuses (confirmed via a real PERMISSION_DENIED
 * crash in CI). Runs here instead via the Admin SDK, which bypasses security rules entirely
 * and never exposes the phlebotomist roster to any client.
 *
 * Reacts to the same two cases the old client-side call covered: a booking transitioning into
 * CONFIRMED or REJECTED_RECOLLECTION_NEEDED (needs a first/new phlebotomist), or an existing
 * assignment's status flipping to REJECTED (the assigned phlebotomist declined, needs a
 * replacement). Each of those writes assignedPhlebotomistUid/assignment.status away from the
 * triggering value, so this never re-fires on its own write.
 */
export const assignPhlebotomistOnBookingWrite = onDocumentWritten("bookings/{bookingId}", async (event) => {
  const before = event.data?.before.data();
  const after = event.data?.after.data();
  if (!after) return; // booking deleted

  const statusJustEnteredNeedsAssignment =
    before?.status !== after.status &&
    (after.status === "CONFIRMED" || after.status === "REJECTED_RECOLLECTION_NEEDED");
  const assignmentJustRejected =
    after.assignment?.status === "REJECTED" && before?.assignment?.status !== "REJECTED";
  if (!statusJustEnteredNeedsAssignment && !assignmentJustRejected) return;

  const phlebotomistSnap = await db.collection("users").where("role", "==", "PHLEBOTOMIST").limit(1).get();
  const phlebotomistDoc = phlebotomistSnap.docs[0];
  if (!phlebotomistDoc) return; // no phlebotomist on the roster yet
  const phlebotomist = phlebotomistDoc.data();

  const bookingId = event.params.bookingId;
  const now = Date.now();
  await db.collection("bookings").doc(bookingId).update({
    status: "PHLEBOTOMIST_ASSIGNED",
    updatedAtMillis: now,
    assignedPhlebotomistUid: phlebotomistDoc.id,
    assignment: {
      phlebotomistUid: phlebotomistDoc.id,
      name: phlebotomist.name ?? "Lab Assistant",
      mobileNumber: phlebotomist.mobileNumber ?? "",
      professionalId: phlebotomist.professionalId ?? "",
      rating: phlebotomist.rating ?? 0,
      status: "ASSIGNED",
      assignedAtMillis: now,
    },
  });
  await db.collection("bookings").doc(bookingId).collection("trackingEvents").add({
    status: "PHLEBOTOMIST_ASSIGNED",
    timestampMillis: now,
    actorId: phlebotomistDoc.id,
    actorRole: "PHLEBOTOMIST",
    notes: null,
  });
});

/**
 * Maintains patients/{patientId}.authorizedLabIds and .authorizedPhlebotomistUids —
 * firestore.rules grants a LABORATORY or PHLEBOTOMIST account read access to a patient
 * profile only via membership in these arrays, scoped to labs/phlebotomists actually
 * involved in a booking for that patient. The old rule granted isLab()/isPhlebotomist()
 * blanket read access to every patient document regardless of any booking relationship —
 * a real cross-tenant data leak once self-registered labs exist (see firestore.rules'
 * myLabId() comment for the same class of bug on bookings/reports, fixed earlier). This
 * closes the same hole for patient profiles (DOB, sex, mobile number, email).
 *
 * Runs via the Admin SDK (bypasses rules) on every booking write: grants the lab on
 * creation (a lab must see the patient profile the moment a booking lands on it) and
 * grants a phlebotomist the moment they're assigned (covers reassignment after a
 * rejection too — the array only ever grows, past assignees keep having touched the
 * case, which is correct, not a loosening of the old behavior since the old behavior was
 * already-unscoped access for every lab/phlebotomist on the roster).
 */
export const grantPatientAccessOnBookingWrite = onDocumentWritten("bookings/{bookingId}", async (event) => {
  const before = event.data?.before.data();
  const after = event.data?.after.data();
  if (!after || !after.patientId) return; // booking deleted, or no patient reference

  const updates: Record<string, FirebaseFirestore.FieldValue> = {};
  if (!before) {
    updates.authorizedLabIds = FieldValue.arrayUnion(after.laboratoryId);
  }
  if (after.assignedPhlebotomistUid && before?.assignedPhlebotomistUid !== after.assignedPhlebotomistUid) {
    updates.authorizedPhlebotomistUids = FieldValue.arrayUnion(after.assignedPhlebotomistUid);
  }
  if (Object.keys(updates).length === 0) return;

  await db.collection("patients").doc(after.patientId).set(updates, { merge: true });
});

/**
 * One-time admin-triggered backfill for patients/{patientId}.authorizedLabIds/
 * authorizedPhlebotomistUids on bookings that existed before grantPatientAccessOnBookingWrite
 * started running (that trigger only fires on a NEW booking write, so pre-existing bookings
 * never populate these arrays on their own). Safe to call more than once — arrayUnion is
 * idempotent. Call once after deploying this fix if there's any existing booking data.
 */
export const backfillPatientAccess = onCall(async (request) => {
  const uid = request.auth?.uid;
  if (!uid) throw new HttpsError("unauthenticated", "Sign in required.");
  const callerSnap = await db.collection("users").doc(uid).get();
  if (callerSnap.data()?.role !== "ADMIN") throw new HttpsError("permission-denied", "Admin only.");

  const bookingsSnap = await db.collection("bookings").get();
  const patientUpdates = new Map<string, { labIds: Set<string>; phlebotomistUids: Set<string> }>();

  bookingsSnap.forEach((doc) => {
    const b = doc.data();
    if (!b.patientId) return;
    const entry = patientUpdates.get(b.patientId) ?? { labIds: new Set(), phlebotomistUids: new Set() };
    if (b.laboratoryId) entry.labIds.add(b.laboratoryId);
    if (b.assignedPhlebotomistUid) entry.phlebotomistUids.add(b.assignedPhlebotomistUid);
    patientUpdates.set(b.patientId, entry);
  });

  let batch = db.batch();
  let opsInBatch = 0;
  for (const [patientId, entry] of patientUpdates) {
    const fields: Record<string, FirebaseFirestore.FieldValue> = {};
    if (entry.labIds.size > 0) fields.authorizedLabIds = FieldValue.arrayUnion(...entry.labIds);
    if (entry.phlebotomistUids.size > 0) fields.authorizedPhlebotomistUids = FieldValue.arrayUnion(...entry.phlebotomistUids);
    if (Object.keys(fields).length === 0) continue;

    batch.set(db.collection("patients").doc(patientId), fields, { merge: true });
    opsInBatch++;
    if (opsInBatch === 400) {
      await batch.commit();
      batch = db.batch();
      opsInBatch = 0;
    }
  }
  if (opsInBatch > 0) await batch.commit();

  return { patientsUpdated: patientUpdates.size };
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
  // Real onboarded customer (feverlabs.in) — a fever/infectious-disease-focused lab, not a
  // fictional demo entry like LAB-1..5 above. openTime/closeTime reflect their Mon-Sat hours;
  // their shorter Sunday hours (7:00-14:00) aren't representable since this schema has no
  // per-day-of-week field. rating is a placeholder (their site shows only individual 5-star
  // testimonials, no aggregate) — replace with their real Google Business rating once known.
  { id: "LAB-6", name: "Dr. Sheela Fever Labs & Diagnostics", city: "Chennai", address: "143, 144, LIC Jeevan Pallava, 142, Thiruvottiyur High Rd, New Washermenpet, Tondiarpet, Chennai, Tamil Nadu 600081", phone: "+91 99627 03342", openTime: "07:00", closeTime: "20:00", estimatedReportHours: 8, rating: 4.8 },
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
  { id: "INV-021", name: "Creatinine", category: "Organ Function", sampleType: "Blood", prep: "No fasting required", turnaroundHours: 6, basePrice: 250.0 },
  { id: "INV-022", name: "Electrolytes (Na, K, Cl)", category: "Organ Function", sampleType: "Blood", prep: "No fasting required", turnaroundHours: 8, basePrice: 450.0 },
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

  // Real fixed-price bundles for the actual onboarded customer (feverlabs.in) — these are
  // their own published panels/pricing, not fictional demo data like LABS/INVESTIGATIONS
  // above. Deliberately scoped to LAB-6 only; the other demo labs have no packages, matching
  // how a real lab wouldn't necessarily offer bundles at all.
  const FEVER_LABS_PACKAGES = [
    {
      id: "PKG-FEVER-BASIC",
      name: "Basic Fever Panel",
      description: "Complete Blood Count (CBC), ESR, Malaria Test",
      price: 800.0,
      investigationIds: ["INV-001", "INV-015", "INV-004"],
    },
    {
      id: "PKG-FEVER-COMPREHENSIVE",
      name: "Comprehensive Fever Panel",
      description: "CBC, ESR, Malaria, Dengue NS1 Antigen, Liver Function Test, Creatinine",
      price: 1200.0,
      investigationIds: ["INV-001", "INV-015", "INV-004", "INV-003", "INV-006", "INV-021"],
    },
    {
      id: "PKG-FEVER-ELABORATE",
      name: "Elaborate Fever & Inflammation Panel",
      description: "CBC, ESR, Malaria, Dengue NS1, LFT, Creatinine, CRP, Typhoid Test, Electrolytes",
      price: 1800.0,
      investigationIds: ["INV-001", "INV-015", "INV-004", "INV-003", "INV-006", "INV-021", "INV-002", "INV-005", "INV-022"],
    },
  ];
  FEVER_LABS_PACKAGES.forEach((pkg) => {
    batch.set(db.collection("laboratories").doc("LAB-6").collection("packages").doc(pkg.id), {
      name: pkg.name,
      description: pkg.description,
      price: pkg.price,
      investigationIds: pkg.investigationIds,
      homeCollectionAvailable: true,
      active: true,
    });
  });

  await batch.commit();
  res.status(200).send(
    `Seeded ${LABS.length} labs, ${INVESTIGATIONS.length} investigations, and ${FEVER_LABS_PACKAGES.length} packages.`
  );
});
