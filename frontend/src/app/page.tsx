import { HostedApp } from "@/features/hosted/hosted-app";
import { LivingWorkspace } from "@/features/workspace/shell";

// A single-user local install keeps its full workspace. Signed-in teams get the tenant-scoped SalesIntel.
export default function Home() {
  return (process.env.NEXT_PUBLIC_AUTH_MODE || "local") === "local" ? <LivingWorkspace /> : <HostedApp />;
}
