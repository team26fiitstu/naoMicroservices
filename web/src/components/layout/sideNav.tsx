import { Link, useLocation } from "react-router-dom";
import { NAV_ITEMS } from "@/lib/navigation";

export function SideNav() {
  const location = useLocation();

  return (
    <aside className="hidden md:flex flex-col w-56 min-h-screen border-r border-border bg-card px-3 py-6 gap-1 shrink-0">
      <p className="text-xs font-semibold text-muted-foreground uppercase tracking-widest px-3 mb-4">
        NAO Cvičenia
      </p>
      {NAV_ITEMS.map(({ path, icon: Icon, label }) => {
        const active = location.pathname === path;
        return (
          <Link
            key={path}
            to={path}
            className={[
              "flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors",
              active
                ? "bg-primary/10 text-primary font-medium"
                : "text-muted-foreground hover:bg-muted hover:text-foreground",
            ].join(" ")}
          >
            <Icon className="h-4 w-4 shrink-0" />
            {label}
          </Link>
        );
      })}
    </aside>
  );
}
