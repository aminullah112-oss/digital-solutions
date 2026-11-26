import UserTab from "./UserTab.jsx";
import SignalsTab from "./SignalsTab.jsx";

// The dashboard builds its tab bar from this list.
// To add a tab: create a component in this folder, then add one line here.
//
//   { id: "holdings", label: "Holdings", component: HoldingsTab },
//
// Each tab component receives an `onSessionExpired` prop (call it when the
// backend answers HTTP 401) so the user is sent back to the login page.
// Tabs stay mounted while you switch between them, so results are kept.
export const TABS = [
  { id: "user", label: "User", component: UserTab },
  { id: "signals", label: "Signals", component: SignalsTab },
];
