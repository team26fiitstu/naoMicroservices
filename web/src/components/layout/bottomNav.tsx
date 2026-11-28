import { Link, useLocation } from "react-router-dom";
import { Moon, Sun } from "lucide-react";
import { NAV_ITEMS } from "@/lib/navigation";
import { useDarkTheme } from "@/hooks/useDarkTheme";

export function BottomNav() {
  const location = useLocation();
  const { dark, toggle } = useDarkTheme();

  return (
    <nav className="md:hidden fixed bottom-(--layout-gap) inset-x-(--layout-gap) rounded-base backdrop-blur-xl shadow-xl border border-border flex justify-around items-center py-3 z-50 bg-background/80">
      {NAV_ITEMS.map(({ path, icon: Icon, label }) => {
        const active = location.pathname === path;
        return (
          <Link key={path} to={path} aria-label={label} className="flex flex-col items-center">
            <Icon className={`w-7 h-7 transition-all ${active ? "text-primary scale-110" : "text-muted-foreground"}`} />
          </Link>
        );
      })}
      <button onClick={toggle} aria-label={dark ? "Svetlý režim" : "Tmavý režim"} className="flex flex-col items-center">
        {dark ? <Sun className="w-7 h-7 text-muted-foreground" /> : <Moon className="w-7 h-7 text-muted-foreground" />}
      </button>
    </nav>
  );
}
