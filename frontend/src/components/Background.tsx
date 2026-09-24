import { useEffect, useState, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { getBackgroundConfig } from "../lib/backgrounds";

export default function Background() {
  const [current, setCurrent] = useState(0);
  const [loaded, setLoaded] = useState<Set<number>>(new Set());
  const [scrollY, setScrollY] = useState(0);
  const rafRef = useRef<number>(0);
  const config = getBackgroundConfig();
  const urls = config.urls;

  useEffect(() => {
    setLoaded(new Set());
    urls.forEach((src, i) => {
      const img = new Image();
      img.src = src;
      img.onload = () => setLoaded((s) => new Set(s).add(i));
    });
  }, [urls]);

  useEffect(() => {
    if (loaded.size === 0) return;
    const interval = setInterval(() => {
      setCurrent((prev) => (prev + 1) % urls.length);
    }, config.interval * 1000);
    return () => clearInterval(interval);
  }, [loaded.size, urls.length, config.interval]);

  useEffect(() => {
    const onScroll = () => {
      cancelAnimationFrame(rafRef.current);
      rafRef.current = requestAnimationFrame(() => setScrollY(window.scrollY));
    };
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  if (urls.length === 0) return null;

  return (
    <div className="fixed inset-0 -z-10 overflow-hidden">
      <div className="absolute inset-0 bg-slate-950" />

      <AnimatePresence mode="popLayout">
        <motion.div
          key={current}
          initial={{ opacity: 0, scale: 1.08 }}
          animate={{ opacity: config.opacity, scale: 1.0 }}
          exit={{ opacity: 0, scale: 1.02 }}
          transition={{ opacity: { duration: 2, ease: "easeInOut" }, scale: { duration: 12, ease: "easeOut" } }}
          className="absolute inset-0 w-full h-full"
          style={{
            backgroundImage: `url(${urls[current]})`,
            backgroundSize: "cover",
            backgroundPosition: "center",
            transform: `translateY(${scrollY * 0.15}px)`,
            filter: `blur(${config.blur}px) saturate(1.4)`,
          }}
        />
      </AnimatePresence>

      <div className="absolute inset-0 bg-gradient-to-b from-slate-950/70 via-slate-950/80 to-slate-950/95" />

      <div className="absolute top-[-10%] left-[5%] w-[500px] h-[500px] rounded-full bg-emerald-600/[0.06] blur-[120px] animate-aurora-drift" />
      <div className="absolute top-[30%] right-[-5%] w-[600px] h-[600px] rounded-full bg-sky-600/[0.05] blur-[140px] animate-aurora-shift" />
      <div className="absolute bottom-[-10%] left-[30%] w-[450px] h-[450px] rounded-full bg-violet-600/[0.04] blur-[100px] animate-aurora-drift" />

      <div
        className="absolute inset-0 opacity-[0.02]"
        style={{
          backgroundImage: `url("data:image/svg+xml,%3Csvg viewBox='0 0 400 400' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)'/%3E%3C/svg%3E")`,
        }}
      />
    </div>
  );
}
