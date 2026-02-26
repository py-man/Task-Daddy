"use client";

import { motion, useMotionTemplate, useReducedMotion, useScroll, useTransform } from "framer-motion";
import { useMemo, useRef, useState } from "react";

const ENABLED = process.env.NEXT_PUBLIC_ENABLE_3D_LAB !== "0";

const ZONES = [
  { key: "hero", title: "Hero", z: 0, body: "Scroll-driven camera intro with neon lanes." },
  { key: "about", title: "About", z: -50, body: "Glass overlay panels over an ambient cyber grid." },
  { key: "product", title: "Product", z: -100, body: "Product signals appear while the camera travels deeper." },
  { key: "features", title: "Features", z: -150, body: "Feature cards and conversion copy stay crisp and readable." },
  { key: "cta", title: "CTA", z: -200, body: "Camera eases and background converges for final conversion." }
];

export default function Neon3DLabPage() {
  const reducedMotion = useReducedMotion();
  const [forceMotionPreview, setForceMotionPreview] = useState(false);
  const motionEnabled = !reducedMotion || forceMotionPreview;
  const viewportRef = useRef<HTMLDivElement | null>(null);
  const { scrollYProgress } = useScroll({ target: viewportRef, offset: ["start start", "end end"] });
  const cameraZ = useTransform(scrollYProgress, [0, 1], [0, -200]);
  const laneShift = useTransform(scrollYProgress, [0, 1], [0, -120]);
  const laneGlow = useTransform(scrollYProgress, [0, 1], [0.28, 0.58]);
  const zoneDrift = useTransform(scrollYProgress, [0, 1], [0, -60]);
  const progressWidth = useTransform(scrollYProgress, (v) => `${Math.round(v * 100)}%`);
  const progressPct = useTransform(scrollYProgress, (v) => `${Math.round(v * 100)}%`);
  const cameraTransform = useMotionTemplate`translate3d(0,0,${cameraZ}px)`;

  const status = useMemo(() => {
    if (reducedMotion && !forceMotionPreview) return "Reduced motion active";
    if (reducedMotion && forceMotionPreview) return "Preview motion override active";
    if (!ENABLED) return "Lab disabled (set NEXT_PUBLIC_ENABLE_3D_LAB=1)";
    return "Lab enabled";
  }, [forceMotionPreview, reducedMotion]);

  if (!ENABLED) {
    return (
      <div className="h-full overflow-auto px-4 py-8 md:px-8">
        <div className="mx-auto max-w-3xl glass rounded-3xl border border-white/10 p-6">
          <h1 className="text-xl font-semibold">3D Lab is disabled</h1>
          <p className="mt-2 text-sm text-muted">
            This route is isolated for UI experiments only. Enable with <code>NEXT_PUBLIC_ENABLE_3D_LAB=1</code>.
          </p>
          <p className="mt-4 text-xs text-muted">Non-regression: no product routes are modified by this lab.</p>
        </div>
      </div>
    );
  }

  return (
    <div ref={viewportRef} className="nl3d-lab h-[100dvh] overflow-y-auto">
      <div className="nl3d-stage">
        <motion.div
          aria-hidden
          className="nl3d-grid"
          style={motionEnabled ? { y: laneShift, opacity: laneGlow } : undefined}
        />
        <motion.div aria-hidden className="nl3d-fog" style={motionEnabled ? { opacity: laneGlow } : undefined} />
        <motion.div aria-hidden className="nl3d-streaks" style={motionEnabled ? { y: zoneDrift } : undefined} />
        <motion.div
          aria-hidden
          className="nl3d-camera"
          style={motionEnabled ? { transform: cameraTransform } : undefined}
        />

        <div className="nl3d-progress glass" aria-hidden>
          <div className="nl3d-progress-track">
            <motion.div className="nl3d-progress-fill" style={{ width: progressWidth }} />
          </div>
          <div className="text-[11px] text-muted mt-1">
            Scroll depth <motion.span>{progressPct}</motion.span>
          </div>
        </div>

        <div className="nl3d-overlay">
          <div className="nl3d-head">
            <span className="nl3d-pill">{status}</span>
            {reducedMotion ? (
              <button className="nl3d-toggle" onClick={() => setForceMotionPreview((v) => !v)} type="button">
                {forceMotionPreview ? "Use reduced motion" : "Preview motion anyway"}
              </button>
            ) : null}
            <h1>Task-Daddy 3D UX Lab</h1>
            <p>Scroll down this page to travel lanes in depth. Overlay UI stays readable and conversion-focused.</p>
          </div>

          <div className="nl3d-zones">
            {ZONES.map((zone, index) => (
              <motion.section
                key={zone.key}
                className="nl3d-card nl3d-card--zone glass"
                initial={{ opacity: 0, y: 12, scale: 0.98 }}
                whileInView={{ opacity: 1, y: 0, scale: 1 }}
                viewport={{ once: true, amount: 0.3 }}
                transition={{ duration: 0.22, delay: index * 0.03 }}
              >
                <div className="nl3d-card-top">
                  <span>{zone.title}</span>
                  <span>Z {zone.z}</span>
                </div>
                <p>{zone.body}</p>
              </motion.section>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
