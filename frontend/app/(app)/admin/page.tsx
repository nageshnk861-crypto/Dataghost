"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

export default function AdminPage() {
  const router = useRouter();

  useEffect(() => {
    // Redirect to provisioning as the default admin page
    router.replace("/admin/provisioning");
  }, [router]);

  return null;
}
