import { useEffect, useState, useRef } from "react";
import { motion } from "framer-motion";

const HERO = "https://images.unsplash.com/photo-1600596542815-ffad4c1539a9?w=1920&q=80";
const DEPTH = "https://images.unsplash.com/photo-1560448204-e02f11c3d0e2?w=1920&q=80";

export default function LoginBackground() {
  const [loaded, setLoaded] = useState(false);
  const [mouse, setMouse] = useState({ x: 0, y: 0 });
  const containerRef = useRef<HTMLDivElement>(null);
  const rafRef = useRef<number>(0);

  useEffect(() => {
    const img = new Image();
    img.src = HERO;
    img.onload = () => setLoaded(true);
    const img2 = new Image();
    img2.src = DEPTH;
  }, []);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;
    const onMove = (e: MouseEvent) => {
      const rect = container.getBoundingClientRect();
      const x = (e.clientX - rect.left) / rect.width - 0.5;
      const y = (e.clientY - rect.top) / rect.height - 0.5;
      cancelAnimationFrame(rafRef.current);
      rafRef.current = requestAnimationFrame(() => setMouse({ x, y }));
    };
    container.addEventListener("mousemove", onMove);
    return () => {
      container.removeEventListener("mousemove", onMove);
      cancelAnimationFrame(rafRef.current);
    };
  }, []);

  return (
    <div ref={containerRef} className="absolute inset-0 overflow-hidden">
      <div className="absolute inset-0 bg-slate-950" />

      {loaded && (
        <>
          <motion.div
            className="absolute inset-0 w-full h-full"
            animate={{
              scale: [1, 1.04, 1],
              rotate: mouse.x * 0.5,
            }}
            transition={{
              scale: { duration: 12, repeat: Infinity, ease: "easeInOut" },
              rotate: { type: "spring", stiffness: 50, damping: 30 },
            }}
            style={{
              backgroundImage: `url(${HERO})`,
              backgroundSize: "cover",
              backgroundPosition: "center",
              filter: "blur(12px) saturate(1.3)",
              transform: `perspective(1000px) rotateY(${mouse.x * 3}deg) rotateX(${-mouse.y * 3}deg)`,
              transformStyle: "preserve-3d",
            }}
          />

          <motion.div
            className="absolute inset-0 w-full h-full opacity-60"
            animate={{
              scale: [1, 1.06, 1],
              x: mouse.x * 20,
              y: mouse.y * 20,
            }}
            transition={{
              scale: { duration: 15, repeat: Infinity, ease: "easeInOut" },
              x: { type: "spring", stiffness: 30, damping: 25 },
              y: { type: "spring", stiffness: 30, damping: 25 },
            }}
            style={{
              backgroundImage: `url(${DEPTH})`,
              backgroundSize: "cover",
              backgroundPosition: "center",
              filter: "blur(20px) saturate(1.2) brightness(0.7)",
              transform: `perspective(1000px) rotateY(${-mouse.x * 2}deg) rotateX(${mouse.y * 2}deg)`,
              transformStyle: "preserve-3d",
            }}
          />
        </>
      )}

      <div className="absolute inset-0 bg-gradient-to-b from-slate-950/60 via-slate-950/75 to-slate-950/95" />

      <div className="absolute top-[-5%] left-[10%] w-[400px] h-[400px] rounded-full bg-emerald-500/[0.07] blur-[100px] animate-aurora-drift" />
      <div className="absolute bottom-[-5%] right-[10%] w-[500px] h-[500px] rounded-full bg-sky-500/[0.05] blur-[120px] animate-aurora-shift" />
      <div className="absolute top-[50%] left-[50%] w-[300px] h-[300px] rounded-full bg-violet-500/[0.03] blur-[80px] -translate-x-1/2 -translate-y-1/2 animate-aurora-drift" />

      <div className="absolute bottom-0 inset-x-0 h-px bg-gradient-to-r from-transparent via-emerald-400/30 to-transparent" />

      {[...Array(6)].map((_, i) => (
        <motion.div
          key={i}
          className="absolute w-1 h-1 rounded-full bg-emerald-400/30"
          initial={{
            x: Math.random() * 100 + "%",
            y: "100%",
            opacity: 0,
          }}
          animate={{
            y: "-10%",
            opacity: [0, 0.6, 0],
            scale: [0, 1.5, 0],
          }}
          transition={{
            duration: 6 + Math.random() * 8,
            repeat: Infinity,
            delay: Math.random() * 10,
            ease: "easeInOut",
          }}
          style={{
            filter: "blur(1px)",
            boxShadow: "0 0 6px rgba(52,211,153,0.3)",
          }}
        />
      ))}

      <div
        className="absolute inset-0 opacity-[0.015]"
        style={{
          backgroundImage: `url("data:image/svg+xml,%3Csvg viewBox='0 0 400 400' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)'/%3E%3C/svg%3E")`,
        }}
      />
    </div>
  );
}
