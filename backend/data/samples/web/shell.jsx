/* ─────────────────────────────────────────────────────────────
   shell.jsx — shared app chrome + design-system primitives
   Exports to window: Icon, AppShell, StatusDot, Pill, SourceBadge,
   Staleness, Gauge, DimBar, ComplexityChip, PriorityBadge, BandPip,
   AgentFeed, Btn, SectionLabel, RunPill, MiniSpark
   ───────────────────────────────────────────────────────────── */

// ── Icon set (simple line icons, lucide-ish) ──────────────────
const ICON_PATHS = {
  cpu: "M9 2v3M15 2v3M9 19v3M15 19v3M2 9h3M2 15h3M19 9h3M19 15h3M6 6h12v12H6zM9 9h6v6H9z",
  layers: "M12 2l9 5-9 5-9-5 9-5zM3 12l9 5 9-5M3 17l9 5 9-5",
  settings: "M12 15a3 3 0 100-6 3 3 0 000 6zM19.4 15a1.6 1.6 0 00.3 1.8l.1.1a2 2 0 11-2.8 2.8l-.1-.1a1.6 1.6 0 00-2.7 1.1V21a2 2 0 11-4 0v-.1A1.6 1.6 0 005 19.4l-.1.1a2 2 0 11-2.8-2.8l.1-.1a1.6 1.6 0 00-1.1-2.7H1a2 2 0 110-4h.1A1.6 1.6 0 002.6 5l-.1-.1a2 2 0 112.8-2.8l.1.1a1.6 1.6 0 001.8.3H9a1.6 1.6 0 001-1.5V1a2 2 0 114 0v.1a1.6 1.6 0 001 1.5 1.6 1.6 0 001.8-.3l.1-.1a2 2 0 112.8 2.8l-.1.1a1.6 1.6 0 00-.3 1.8V9a1.6 1.6 0 001.5 1H23a2 2 0 110 4h-.1a1.6 1.6 0 00-1.5 1z",
  logout: "M9 21H5a2 2 0 01-2-2V5a2 2 0 012-2h4M16 17l5-5-5-5M21 12H9",
  chevR: "M9 18l6-6-6-6",
  chevD: "M6 9l6 6 6-6",
  plus: "M12 5v14M5 12h14",
  arrowR: "M5 12h14M13 6l6 6-6 6",
  play: "M6 4l14 8-14 8V4z",
  bot: "M12 8V4M8 2h8M9 13v2M15 13v2M5 8h14a2 2 0 012 2v8a2 2 0 01-2 2H5a2 2 0 01-2-2v-8a2 2 0 012-2z",
  spark: "M12 3l1.9 5.6L19 10l-5.1 1.4L12 17l-1.9-5.6L5 10l5.1-1.4L12 3z",
  doc: "M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8l-6-6zM14 2v6h6",
  upload: "M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4M17 8l-5-5-5 5M12 3v12",
  check: "M20 6L9 17l-5-5",
  alert: "M10.3 3.9L1.8 18a2 2 0 001.7 3h17a2 2 0 001.7-3L14.4 3.9a2 2 0 00-3.4 0zM12 9v4M12 17h.01",
  edit: "M11 4H4a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2v-7M18.5 2.5a2.1 2.1 0 013 3L12 15l-4 1 1-4 9.5-9.5z",
  clock: "M12 22a10 10 0 100-20 10 10 0 000 20zM12 6v6l4 2",
  calendar: "M8 2v4M16 2v4M3 10h18M5 4h14a2 2 0 012 2v14a2 2 0 01-2 2H5a2 2 0 01-2-2V6a2 2 0 012-2z",
  grid: "M3 3h7v7H3zM14 3h7v7h-7zM14 14h7v7h-7zM3 14h7v7H3z",
  list: "M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01",
  download: "M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4M7 10l5 5 5-5M12 15V3",
  refresh: "M3 12a9 9 0 0115-6.7L21 8M21 3v5h-5M21 12a9 9 0 01-15 6.7L3 16M3 21v-5h5",
  history: "M3 12a9 9 0 109-9 9 9 0 00-6.4 2.6L3 8M3 3v5h5M12 7v5l4 2",
  flag: "M4 15s1-1 4-1 5 2 8 2 4-1 4-1V3s-1 1-4 1-5-2-8-2-4 1-4 1zM4 22v-7",
  user: "M20 21v-2a4 4 0 00-4-4H8a4 4 0 00-4 4v2M12 11a4 4 0 100-8 4 4 0 000 8z",
  search: "M11 19a8 8 0 100-16 8 8 0 000 16zM21 21l-4.3-4.3",
  filter: "M22 3H2l8 9.5V19l4 2v-8.5L22 3z",
  target: "M12 22a10 10 0 100-20 10 10 0 000 20zM12 18a6 6 0 100-12 6 6 0 000 12zM12 14a2 2 0 100-4 2 2 0 000 4z",
  link: "M10 13a5 5 0 007 0l3-3a5 5 0 00-7-7l-1 1M14 11a5 5 0 00-7 0l-3 3a5 5 0 007 7l1-1",
  gauge: "M12 14l4-4M3.3 18a9 9 0 1117.4 0",
  zap: "M13 2L3 14h9l-1 8 10-12h-9l1-8z",
  dots: "M12 13a1 1 0 100-2 1 1 0 000 2zM19 13a1 1 0 100-2 1 1 0 000 2zM5 13a1 1 0 100-2 1 1 0 000 2z",
  x: "M18 6L6 18M6 6l12 12",
  sliders: "M4 21v-7M4 10V3M12 21v-9M12 8V3M20 21v-5M20 12V3M1 14h6M9 8h6M17 16h6",
};

