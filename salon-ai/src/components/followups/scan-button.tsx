"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useToast } from "@/components/ui/toast";

export function ScanButton() {
  const router = useRouter();
  const [scanning, setScanning] = useState(false);
  const { push } = useToast();

  async function scan() {
    setScanning(true);
    try {
      const res = await fetch("/api/followups/scan", { method: "POST" });
      const data = await res.json();
      push({ kind: "info", title: `Scan complete`, description: `${data.created ?? 0} new follow-up(s) found.` });
      router.refresh();
    } catch {
      push({ kind: "error", title: "Scan failed" });
    } finally {
      setScanning(false);
    }
  }

  return (
    <Button size="sm" variant="secondary" onClick={scan} disabled={scanning}>
      <RefreshCw className={scanning ? "size-3.5 animate-spin" : "size-3.5"} /> Scan for follow-ups
    </Button>
  );
}
