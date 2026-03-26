import { ScanSearch } from "lucide-react";

export default function ScanPage() {
  return (
    <div className="flex h-full flex-col items-center justify-center gap-3 px-6 pt-32 text-muted-foreground">
      <ScanSearch className="h-10 w-10" />
      <h2 className="text-lg font-medium text-foreground">Сканер схем</h2>
      <p className="text-sm">
        Schema scan parity will be migrated after chat and analytics demo flows.
      </p>
    </div>
  );
}