function Icon({ name, size = 16, sw = 1.8, style, fill }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill={fill || "none"}
      stroke={fill ? "none" : "currentColor"} strokeWidth={sw} strokeLinecap="round"
      strokeLinejoin="round" style={{ flexShrink: 0, ...style }}>
      <path d={ICON_PATHS[name] || ""} />
    </svg>
  );
}

// ── status dot ────────────────────────────────────────────────
function StatusDot({ status, size = 8, pulse }) {
  const s = (window.RPA_STATUS || {})[status] || { dot: "var(--muted-fg)" };
  const isRunning = status === "running" || pulse;
  return (
    <span style={{
      width: size, height: size, borderRadius: 99, background: s.dot,
      display: "inline-block", flexShrink: 0,
      boxShadow: isRunning ? `0 0 0 3px color-mix(in oklab, ${s.dot} 22%, transparent)` : "none",
      animation: isRunning ? "rpaPulse 1.6s ease-in-out infinite" : "none",
    }} />
  );
}

// ── generic pill ──────────────────────────────────────────────
function Pill({ children, color = "var(--muted-fg)", solid, mono, style }) {
  return (
    <span style={{
      display: "inline-flex", alignItems: "center", gap: 5,
      fontSize: 11, fontWeight: 600, lineHeight: 1,
      letterSpacing: mono ? 0.3 : 0.1,
      fontFamily: mono ? "var(--mono)" : "inherit",
      padding: "4px 8px", borderRadius: 6,
      color: solid ? "#0b0b12" : color,
      background: solid ? color : `color-mix(in oklab, ${color} 14%, transparent)`,
      border: `1px solid color-mix(in oklab, ${color} ${solid ? 0 : 32}%, transparent)`,
      ...style,
    }}>{children}</span>
  );
}

function PriorityBadge({ band, solid }) {
  const b = (window.RPA_BANDS || {})[band];
  if (!b) return null;
  return <Pill color={b.color} solid={solid}>{b.label}</Pill>;
}

function ComplexityChip({ cls, size = 30 }) {
  const c = (window.RPA_COMPLEXITY || {})[cls] || { color: "var(--muted-fg)" };
  return (
    <span style={{
      width: size, height: size, borderRadius: 8, flexShrink: 0,
      display: "inline-flex", alignItems: "center", justifyContent: "center",
      fontFamily: "var(--mono)", fontSize: size * 0.42, fontWeight: 700,
      color: c.color, background: `color-mix(in oklab, ${c.color} 16%, transparent)`,
      border: `1px solid color-mix(in oklab, ${c.color} 38%, transparent)`,
    }}>{cls}</span>
  );
}

