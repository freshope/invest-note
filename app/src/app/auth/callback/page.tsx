"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/components/providers/AuthProvider";
import { FullPageSpinner } from "@/components/base/FullPageSpinner";

export default function AuthCallbackPage() {
  const { user, loading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!loading) {
      router.replace(user ? "/" : "/login?error=oauth_failed");
    }
  }, [loading, user, router]);

  return <FullPageSpinner />;
}
