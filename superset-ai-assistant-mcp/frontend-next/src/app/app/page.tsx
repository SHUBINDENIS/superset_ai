import { redirect } from "next/navigation";

/** `/app` redirects to the default tab. */
export default function AppIndex() {
  redirect("/app/chat");
}
