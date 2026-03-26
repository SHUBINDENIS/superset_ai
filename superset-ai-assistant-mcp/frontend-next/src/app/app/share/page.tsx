import { Share2 } from "lucide-react";

export default function SharePage() {
  return (
    <div className="flex h-full flex-col items-center justify-center gap-3 px-6 pt-32 text-muted-foreground">
      <Share2 className="h-10 w-10" />
      <h2 className="text-lg font-medium text-foreground">Шеринг</h2>
      <p className="text-sm">
        Chart/dashboard sharing remains on Streamlit in this phase.
      </p>
    </div>
  );
}
