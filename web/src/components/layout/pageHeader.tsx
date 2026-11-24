import type { ReactNode } from "react";

type Props = { title: string; description?: ReactNode; actions?: ReactNode };

export function PageHeader({ title, description, actions }: Props) {
  return (
    <div className="flex items-center justify-between gap-4">
      <div>
        <h1 className="text-xl font-semibold tracking-tight text-foreground">{title}</h1>
        {description && <div className="text-xs text-muted-foreground mt-0.5">{description}</div>}
      </div>
      {actions && <div className="flex items-center gap-2">{actions}</div>}
    </div>
  );
}
