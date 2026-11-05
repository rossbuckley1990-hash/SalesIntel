import { DashboardShell } from "@/components/dashboard-shell";

export default function ClassicWorkspace() {
  return (
    <div className="classic-light classic-page">
      <div className="m-classic-banner">
        <a href="/">← Back to SalesIntel</a>
        <span>
          Classic modules · public connectors include fixtures · local
          unauthenticated workspace
        </span>
      </div>
      <DashboardShell />
    </div>
  );
}
