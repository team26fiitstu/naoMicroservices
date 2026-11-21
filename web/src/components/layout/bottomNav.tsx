import { Link, useLocation } from "react-router-dom";
import { NAV_ITEMS } from "@/lib/navigation";

export function BottomNav() {
  const location = useLocation();

  return (
    <nav className="md:hidden fixed bottom-3 left-1/2 -translate-x-1/2 w-[92%] rounded-3xl backdrop-blur-xl shadow-gray-400 shadow-xl border border-gray-300 flex justify-around items-center py-3 z-50 bg-background/80">
      {NAV_ITEMS.map(({ path, icon: Icon, label }) => {
        const active = location.pathname === path;
        return (
          <Link key={path} to={path} aria-label={label} className="flex flex-col items-center">
            <Icon className={`w-7 h-7 transition-all ${active ? "text-primary scale-110" : "text-muted-foreground"}`} />
          </Link>
        );
      })}
    </nav>
  );
}
