import { Sparkles } from "lucide-react";

export default function RecommendPage() {
  return (
    <div className="flex flex-col items-center justify-center gap-3 pt-32 text-muted-foreground">
      <Sparkles className="h-10 w-10" />
      <h2 className="text-lg font-medium text-foreground">Recommend</h2>
      <p className="text-sm">AI-powered recommendations will be available here.</p>
    </div>
  );
}
