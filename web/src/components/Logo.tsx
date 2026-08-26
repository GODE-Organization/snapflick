export function Logo({ className = "" }: { className?: string }) {
  return (
    <span className={`inline-flex items-center gap-2 ${className}`}>
      <span className="grid h-8 w-8 place-items-center rounded-lg gradient-ai text-sm font-bold text-white">
        SF
      </span>
      <span className="text-headline-md font-semibold tracking-tight text-primary">SnapFlick</span>
    </span>
  );
}
