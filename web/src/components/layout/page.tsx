import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

type Props = {
  title: string;
  description?: ReactNode;
  actions?: ReactNode;
  // last child stretched to bottom gap, only while content fills screen width
  fill?: boolean;
  children: ReactNode;
};

// Page with header, same width and spacing on every page
export function Page({ title, description, actions, fill, children }: Props) {
  return (
    <div
      className={cn(
        // own padding on mobile, bottom one above bottom menu, gap from app shell on desktop
        "w-full max-w-7xl mx-auto px-(--layout-gap) pt-(--layout-gap) pb-24 md:p-0 space-y-(--layout-gap)",
        fill && "fill-screen:flex fill-screen:flex-col fill-screen:min-h-[calc(100vh-2*var(--layout-gap))]",
      )}
    >
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
