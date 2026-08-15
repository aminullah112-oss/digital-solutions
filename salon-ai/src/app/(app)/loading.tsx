import { Loader2 } from "lucide-react";

export default function AppLoading() {
  return (
    <div className="flex h-full items-center justify-center">
      <Loader2 className="size-5 animate-spin text-accent" />
    </div>
  );
}
