"use client";

export type ChatSyncEvent =
  | { type: "chat_created"; sessionId: string; timestamp: number }
  | { type: "chat_activated"; sessionId: string; timestamp: number }
  | { type: "chat_renamed"; sessionId: string; timestamp: number }
  | { type: "chat_deleted"; sessionId: string; timestamp: number }
  | { type: "chat_cleared"; sessionId: string; timestamp: number }
  | { type: "chat_settings_updated"; sessionId: string; timestamp: number }
  | { type: "chat_messages_updated"; sessionId: string; timestamp: number };

const CHAT_SYNC_CHANNEL = "superset-ai-chat-sync-v1";

function supportsBroadcastChannel() {
  return typeof window !== "undefined" && "BroadcastChannel" in window;
}

export function publishChatSyncEvent(event: Omit<ChatSyncEvent, "timestamp">) {
  if (!supportsBroadcastChannel()) {
    return;
  }
  const channel = new BroadcastChannel(CHAT_SYNC_CHANNEL);
  channel.postMessage({ ...event, timestamp: Date.now() } satisfies ChatSyncEvent);
  channel.close();
}

export function subscribeChatSyncEvents(
  handler: (event: ChatSyncEvent) => void,
) {
  if (!supportsBroadcastChannel()) {
    return () => {};
  }
  const channel = new BroadcastChannel(CHAT_SYNC_CHANNEL);
  channel.onmessage = (message) => {
    const payload = message.data;
    if (!payload || typeof payload !== "object") {
      return;
    }
    const type = String((payload as { type?: string }).type || "").trim();
    const sessionId = String((payload as { sessionId?: string }).sessionId || "").trim();
    if (!type || !sessionId) {
      return;
    }
    handler({
      type: type as ChatSyncEvent["type"],
      sessionId,
      timestamp: Number((payload as { timestamp?: number }).timestamp || Date.now()),
    });
  };
  return () => {
    channel.close();
  };
}
