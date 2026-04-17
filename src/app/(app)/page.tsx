import { createClient } from "@/lib/supabase/server";
import { redirect } from "next/navigation";
import { HomeDashboard } from "@/components/home/HomeDashboard";

export default async function HomePage() {
  const supabase = await createClient();
  const { data: { user }, error } = await supabase.auth.getUser();
  if (error || !user) redirect("/login");
  return <HomeDashboard />;
}
