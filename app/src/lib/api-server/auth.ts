import { createClient } from "@/lib/supabase/server";
import { HttpError } from "./errors";

export async function requireUser() {
  const supabase = await createClient();
  const {
    data: { user },
    error,
  } = await supabase.auth.getUser();

  if (error || !user) {
    throw new HttpError("Unauthorized", 401);
  }

  return { supabase, user };
}
