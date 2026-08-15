import {
  LayoutDashboard,
  Inbox,
  Siren,
  Clock,
  Users,
  CalendarCheck,
  BarChart3,
  Brain,
  Compass,
  BookOpen,
  UserCog,
  Settings,
} from "lucide-react";

export interface NavItem {
  href: string;
  label: string;
  icon: typeof LayoutDashboard;
  mobilePriority?: boolean;
}

export const NAV_ITEMS: NavItem[] = [
  { href: "/", label: "Command Center", icon: LayoutDashboard, mobilePriority: true },
  { href: "/inbox", label: "Inbox", icon: Inbox, mobilePriority: true },
  { href: "/attention", label: "Attention Queue", icon: Siren, mobilePriority: true },
  { href: "/followups", label: "Follow-ups", icon: Clock },
  { href: "/customers", label: "Customers", icon: Users },
  { href: "/bookings", label: "Bookings", icon: CalendarCheck, mobilePriority: true },
  { href: "/analytics", label: "Analytics", icon: BarChart3 },
  { href: "/advisor", label: "AI Advisor", icon: Brain },
  { href: "/decisions", label: "Decision Center", icon: Compass },
  { href: "/knowledge", label: "Knowledge Base", icon: BookOpen },
  { href: "/staff", label: "Staff", icon: UserCog },
  { href: "/settings", label: "Settings", icon: Settings },
];
