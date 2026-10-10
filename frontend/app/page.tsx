import { redirect } from "next/navigation";

/**
 * Root route — redirects to the login page.
 */
export default function RootPage() {
  redirect("/login");
}
