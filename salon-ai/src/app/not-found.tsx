import Link from "next/link";
import { Compass } from "lucide-react";

export default function NotFound() {
  return (
    <div className="flex h-dvh flex-col items-center justify-center gap-3 bg-background text-foreground">
      <Compass className="size-8 text-accent" />
      <p className="text-sm font-semibold">Page not found</p>
      <Link href="/" className="text-xs text-accent hover:underline">
        Back to Command Center
      </Link>
    </div>
  );
}
