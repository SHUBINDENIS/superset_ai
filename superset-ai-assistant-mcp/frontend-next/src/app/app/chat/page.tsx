import { MessageSquare } from "lucide-react";

export default function ChatPage() {
  return (
    <div className="flex flex-col items-center justify-center gap-3 pt-32 text-muted-foreground">
      <MessageSquare className="h-10 w-10" />
      <h2 className="text-lg font-medium text-foreground">Chat</h2>
      <p className="text-sm">AI assistant chat will be available here.</p>
    </div>
  );
}
