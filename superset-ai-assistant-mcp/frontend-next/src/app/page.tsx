import { redirect } from "next/navigation";

/** Root `/` redirects to the protected app shell. */
export default function Home() {
  redirect("/app");
}
