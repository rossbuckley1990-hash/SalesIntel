import { DashboardShell } from "@/components/dashboard-shell";

export default function ClassicWorkspace() {
  return (
    <>
      <div className="m-classic-banner">
        <a href="/">← Living workspace</a>
        <span>
          Classic modules · public connectors include fixtures · local
          unauthenticated workspace
        </span>
      </div>
      <DashboardShell />
    </>
  );
}
