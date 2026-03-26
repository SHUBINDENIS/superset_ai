import { Sparkles } from "lucide-react";

export default function RecommendPage() {
  return (
    <div className="flex h-full flex-col items-center justify-center gap-3 px-6 pt-32 text-muted-foreground">
      <Sparkles className="h-10 w-10" />
      <h2 className="text-lg font-medium text-foreground">Рекомендации</h2>
      <p className="text-sm">
        Recommendation flow stays on Streamlit for now and will be migrated
        separately.
      </p>
    </div>
  );
}
