"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/components/providers/AuthProvider";
import { FullPageSpinner } from "@/components/base/FullPageSpinner";
import { LOGIN_OAUTH_FAILED_PATH } from "@/lib/auth/errors";

export default function AuthCallbackPage() {
  const { user, loading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!loading) {
      router.replace(user ? "/" : LOGIN_OAUTH_FAILED_PATH);
    }
  }, [loading, user, router]);

  return <FullPageSpinner />;
}
