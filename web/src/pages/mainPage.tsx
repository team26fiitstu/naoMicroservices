import { useNavigate } from "react-router-dom";
import { NAV_ITEMS } from "@/lib/navigation";

export default function MainPage() {
  const navigate = useNavigate();

  return (
    <div className="w-full max-w-2xl mx-auto px-4 py-10 pb-24 space-y-8">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight text-foreground">NAO Cvičenia</h1>
        <p className="text-sm text-muted-foreground mt-2 leading-relaxed">
          Nástroj na vytváranie, úpravu a spúšťanie sekvencií fyzických cvičení na humanoidnom robotovi NAO.
          Nahrajte videá na extrakciu snímok, zostavte vlastné sekvencie, ovládajte robota hlasom
          alebo posielajte pózy priamo z prehliadača.
        </p>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        {NAV_ITEMS.filter((item) => item.description).map(({ icon: Icon, label, description, path }) => (
          <button
            key={path}
            onClick={() => navigate(path)}
            className="text-left rounded-xl border border-border bg-card p-4 hover:bg-muted/50 transition-colors space-y-2"
          >
            <div className="flex items-center gap-2">
              <div className="w-8 h-8 rounded-lg bg-primary/10 flex items-center justify-center">
                <Icon className="h-4 w-4 text-primary" />
              </div>
              <span className="text-sm font-medium text-foreground">{label}</span>
            </div>
            <p className="text-xs text-muted-foreground leading-relaxed">{description}</p>
          </button>
        ))}
      </div>
    </div>
  );
}