// ── input source badge ────────────────────────────────────────
const SOURCE_META = {
  ai_extracted: { label: "AI", color: "var(--primary)" },
  manual:       { label: "Manual", color: "var(--muted-fg)" },
  corrected:    { label: "Edited", color: "var(--c-amber)" },
  from_s1:      { label: "← S1", color: "var(--c-teal)" },
  from_s2:      { label: "← S2", color: "var(--c-teal)" },
  from_s3:      { label: "← S3", color: "var(--c-teal)" },
  imported:     { label: "Import", color: "var(--c-blue)" },
};
function SourceBadge({ source }) {
  const m = SOURCE_META[source] || { label: source, color: "var(--muted-fg)" };
  return (
    <span style={{
      fontSize: 9.5, fontWeight: 700, letterSpacing: 0.4, textTransform: "uppercase",
      fontFamily: "var(--mono)", padding: "2px 5px", borderRadius: 4,
      color: m.color, background: `color-mix(in oklab, ${m.color} 13%, transparent)`,
    }}>{m.label}</span>
  );
}

// ── staleness banner ──────────────────────────────────────────
function Staleness({ text = "Inputs changed — re-run to update", inline }) {
  return (
    <div style={{
      display: "inline-flex", alignItems: "center", gap: 8,
      fontSize: 12.5, fontWeight: 500, color: "var(--c-amber)",
      padding: inline ? "4px 10px" : "9px 13px", borderRadius: inline ? 99 : 9,
      background: "color-mix(in oklab, var(--c-amber) 12%, transparent)",
      border: "1px solid color-mix(in oklab, var(--c-amber) 30%, transparent)",
    }}>
      <Icon name="alert" size={14} /> {text}
    </div>
  );
}

