import type { ReactNode } from "react";

type Props = { title: string; description?: ReactNode; actions?: ReactNode; children: ReactNode };

// Page with header, same width and spacing on every page
export function Page({ title, description, actions, children }: Props) {
  return (
    <div className="w-full max-w-7xl mx-auto px-4 py-6 pb-24 space-y-4">
      <div className="flex items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-semibold tracking-tight text-foreground">{title}</h1>
          {description && <div className="text-xs text-muted-foreground mt-0.5">{description}</div>}
        </div>
        {actions && <div className="flex items-center gap-2">{actions}</div>}
      </div>
      {children}
    </div>
  );
}
