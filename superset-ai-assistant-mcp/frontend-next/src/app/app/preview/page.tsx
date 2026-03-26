import { Eye } from "lucide-react";

export default function PreviewPage() {
  return (
    <div className="flex h-full flex-col items-center justify-center gap-3 px-6 pt-32 text-muted-foreground">
      <Eye className="h-10 w-10" />
      <h2 className="text-lg font-medium text-foreground">Предпросмотр</h2>
      <p className="text-sm">
        Demo-critical preview flow will be migrated in the next iteration.
      </p>
    </div>
  );
}
