import type { ComponentType } from "react";
import { DropdownMenu } from "radix-ui";
import { Check, ChevronLeft, ChevronRight, Gauge, Languages, Loader2, MoreHorizontal, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { poseLabel, type PoseCommand } from "@/lib/poses";
import { SPEECH_LANGUAGES, SPEECH_SPEEDS } from "@/lib/voiceLines";

const MENU_CONTENT = "z-50 min-w-44 rounded-md border bg-popover p-1 text-popover-foreground shadow-md";
const MENU_ITEM = "flex items-center gap-2 rounded-sm px-2 py-1.5 text-sm outline-none cursor-default select-none data-[highlighted]:bg-accent data-[disabled]:opacity-50 data-[disabled]:pointer-events-none";

type Props = {
  poses: PoseCommand[];
  busy: boolean;
  language: string;
  speed: number;
  onInsertBefore: (pose: string) => void;
  onInsertAfter: (pose: string) => void;
  onVoiceChange: (language: string, speed: number) => void;
  onDelete: () => void;
};

// Frame options: insert pose before or after, speech voice, delete
export function FrameMenu({ poses, busy, language, speed, onInsertBefore, onInsertAfter, onVoiceChange, onDelete }: Props) {
  return (
    <DropdownMenu.Root modal={false}>
      <DropdownMenu.Trigger asChild>
        <Button variant="ghost" size="icon-sm" aria-label="Možnosti snímky" disabled={busy}>
          {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <MoreHorizontal className="h-4 w-4" />}
        </Button>
      </DropdownMenu.Trigger>
      <DropdownMenu.Portal>
        <DropdownMenu.Content align="end" sideOffset={4} className={MENU_CONTENT}>
          {([["Vložiť pózu pred", onInsertBefore, ChevronLeft], ["Vložiť pózu za", onInsertAfter, ChevronRight]] as const).map(
            ([label, onInsert, Icon]) => (
              <DropdownMenu.Sub key={label}>
                <DropdownMenu.SubTrigger className={MENU_ITEM} disabled={poses.length === 0}>
                  <Icon className="h-4 w-4 text-muted-foreground" />
                  {label}
                  <ChevronRight className="h-4 w-4 ml-auto text-muted-foreground" />
                </DropdownMenu.SubTrigger>
                <DropdownMenu.Portal>
                  <DropdownMenu.SubContent sideOffset={4} className={`${MENU_CONTENT} max-h-72 overflow-y-auto`}>
                    {poses.map((p) => (
                      <DropdownMenu.Item key={p.name} className={MENU_ITEM} onSelect={() => onInsert(p.name)}>
                        {poseLabel(p.name)}
                      </DropdownMenu.Item>
                    ))}
                  </DropdownMenu.SubContent>
                </DropdownMenu.Portal>
              </DropdownMenu.Sub>
            )
          )}
          <DropdownMenu.Separator className="my-1 h-px bg-border" />
          <RadioSubmenu
            icon={Languages}
            label="Jazyk reči"
            value={language}
            options={SPEECH_LANGUAGES}
            onChange={(lang) => onVoiceChange(lang, speed)}
          />
          <RadioSubmenu
            icon={Gauge}
            label="Rýchlosť reči"
            value={String(speed)}
            options={SPEECH_SPEEDS.map((rate) => [String(rate), `${rate} %`])}
            onChange={(rate) => onVoiceChange(language, Number(rate))}
          />
          <DropdownMenu.Separator className="my-1 h-px bg-border" />
          <DropdownMenu.Item className={`${MENU_ITEM} text-destructive data-[highlighted]:text-destructive`} onSelect={onDelete}>
            <Trash2 className="h-4 w-4" />
            Odstrániť snímku
          </DropdownMenu.Item>
        </DropdownMenu.Content>
      </DropdownMenu.Portal>
    </DropdownMenu.Root>
  );
}

type RadioSubmenuProps = {
  icon: ComponentType<{ className?: string }>;
  label: string;
  value: string;
  options: [string, string][];
  onChange: (value: string) => void;
};

function RadioSubmenu({ icon: Icon, label, value, options, onChange }: RadioSubmenuProps) {
  return (
    <DropdownMenu.Sub>
      <DropdownMenu.SubTrigger className={MENU_ITEM}>
        <Icon className="h-4 w-4 text-muted-foreground" />
        {label}
        <ChevronRight className="h-4 w-4 ml-auto text-muted-foreground" />
      </DropdownMenu.SubTrigger>
      <DropdownMenu.Portal>
        <DropdownMenu.SubContent sideOffset={4} className={MENU_CONTENT}>
          <DropdownMenu.RadioGroup value={value} onValueChange={onChange}>
            {options.map(([optionValue, optionLabel]) => (
              <DropdownMenu.RadioItem key={optionValue} value={optionValue} className={MENU_ITEM}>
                <span className="w-4">
                  <DropdownMenu.ItemIndicator><Check className="h-4 w-4" /></DropdownMenu.ItemIndicator>
                </span>
                {optionLabel}
              </DropdownMenu.RadioItem>
            ))}
          </DropdownMenu.RadioGroup>
        </DropdownMenu.SubContent>
      </DropdownMenu.Portal>
    </DropdownMenu.Sub>
  );
}