// ── radial score gauge (0-100) ────────────────────────────────
function Gauge({ value, max = 100, size = 156, band, label = "Migration score", thick = 11 }) {
  const r = (size - thick) / 2;
  const C = 2 * Math.PI * r;
  const pct = Math.max(0, Math.min(1, value / max));
  const color = band ? (window.RPA_BANDS[band] || {}).color : "var(--primary)";
  const gap = C * 0.25; // 270° arc
  const arc = C * 0.75;
  return (
    <div style={{ position: "relative", width: size, height: size }}>
      <svg width={size} height={size} style={{ transform: "rotate(135deg)" }}>
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="var(--track)"
          strokeWidth={thick} strokeLinecap="round" strokeDasharray={`${arc} ${C - arc}`} />
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke={color}
          strokeWidth={thick} strokeLinecap="round"
          strokeDasharray={`${arc * pct} ${C - arc * pct}`}
          style={{ filter: `drop-shadow(0 0 6px color-mix(in oklab, ${color} 55%, transparent))`, transition: "stroke-dasharray .6s cubic-bezier(.4,1,.4,1)" }} />
      </svg>
      <div style={{ position: "absolute", inset: 0, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center" }}>
        <div style={{ fontFamily: "var(--mono)", fontSize: size * 0.31, fontWeight: 700, lineHeight: 1, color: "var(--fg)" }}>{value}</div>
        <div style={{ fontSize: 10.5, color: "var(--muted-fg)", marginTop: 4, letterSpacing: 0.3 }}>/ {max}</div>
        <div style={{ fontSize: 10, color: "var(--muted-fg)", marginTop: 7, textTransform: "uppercase", letterSpacing: 0.6 }}>{label}</div>
      </div>
    </div>
  );
}

// ── dimension contribution bar ────────────────────────────────
function DimBar({ label, value, max, color = "var(--primary)" }) {
  const pct = Math.max(0, Math.min(1, value / max));
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
        <span style={{ fontSize: 12.5, color: "var(--fg-2)" }}>{label}</span>
        <span style={{ fontFamily: "var(--mono)", fontSize: 12, color: "var(--muted-fg)" }}>
          <b style={{ color: "var(--fg)" }}>{value}</b> / {max}
        </span>
      </div>
      <div style={{ height: 7, borderRadius: 99, background: "var(--track)", overflow: "hidden" }}>
        <div style={{ width: `${pct * 100}%`, height: "100%", borderRadius: 99, background: color,
          boxShadow: `0 0 8px color-mix(in oklab, ${color} 50%, transparent)` }} />
      </div>
    </div>
  );
}

// ── small sparkline / segment row ─────────────────────────────
function MiniSpark({ values, color = "var(--primary)", w = 64, h = 20 }) {
  const max = Math.max(...values, 1);
  const step = w / values.length;
  return (
    <svg width={w} height={h} style={{ display: "block" }}>
      {values.map((v, i) => (
        <rect key={i} x={i * step + 1} y={h - (v / max) * h} width={step - 2}
          height={(v / max) * h} rx={1} fill={color} opacity={0.45 + 0.55 * (v / max)} />
      ))}
    </svg>
  );
}

// ── button ────────────────────────────────────────────────────
function Btn({ children, variant = "default", size = "md", icon, iconR, onClick, style, disabled, title }) {
  const sz = size === "sm" ? { h: 30, px: 11, fs: 12.5 } : size === "lg" ? { h: 42, px: 18, fs: 14 } : { h: 36, px: 14, fs: 13 };
  const variants = {
    default: { bg: "var(--primary)", fg: "#0a0a12", bd: "transparent", glow: 1 },
    ghost:   { bg: "transparent", fg: "var(--fg-2)", bd: "transparent" },
    outline: { bg: "transparent", fg: "var(--fg)", bd: "var(--border)" },
    subtle:  { bg: "var(--surface-2)", fg: "var(--fg)", bd: "var(--border)" },
  };
  const v = variants[variant] || variants.default;
  return (
    <button onClick={onClick} disabled={disabled} title={title} style={{
      display: "inline-flex", alignItems: "center", justifyContent: "center", gap: 7,
      height: sz.h, padding: `0 ${sz.px}px`, fontSize: sz.fs, fontWeight: 600,
      fontFamily: "inherit", borderRadius: 9, cursor: disabled ? "not-allowed" : "pointer",
      color: v.fg, background: v.bg, border: `1px solid ${v.bd}`,
      opacity: disabled ? 0.5 : 1, whiteSpace: "nowrap",
      boxShadow: v.glow ? "0 0 0 1px color-mix(in oklab, var(--primary) 40%, transparent), 0 6px 20px color-mix(in oklab, var(--primary) 28%, transparent)" : "none",
      transition: "filter .15s, background .15s", ...style,
    }}
      onMouseEnter={(e) => { if (!disabled) e.currentTarget.style.filter = "brightness(1.1)"; }}
      onMouseLeave={(e) => { e.currentTarget.style.filter = "none"; }}>
      {icon && <Icon name={icon} size={sz.fs + 2} />}
      {children}
      {iconR && <Icon name={iconR} size={sz.fs + 2} />}
    </button>
  );
}

function SectionLabel({ children, style }) {
  return <div style={{ fontSize: 10.5, fontWeight: 700, letterSpacing: 1.4, textTransform: "uppercase",
    color: "var(--muted-fg)", ...style }}>{children}</div>;
}

// generic surface card
function Card({ children, style, hover, pad = 18 }) {
  return <div className={hover ? "rpa-card-hover" : ""} style={{ borderRadius: 14, border: "1px solid var(--border)",
    background: "var(--surface)", padding: pad, ...style }}>{children}</div>;
}

// ── run pill (history row) ────────────────────────────────────
function RunPill({ n, active, model, time, onClick }) {
  return (
    <button onClick={onClick} style={{
      display: "flex", alignItems: "center", gap: 9, width: "100%", textAlign: "left",
      padding: "9px 11px", borderRadius: 9, cursor: "pointer", fontFamily: "inherit",
      background: active ? "color-mix(in oklab, var(--primary) 12%, transparent)" : "transparent",
      border: `1px solid ${active ? "color-mix(in oklab, var(--primary) 35%, transparent)" : "var(--border)"}`,
      color: "var(--fg)",
    }}>
      <span style={{ fontFamily: "var(--mono)", fontSize: 11.5, fontWeight: 700,
        color: active ? "var(--primary)" : "var(--muted-fg)", width: 28 }}>#{n}</span>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontSize: 12, fontWeight: 500 }}>{model}</div>
        <div style={{ fontSize: 10.5, color: "var(--muted-fg)" }}>{time}</div>
      </div>
      {active && <Pill color="var(--primary)" style={{ fontSize: 9.5, padding: "2px 6px" }}>VIEWING</Pill>}
    </button>
  );
}

// ── agent activity feed (rich) ────────────────────────────────
const AGENT_STYLE = {
  decision:    { label: "Decision",  color: "var(--c-violet)", mono: false, w: 700 },
  thinking:    { label: "Thinking",  color: "var(--muted-fg)", mono: false, italic: true },
  tool_call:   { label: "Tool",      color: "var(--primary)",  mono: true,  chip: true },
  tool_result: { label: "Result",    color: "var(--c-green)",  mono: true },
  correction:  { label: "Correct",   color: "var(--c-amber)",  mono: false },
  needs_input: { label: "Input",     color: "var(--c-amber)",  mono: false, box: true },
  error:       { label: "Error",     color: "var(--c-red)",    mono: false },
  complete:    { label: "Done",      color: "var(--c-green)",  mono: false, w: 700 },
};
function AgentFeed({ log, connected = true, title = "Agent activity", compact, height = 280 }) {
  return (
    <div style={{ borderRadius: 13, border: "1px solid var(--border)", background: "var(--surface)", overflow: "hidden" }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between",
        padding: "11px 14px", borderBottom: "1px solid var(--border)" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <span style={{ position: "relative", display: "flex" }}>
            <Icon name="bot" size={16} style={{ color: "var(--c-violet)" }} />
          </span>
          <span style={{ fontSize: 13, fontWeight: 600 }}>{title}</span>
          <Pill color="var(--muted-fg)" style={{ fontSize: 9.5, padding: "2px 6px" }}>{log.length} events</Pill>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 11, color: connected ? "var(--c-green)" : "var(--muted-fg)" }}>
          <StatusDot status={connected ? "complete" : "not_ready"} size={6} pulse={connected} /> {connected ? "Live" : "Idle"}
        </div>
      </div>
      <div style={{ padding: "10px 12px", display: "flex", flexDirection: "column", gap: compact ? 5 : 7, maxHeight: height, overflow: "hidden" }}>
        {log.map((e, i) => {
          const s = AGENT_STYLE[e.type] || AGENT_STYLE.thinking;
          if (s.box) return (
            <div key={i} style={{ borderRadius: 8, padding: "8px 10px",
              background: "color-mix(in oklab, var(--c-amber) 11%, transparent)",
              border: "1px solid color-mix(in oklab, var(--c-amber) 30%, transparent)" }}>
              <div style={{ fontSize: 10, fontWeight: 700, color: "var(--c-amber)", letterSpacing: 0.4, marginBottom: 3 }}>INPUT NEEDED</div>
              <div style={{ fontSize: 12, color: "var(--fg-2)" }}>{e.t}</div>
            </div>
          );
          return (
            <div key={i} style={{ display: "flex", alignItems: "flex-start", gap: 8 }}>
              {s.chip ? (
                <span style={{ fontSize: 9, fontWeight: 700, fontFamily: "var(--mono)", letterSpacing: 0.3,
                  color: s.color, background: `color-mix(in oklab, ${s.color} 15%, transparent)`,
                  border: `1px solid color-mix(in oklab, ${s.color} 32%, transparent)`,
                  padding: "2px 5px", borderRadius: 4, marginTop: 1, flexShrink: 0, width: 38, textAlign: "center" }}>{s.label}</span>
              ) : (
                <span style={{ fontSize: 9.5, color: "color-mix(in oklab, var(--muted-fg) 75%, transparent)",
                  width: 46, textAlign: "right", flexShrink: 0, marginTop: 2, letterSpacing: 0.2 }}>{s.label}</span>
              )}
              <span style={{ fontSize: 12, lineHeight: 1.45, color: s.color, fontWeight: s.w || 400,
                fontFamily: s.mono ? "var(--mono)" : "inherit", fontStyle: s.italic ? "italic" : "normal" }}>
                {e.type === "thinking" && "… "}{e.t}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ── App shell: sidebar + topbar + content ─────────────────────
const STAGE_NAV = [
  { id: "s1", label: "Assessment", n: "1" },
  { id: "s2", label: "Complexity", n: "2" },
  { id: "s3", label: "Timeline", n: "3" },
  { id: "s4", label: "Tracker", n: "4" },
];

function AppShell({ activeStage, useCase, breadcrumb, action, children, contentStyle }) {
  const ucs = window.RPA_USECASES || [];
  const uc = useCase || ucs[0];
  return (
    <div style={{ display: "flex", height: "100%", width: "100%", background: "var(--bg)", color: "var(--fg)",
      fontFamily: "var(--sans)", overflow: "hidden" }}>
      {/* sidebar */}
      <aside style={{ width: 232, flexShrink: 0, display: "flex", flexDirection: "column",
        background: "var(--sidebar)", borderRight: "1px solid var(--border)" }}>
        <div style={{ padding: "16px 16px", display: "flex", alignItems: "center", gap: 9 }}>
          <span style={{ width: 28, height: 28, borderRadius: 8, display: "flex", alignItems: "center", justifyContent: "center",
            background: "color-mix(in oklab, var(--primary) 18%, transparent)", color: "var(--primary)" }}>
            <Icon name="cpu" size={17} />
          </span>
          <span className="rpa-gradient-text" style={{ fontSize: 14, fontWeight: 700, letterSpacing: -0.2 }}>RPA Intelligence</span>
        </div>
        <div style={{ padding: "6px 12px", flex: 1, overflow: "hidden" }}>
          <div style={{ fontSize: 10, fontWeight: 700, letterSpacing: 1, color: "var(--muted-fg)", padding: "10px 8px 6px" }}>PROJECTS</div>
          {/* active project */}
          <div style={{ borderRadius: 8 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 7, padding: "7px 8px", fontSize: 12.5, fontWeight: 600, color: "var(--fg)" }}>
              <Icon name="chevD" size={14} style={{ color: "var(--muted-fg)" }} />
              RPA Migration Project
            </div>
            <div style={{ marginLeft: 8, paddingLeft: 8, borderLeft: "1px solid var(--border)", display: "flex", flexDirection: "column", gap: 1 }}>
              {STAGE_NAV.map((s) => {
                const active = s.id === activeStage;
                const st = uc.readiness[s.id];
                return (
                  <div key={s.id} style={{ display: "flex", alignItems: "center", gap: 8, padding: "6px 9px", borderRadius: 7,
                    fontSize: 12, color: active ? "var(--fg)" : "var(--fg-2)",
                    background: active ? "color-mix(in oklab, var(--primary) 13%, transparent)" : "transparent",
                    border: `1px solid ${active ? "color-mix(in oklab, var(--primary) 26%, transparent)" : "transparent"}`,
                    fontWeight: active ? 600 : 400 }}>
                    <StatusDot status={st} size={7} />
                    {s.label}
                  </div>
                );
              })}
            </div>
          </div>
          {/* other projects */}
          {["Finance Bots Wave 2", "Shared Services Q3"].map((p) => (
            <div key={p} style={{ display: "flex", alignItems: "center", gap: 7, padding: "7px 8px", fontSize: 12.5, color: "var(--fg-2)" }}>
              <Icon name="chevR" size={14} style={{ color: "var(--muted-fg)" }} /> {p}
            </div>
          ))}
        </div>
        <div style={{ padding: 12, borderTop: "1px solid var(--border)", display: "flex", flexDirection: "column", gap: 2 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 9, padding: "7px 8px", fontSize: 12.5, color: "var(--fg-2)" }}>
            <Icon name="settings" size={15} /> Settings
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 9, padding: "7px 8px", fontSize: 12.5, color: "var(--muted-fg)" }}>
            <Icon name="user" size={15} /> architect@acme.io
          </div>
        </div>
      </aside>

      {/* main */}
      <div style={{ flex: 1, display: "flex", flexDirection: "column", minWidth: 0 }}>
        <header style={{ height: 56, flexShrink: 0, display: "flex", alignItems: "center", justifyContent: "space-between",
          padding: "0 24px", borderBottom: "1px solid var(--border)", background: "var(--bg)" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10, fontSize: 13, minWidth: 0 }}>
            {(breadcrumb || ["RPA Migration Project", uc.name]).map((b, i, arr) => (
              <React.Fragment key={i}>
                <span style={{ color: i === arr.length - 1 ? "var(--fg)" : "var(--muted-fg)", fontWeight: i === arr.length - 1 ? 600 : 400,
                  whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{b}</span>
                {i < arr.length - 1 && <Icon name="chevR" size={13} style={{ color: "var(--muted-fg)", opacity: 0.6 }} />}
              </React.Fragment>
            ))}
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            {action}
          </div>
        </header>
        <div style={{ flex: 1, overflow: "hidden", ...contentStyle }}>{children}</div>
      </div>
    </div>
  );
}

Object.assign(window, {
  Icon, AppShell, StatusDot, Pill, SourceBadge, Staleness, Gauge, DimBar,
  ComplexityChip, PriorityBadge, AgentFeed, Btn, SectionLabel, RunPill, MiniSpark, Card,
});
