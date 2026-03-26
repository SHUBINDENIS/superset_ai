import { ScanSearch } from "lucide-react";

export default function ScanPage() {
  return (
    <div className="flex flex-col items-center justify-center gap-3 pt-32 text-muted-foreground">
      <ScanSearch className="h-10 w-10" />
      <h2 className="text-lg font-medium text-foreground">Scan</h2>
      <p className="text-sm">Schema scanning will be available here.</p>
    </div>
  );
}
