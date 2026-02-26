"use client";

import { useEffect, useRef } from "react";

export function MarketingScene({ progress }: { progress: number }) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const progressRef = useRef(progress);

  useEffect(() => {
    progressRef.current = progress;
  }, [progress]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    let raf = 0;
    let alive = true;

    const resize = () => {
      const dpr = Math.min(1.6, window.devicePixelRatio || 1);
      const width = window.innerWidth;
      const height = window.innerHeight;
      canvas.width = Math.floor(width * dpr);
      canvas.height = Math.floor(height * dpr);
      canvas.style.width = `${width}px`;
      canvas.style.height = `${height}px`;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    };

    const draw = (time: number) => {
      if (!alive) return;
      const width = window.innerWidth;
      const height = window.innerHeight;
      const p = progressRef.current;
      const horizon = height * (0.28 + p * 0.08);
      const speed = 0.00008;
      const zShift = (time * speed + p * 2.8) % 1;

      ctx.clearRect(0, 0, width, height);
      const bg = ctx.createLinearGradient(0, 0, 0, height);
      bg.addColorStop(0, "#05070f");
      bg.addColorStop(1, "#060915");
      ctx.fillStyle = bg;
      ctx.fillRect(0, 0, width, height);

      const fog = ctx.createRadialGradient(width * 0.5, height * 0.25, 0, width * 0.5, height * 0.45, width * 0.8);
      fog.addColorStop(0, "rgba(94,255,224,0.20)");
      fog.addColorStop(0.5, "rgba(208,96,255,0.12)");
      fog.addColorStop(1, "rgba(4,7,14,0)");
      ctx.fillStyle = fog;
      ctx.fillRect(0, 0, width, height);

      ctx.save();
      ctx.translate(width / 2, horizon);

      for (let i = 0; i < 24; i++) {
        const t = ((i / 24 + zShift) % 1) + 0.0001;
        const y = t * t * height * 1.4;
        const alpha = Math.max(0.04, 1 - t) * 0.34;
        ctx.strokeStyle = `rgba(102,232,249,${alpha})`;
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.moveTo(-width, y);
        ctx.lineTo(width, y);
        ctx.stroke();
      }

      const lanes = 11;
      for (let i = -lanes; i <= lanes; i++) {
        const x = (i / lanes) * (width * 0.55);
        const laneAlpha = 0.08 + (1 - Math.abs(i) / lanes) * 0.24;
        ctx.strokeStyle = i % 2 ? `rgba(217,70,239,${laneAlpha})` : `rgba(103,232,249,${laneAlpha})`;
        ctx.beginPath();
        ctx.moveTo(x, 0);
        ctx.lineTo(x * 2.6, height);
        ctx.stroke();
      }

      ctx.restore();

      ctx.strokeStyle = "rgba(255,255,255,0.08)";
      for (let i = 0; i < 7; i++) {
        const y = horizon + (i * height) / 9;
        ctx.beginPath();
        ctx.moveTo(width * 0.12, y);
        ctx.lineTo(width * 0.88, y);
        ctx.stroke();
      }

      raf = window.requestAnimationFrame(draw);
    };

    resize();
    window.addEventListener("resize", resize);
    raf = window.requestAnimationFrame(draw);

    return () => {
      alive = false;
      window.removeEventListener("resize", resize);
      window.cancelAnimationFrame(raf);
    };
  }, []);

  return <canvas ref={canvasRef} className="absolute inset-0 h-full w-full" aria-hidden />;
}
