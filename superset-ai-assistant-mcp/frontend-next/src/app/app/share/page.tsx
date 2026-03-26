import { Share2 } from "lucide-react";

export default function SharePage() {
  return (
    <div className="flex flex-col items-center justify-center gap-3 pt-32 text-muted-foreground">
      <Share2 className="h-10 w-10" />
      <h2 className="text-lg font-medium text-foreground">Share</h2>
      <p className="text-sm">Artifact sharing will be available here.</p>
    </div>
  );
}
