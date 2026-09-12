import { Icon } from "./Icon";

export function Logo({ className = "" }: { className?: string }) {
  return (
    <span className={`inline-flex items-center gap-2 ${className}`}>
      <span className="grid h-8 w-8 shrink-0 place-items-center rounded-lg gradient-ai shadow-glow">
        <Icon name="auto_fix_high" className="text-[18px] text-white" filled />
      </span>
      <span className="text-headline-md font-semibold tracking-tight text-primary">SnapFlick</span>
    </span>
  );
}
