import { Link, useLocation } from "react-router-dom";
import { Bot, Moon, Sun } from "lucide-react";
import { NAV_ITEMS } from "@/lib/navigation";
import { useDarkTheme } from "@/hooks/useDarkTheme";

export function SideNav() {
  const location = useLocation();
  const { dark, toggle } = useDarkTheme();

  return (
    <aside className="hidden md:flex flex-col w-56 sticky top-0 h-screen border-r border-border bg-card px-3 py-6 gap-1 shrink-0">
      <p className="flex items-center gap-2 text-base font-semibold text-foreground px-3 mb-4">
        <Bot className="h-5 w-5 shrink-0" />
        NAO Cvičenia
      </p>
      {NAV_ITEMS.map(({ path, icon: Icon, label }) => {
        const active = location.pathname === path;
        return (
          <Link
            key={path}
            to={path}
            className={[
              "flex items-center gap-3 px-3 py-2 rounded-base text-sm transition-colors",
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
      <button
        onClick={toggle}
        className="mt-auto flex items-center gap-3 px-3 py-2 rounded-base text-sm text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
      >
        {dark ? <Sun className="h-4 w-4 shrink-0" /> : <Moon className="h-4 w-4 shrink-0" />}
        {dark ? "Svetlý režim" : "Tmavý režim"}
      </button>
    </aside>
  );
}
