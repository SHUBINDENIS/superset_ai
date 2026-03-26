import { Eye } from "lucide-react";

export default function PreviewPage() {
  return (
    <div className="flex flex-col items-center justify-center gap-3 pt-32 text-muted-foreground">
      <Eye className="h-10 w-10" />
      <h2 className="text-lg font-medium text-foreground">Preview</h2>
      <p className="text-sm">Chart and dashboard preview will be available here.</p>
    </div>
  );
}
