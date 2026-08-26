"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Icon } from "./Icon";
import { Logo } from "./Logo";

const NAV = [
  { href: "/", label: "Dashboard" },
  { href: "/", label: "Catálogos" },
];

const QUICK_ACTIONS = [
  { href: "/", label: "Nuevo lote", icon: "add_circle", color: "text-electric-indigo" },
  { href: "/", label: "Generador IA", icon: "auto_awesome", color: "text-vivid-cyan" },
];

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();

  return (
    <>
      <header className="fixed top-0 z-50 w-full border-b border-outline-variant bg-surface/80 backdrop-blur-xl">
        <div className="flex h-16 w-full items-center justify-between px-4 sm:px-margin-desktop">
          <div className="flex items-center gap-8">
            <Link href="/">
              <Logo />
            </Link>
            <nav className="hidden items-center gap-6 md:flex">
              {NAV.map((item) => (
                <Link
                  key={item.label}
                  href={item.href}
                  className={`font-mono text-label-md transition-colors ${
                    pathname === item.href
                      ? "font-bold text-primary"
                      : "text-on-surface-variant hover:text-primary"
                  }`}
                >
                  {item.label}
                </Link>
              ))}
            </nav>
          </div>
          <div className="flex items-center gap-4">
            <button className="rounded-full p-2 text-on-surface-variant transition-all hover:bg-surface-container-high">
              <Icon name="notifications" />
            </button>
            <div className="flex items-center gap-3 border-l border-outline-variant pl-4">
              <div className="hidden text-right sm:block">
                <p className="font-mono text-label-sm text-on-surface">Mi negocio</p>
                <p className="font-mono text-label-sm text-on-surface-variant opacity-70">Local</p>
              </div>
              <div className="flex h-8 w-8 items-center justify-center rounded-full bg-primary text-on-primary ring-2 ring-primary/10">
                <Icon name="storefront" className="text-[18px]" />
              </div>
            </div>
          </div>
        </div>
      </header>

      <aside className="fixed left-0 top-16 z-40 hidden h-[calc(100vh-64px)] w-64 flex-col border-r border-outline-variant bg-surface-container-lowest py-6 lg:flex">
        <div className="mb-4 px-6">
          <span className="font-mono text-label-sm uppercase tracking-widest text-on-surface-variant">
            Acciones rápidas
          </span>
        </div>
        <nav className="flex-1 space-y-1 px-3">
          {QUICK_ACTIONS.map((item) => (
            <Link
              key={item.label}
              href={item.href}
              className="group flex items-center rounded-xl px-4 py-3 text-on-surface-variant transition-all hover:bg-surface-container-high"
            >
              <Icon name={item.icon} className={`mr-3 ${item.color}`} />
              <span className="font-mono text-label-md">{item.label}</span>
            </Link>
          ))}
        </nav>
      </aside>

      <div className="lg:pl-64">
        <main className="relative min-h-screen bg-background pt-16">{children}</main>
      </div>
    </>
  );
}
