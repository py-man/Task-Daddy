"use client";

import dynamic from "next/dynamic";
import { useEffect, useMemo, useState } from "react";
import { motion, useReducedMotion } from "framer-motion";
import { MarketingFallbackScene } from "@/components/marketing/fallback-scene";

const MarketingScene = dynamic(() => import("@/components/marketing/scene").then((m) => m.MarketingScene), {
  ssr: false
});

const sections = [
  { id: "hero", title: "Small tasks. Big momentum.", body: "Task-Daddy helps you organise work, plan your day, and finish what matters." },
  { id: "problem", title: "Stop keeping life in your head", body: "Capture quickly, then structure and execute with clear ownership and due dates." },
  { id: "features", title: "AI + Integrations + Flow", body: "Context-aware task enhancement, idempotent sync, and execution views that stay readable." },
  { id: "workflows", title: "Made for real daily rhythm", body: "Quick mobile capture, deeper desktop planning, and follow-through without overload." },
  { id: "cta", title: "You do not need perfect. You need a system.", body: "Start with one board and build momentum from there." }
];

function supportsWebGL() {
  try {
    const c = document.createElement("canvas");
    return !!(c.getContext("webgl") || c.getContext("experimental-webgl"));
  } catch {
    return false;
  }
}

export default function MarketingPage() {
  const reduceMotion = useReducedMotion();
  const [progress, setProgress] = useState(0);
  const [webgl, setWebgl] = useState(false);

  useEffect(() => {
    setWebgl(supportsWebGL());
  }, []);

  useEffect(() => {
    const onScroll = () => {
      const doc = document.documentElement;
      const max = Math.max(1, doc.scrollHeight - window.innerHeight);
      setProgress(Math.max(0, Math.min(1, window.scrollY / max)));
    };
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  const sectionProgress = useMemo(() => `${Math.round(progress * 100)}%`, [progress]);

  return (
    <main className="relative min-h-[100dvh] overflow-x-hidden bg-[#05070f] text-white">
      <div className="fixed inset-0 z-0 pointer-events-none">
        {!reduceMotion && webgl ? <MarketingScene progress={progress} /> : <MarketingFallbackScene />}
      </div>

      <header className="fixed top-4 left-1/2 z-20 w-[min(980px,94vw)] -translate-x-1/2 glass rounded-2xl border border-white/10 px-4 py-3 flex items-center justify-between">
        <div className="text-sm font-semibold tracking-wide">TASK-DADDY</div>
        <div className="text-xs text-muted">Route progress {sectionProgress}</div>
      </header>

      <div className="relative z-10">
        {sections.map((section, idx) => (
          <section key={section.id} id={section.id} className="min-h-[100dvh] flex items-center px-4 py-24">
            <motion.div
              initial={{ opacity: 0, y: 14 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, amount: 0.4 }}
              transition={{ duration: 0.35, delay: idx * 0.03 }}
              className="mx-auto w-[min(980px,94vw)] glass nl-marketing-card rounded-3xl p-6 md:p-10"
            >
              <div className="text-xs uppercase tracking-[0.16em] text-cyan-200">{section.id}</div>
              <h2 className="mt-2 text-3xl md:text-5xl font-semibold leading-tight text-white">{section.title}</h2>
              <p className="mt-4 text-sm md:text-base text-white/85 max-w-2xl">{section.body}</p>
              {section.id === "hero" ? (
                <div className="mt-6 flex flex-wrap gap-3">
                  <a href="/login" className="rounded-xl px-4 py-2 bg-cyan-300 text-black font-medium shadow-[0_0_0_1px_rgba(255,255,255,0.15)]">
                    Start Free
                  </a>
                  <a href="/app/board" className="rounded-xl px-4 py-2 border border-white/45 text-white bg-white/5">
                    Live Demo
                  </a>
                </div>
              ) : null}
            </motion.div>
          </section>
        ))}
      </div>
    </main>
  );
}
