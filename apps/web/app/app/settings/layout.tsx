import { SettingsNav } from "@/components/settings-nav";

export default function SettingsLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="nl-settings h-full overflow-hidden">
      <div className="h-full overflow-auto px-4 pb-24 md:pb-6 scrollbar">
        <div className="mt-4 grid grid-cols-1 lg:grid-cols-[280px_1fr] gap-4 items-start">
          <SettingsNav />
          <div className="nl-settings-content">{children}</div>
        </div>
      </div>
    </div>
  );
}
