"use client";
import { useEffect } from "react";
import { AlertTriangle } from "lucide-react";
import { Button } from "@/components/ui/button";

export default function AppError({ error, reset }: { error: Error & { digest?: string }; reset: () => void }) {
  useEffect(() => {
    console.error(error);
  }, [error]);

  return (
    <div className="flex h-full flex-col items-center justify-center gap-3 p-8 text-center">
      <div className="flex size-12 items-center justify-center rounded-full bg-danger/10 text-danger">
        <AlertTriangle className="size-6" />
      </div>
      <p className="text-sm font-medium">Something went wrong loading this page.</p>
      <p className="max-w-sm text-xs text-muted">{error.message || "An unexpected error occurred. Your data is safe — try again."}</p>
      <Button size="sm" onClick={reset}>
        Try again
      </Button>
    </div>
  );
}
