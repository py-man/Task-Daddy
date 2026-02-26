"use client";

export function MarketingFallbackScene() {
  return (
    <div
      aria-hidden
      className="absolute inset-0"
      style={{
        background:
          "radial-gradient(900px 420px at 50% 18%, rgba(88,255,224,0.2), transparent 62%), radial-gradient(760px 380px at 75% 45%, rgba(220,92,255,0.18), transparent 65%), linear-gradient(180deg, #060915 0%, #05060e 100%)"
      }}
    >
      <div className="absolute inset-0 opacity-30 [background-size:64px_64px] [background-image:linear-gradient(rgba(255,255,255,0.08)_1px,transparent_1px),linear-gradient(90deg,rgba(255,255,255,0.07)_1px,transparent_1px)]" />
    </div>
  );
}
