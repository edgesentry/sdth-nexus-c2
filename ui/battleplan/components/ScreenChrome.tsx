import Link from "next/link";

type Props = {
  role: "hub" | "command" | "recipient";
  children: React.ReactNode;
  status?: string;
};

export function ScreenChrome({ role, children, status }: Props) {
  return (
    <div className="bp-shell">
      <header className="bp-header">
        <div className="bp-brand">
          <span className="bp-brand-mark">NexusGate</span>
          <span className="bp-brand-sub">BattlePlan</span>
        </div>
        <nav className="bp-nav" aria-label="Screens">
          <Link
            href="/"
            className={role === "hub" ? "bp-nav-link active" : "bp-nav-link"}
          >
            Hub
          </Link>
          <Link
            href="/command"
            className={
              role === "command" ? "bp-nav-link active" : "bp-nav-link"
            }
          >
            Screen 1 · Command
          </Link>
          <Link
            href="/recipient"
            className={
              role === "recipient" ? "bp-nav-link active" : "bp-nav-link"
            }
          >
            Screen 2 · Recipient
          </Link>
        </nav>
        {status ? <p className="bp-status">{status}</p> : null}
      </header>
      <main className="bp-main">{children}</main>
    </div>
  );
}
