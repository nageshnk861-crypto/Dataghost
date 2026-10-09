import { redirect } from "next/navigation";

/**
 * Root route — redirects to the authenticated dashboard.
 * The real dashboard lives at app/(app)/dashboard/page.tsx.
 */
export default function RootPage() {
  redirect("/dashboard");
}
