import { Home, Upload, FilmIcon, Mic, Library, Workflow, type LucideIcon } from "lucide-react";

type NavItem = { path: string; icon: LucideIcon; label: string; description?: string };

// Single source for side menu, bottom menu and home page cards
export const NAV_ITEMS: NavItem[] = [
  { path: "/", icon: Home, label: "Domov" },
  {
    path: "/upload",
    icon: Upload,
    label: "Nahranie",
    description: "Nahrajte video alebo obrázok a vytvorte z neho cvičenie.",
  },
  {
    path: "/edit",
    icon: FilmIcon,
    label: "Editor",
    description: "Nahrajte video pre extrakciu snímok, zoraďte ich, vložte pomenované pózy a spustite celú sekvenciu na robotovi.",
  },
  {
    path: "/voice",
    icon: Mic,
    label: "Hlasové príkazy",
    description: "Ovládajte robota NAO hlasom. Povedzte názov pózy a robot ju okamžite vykoná.",
  },
  {
    path: "/exercises",
    icon: Library,
    label: "Cvičenia",
    description: "Prehliadajte, premenúvajte, mažte a spúšťajte uložené cvičenia.",
  },
  {
    path: "/choreographies",
    icon: Workflow,
    label: "Choreografie",
    description: "Spojte cvičenia do grafu stavov s prechodmi medzi nimi.",
  },
];
