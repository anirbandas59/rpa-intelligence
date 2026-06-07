/* ─────────────────────────────────────────────────────────────
   stage3.jsx — Delivery Timeline, three directions
   Exports: S3Gantt, S3Stepper, S3Calendar
   Pure-Python-equivalent phase calculator in JS.
   ───────────────────────────────────────────────────────────── */

// phase plan for the invoice use case (effort 6w, class L, start Mon 2026-07-06)
// delta: Build +2 weeks (security requirements) — shown as an edit
const S3_PLAN = [
  { key: "define",  name: "Define",            weeks: 1, kind: "Fixed buffer",        color: "var(--c-blue)",   start: "Jul 6",  end: "Jul 10" },
  { key: "design",  name: "Design",            weeks: 2, kind: "Complexity-adjusted",  color: "var(--c-teal)",   start: "Jul 13", end: "Jul 24" },
  { key: "build",   name: "Build + Unit Test", weeks: 8, kind: "Variable · from S2",   color: "var(--primary)",  start: "Jul 27", end: "Sep 18", delta: 2 },
  { key: "sit",     name: "SIT / Integration", weeks: 1, kind: "Fixed buffer",        color: "var(--c-violet)", start: "Sep 21", end: "Sep 25" },
  { key: "uat",     name: "UAT",               kind: "Complexity-adjusted",  weeks: 2, color: "var(--c-amber)",  start: "Sep 28", end: "Oct 9"  },
  { key: "deploy",  name: "Deployment",        weeks: 1, kind: "Fixed buffer",        color: "var(--c-green)",  start: "Oct 12", end: "Oct 16" },
];
const S3_TOTAL = S3_PLAN.reduce((t, p) => t + p.weeks, 0); // 15 (with +2 delta)
const S3_SPRINT_WINDOW = ["build", "sit"]; // the only sprinted phases

function s3WeekOffset(idx) { return S3_PLAN.slice(0, idx).reduce((t, p) => t + p.weeks, 0); }

// ══════════════════════════════════════════════════════════════
// A · Gantt hero + phase cards
// ══════════════════════════════════════════════════════════════
function S3Gantt() {
  const uc = window.RPA_USECASES[0];
  const colW = 100 / S3_TOTAL;
  const weekTicks = Array.from({ length: S3_TOTAL + 1 });
  return (
    <AppShell activeStage="s3" useCase={uc}
      action={<><Btn variant="subtle" size="sm" icon="refresh">Reset to calculated</Btn><Btn variant="subtle" size="sm" icon="spark">Narrative</Btn><Btn size="sm" icon="download">Export Gantt</Btn></>}>
      <div style={{ height: "100%", overflow: "hidden", padding: "24px 28px", display: "flex", flexDirection: "column", gap: 18 }}>
        {/* summary strip */}
        <div style={{ display: "flex", gap: 14 }}>
          {[["Start", "Jul 6, 2026", "calendar"], ["Build effort", "6 + 2 wks", "clock"], ["Total duration", "15 weeks", "target"], ["Go-live", "Oct 16, 2026", "check"]].map(([l, v, ic], i) => (
            <Card key={l} pad={15} style={{ flex: 1, display: "flex", alignItems: "center", gap: 12 }}>
              <span style={{ width: 34, height: 34, borderRadius: 9, display: "flex", alignItems: "center", justifyContent: "center",
                background: "var(--surface-2)", color: i === 3 ? "var(--c-green)" : "var(--primary)" }}><Icon name={ic} size={17} /></span>
              <div>
                <div style={{ fontSize: 10.5, color: "var(--muted-fg)" }}>{l}</div>
                <div style={{ fontSize: 15, fontWeight: 700, fontFamily: i === 1 || i === 2 ? "var(--mono)" : "inherit" }}>{v}</div>
              </div>
            </Card>
          ))}
        </div>

        {/* GANTT */}
        <Card style={{ flex: 1, minHeight: 0, display: "flex", flexDirection: "column" }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 16 }}>
            <SectionLabel>Delivery Gantt · drag a phase edge to adjust</SectionLabel>
            <div style={{ display: "flex", gap: 14, fontSize: 11, color: "var(--muted-fg)" }}>
              <span style={{ display: "flex", alignItems: "center", gap: 5 }}><span style={{ width: 18, height: 8, borderRadius: 2, background: "var(--primary)" }} /> Sprint window</span>
              <span style={{ display: "flex", alignItems: "center", gap: 5 }}><Icon name="edit" size={11} style={{ color: "var(--c-amber)" }} /> Manual delta</span>
            </div>
          </div>

          {/* week axis */}
          <div style={{ display: "flex", paddingLeft: 168, marginBottom: 6 }}>
            {Array.from({ length: S3_TOTAL }).map((_, i) => (
              <div key={i} style={{ width: `${colW}%`, fontSize: 9.5, color: "var(--muted-fg)", textAlign: "center", fontFamily: "var(--mono)" }}>W{i + 1}</div>
            ))}
          </div>

          {/* rows */}
          <div style={{ position: "relative", flex: 1 }}>
            {/* gridlines */}
            <div style={{ position: "absolute", left: 168, right: 0, top: 0, bottom: 0, display: "flex", pointerEvents: "none" }}>
              {weekTicks.map((_, i) => <div key={i} style={{ width: `${colW}%`, borderLeft: "1px solid color-mix(in oklab, var(--border) 55%, transparent)" }} />)}
            </div>
            {/* sprint window tint */}
            <div style={{ position: "absolute", top: 0, bottom: 22, pointerEvents: "none",
              left: `calc(168px + ${s3WeekOffset(2) * colW}%)`,
              width: `${(S3_PLAN[2].weeks + S3_PLAN[3].weeks) * colW}%`,
              background: "color-mix(in oklab, var(--primary) 7%, transparent)", borderRadius: 6,
              border: "1px dashed color-mix(in oklab, var(--primary) 30%, transparent)" }} />

            <div style={{ display: "flex", flexDirection: "column", gap: 9, position: "relative" }}>
              {S3_PLAN.map((p, idx) => (
                <div key={p.key} style={{ display: "flex", alignItems: "center", height: 40 }}>
                  <div style={{ width: 168, paddingRight: 14, flexShrink: 0 }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 7, fontSize: 12.5, fontWeight: 600 }}>
                      <span style={{ width: 8, height: 8, borderRadius: 2, background: p.color }} />{p.name}
                    </div>
                    <div style={{ fontSize: 10, color: "var(--muted-fg)", marginLeft: 15 }}>{p.kind}</div>
                  </div>
                  <div style={{ flex: 1, position: "relative", height: 26 }}>
                    <div style={{ position: "absolute", left: `${s3WeekOffset(idx) * colW}%`, width: `${p.weeks * colW}%`, height: "100%",
                      borderRadius: 7, background: `linear-gradient(90deg, ${p.color}, color-mix(in oklab, ${p.color} 78%, black))`,
                      boxShadow: `0 2px 10px color-mix(in oklab, ${p.color} 35%, transparent)`,
                      display: "flex", alignItems: "center", justifyContent: "space-between", padding: "0 8px",
                      border: p.delta ? "1.5px dashed color-mix(in oklab, var(--c-amber) 80%, white)" : "none" }}>
                      <span style={{ width: 4, height: "60%", borderRadius: 2, background: "rgba(255,255,255,.5)", cursor: "ew-resize" }} />
                      <span style={{ fontSize: 10.5, fontWeight: 700, color: "#0b0b12", fontFamily: "var(--mono)" }}>{p.weeks}w</span>
                      <span style={{ width: 4, height: "60%", borderRadius: 2, background: "rgba(255,255,255,.5)", cursor: "ew-resize" }} />
                    </div>
                    {p.delta && (
                      <div style={{ position: "absolute", left: `calc(${(s3WeekOffset(idx) + p.weeks) * colW}% - 4px)`, top: -16,
                        fontSize: 9.5, color: "var(--c-amber)", fontWeight: 700, fontFamily: "var(--mono)", whiteSpace: "nowrap", transform: "translateX(-100%)" }}>+{p.delta}w delta</div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </Card>

        {/* phase cards */}
        <div style={{ display: "grid", gridTemplateColumns: "repeat(6, 1fr)", gap: 12 }}>
          {S3_PLAN.map((p) => (
            <Card key={p.key} pad={13} hover style={{ borderTop: `2px solid ${p.color}` }}>
              <div style={{ fontSize: 12, fontWeight: 600, marginBottom: 8 }}>{p.name}</div>
              <div style={{ fontFamily: "var(--mono)", fontSize: 20, fontWeight: 700, color: p.color }}>{p.weeks}<span style={{ fontSize: 11, color: "var(--muted-fg)" }}>wk</span></div>
              <div style={{ fontSize: 10.5, color: "var(--muted-fg)", marginTop: 8 }}>{p.start} – {p.end}</div>
              {p.delta && <div style={{ marginTop: 6 }}><Pill color="var(--c-amber)" style={{ fontSize: 9 }}>edited +{p.delta}w</Pill></div>}
            </Card>
          ))}
        </div>
      </div>
    </AppShell>
  );
}

// ══════════════════════════════════════════════════════════════
// B · Phase stepper
// ══════════════════════════════════════════════════════════════
function S3Stepper() {
  const uc = window.RPA_USECASES[0];
  return (
    <AppShell activeStage="s3" useCase={uc}
      action={<><Btn variant="subtle" size="sm" icon="sliders">Phase buffers</Btn><Btn size="sm" icon="download">Export</Btn></>}>
      <div style={{ height: "100%", overflow: "hidden", padding: "24px 28px", display: "grid", gridTemplateColumns: "1.3fr 1fr", gap: 24 }}>
        {/* vertical stepper */}
        <div style={{ display: "flex", flexDirection: "column", minHeight: 0 }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 18 }}>
            <h2 style={{ fontSize: 19, fontWeight: 700, margin: 0 }}>Delivery phases</h2>
            <span style={{ fontSize: 12, color: "var(--muted-fg)" }}>15 weeks · Jul 6 → Oct 16</span>
          </div>
          <div style={{ position: "relative", paddingLeft: 4 }}>
            {/* connector line */}
            <div style={{ position: "absolute", left: 13, top: 14, bottom: 14, width: 2, background: "var(--border)" }} />
            <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
              {S3_PLAN.map((p, idx) => (
                <div key={p.key} style={{ display: "flex", gap: 16, alignItems: "stretch" }}>
                  <div style={{ position: "relative", zIndex: 1, flexShrink: 0 }}>
                    <span style={{ width: 28, height: 28, borderRadius: 99, display: "flex", alignItems: "center", justifyContent: "center",
                      background: p.color, color: "#0b0b12", fontSize: 12, fontWeight: 700, fontFamily: "var(--mono)",
                      boxShadow: `0 0 0 4px var(--bg), 0 0 12px color-mix(in oklab, ${p.color} 45%, transparent)` }}>{idx + 1}</span>
                  </div>
                  <Card pad={14} hover style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "space-between",
                    borderLeft: `3px solid ${p.color}` }}>
                    <div>
                      <div style={{ display: "flex", alignItems: "center", gap: 9 }}>
                        <span style={{ fontSize: 13.5, fontWeight: 600 }}>{p.name}</span>
                        {S3_SPRINT_WINDOW.includes(p.key) && <Pill color="var(--primary)" style={{ fontSize: 9 }}>SPRINTED</Pill>}
                        {p.delta && <Pill color="var(--c-amber)" style={{ fontSize: 9 }}>+{p.delta}w</Pill>}
                      </div>
                      <div style={{ fontSize: 11, color: "var(--muted-fg)", marginTop: 3 }}>{p.kind} · {p.start} – {p.end}</div>
                    </div>
                    <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
                      {/* mini week bar */}
                      <div style={{ display: "flex", gap: 2 }}>
                        {Array.from({ length: p.weeks }).map((_, i) => <span key={i} style={{ width: 7, height: 18, borderRadius: 2, background: p.color, opacity: 0.55 + i * 0.05 }} />)}
                      </div>
                      <span style={{ fontFamily: "var(--mono)", fontSize: 17, fontWeight: 700, color: p.color, width: 40, textAlign: "right" }}>{p.weeks}w</span>
                    </div>
                  </Card>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* right: buffers config + delta log */}
        <div style={{ display: "flex", flexDirection: "column", gap: 16, minHeight: 0 }}>
          <Card>
            <SectionLabel style={{ marginBottom: 14 }}>Phase buffers (project)</SectionLabel>
            {[["Define", "Fixed", "1 wk"], ["Design", "S/M 1w · L/XL 2w", "2 wks"], ["SIT", "Fixed", "1 wk"], ["UAT", "S/M 1w · L/XL 2w", "2 wks"], ["Deploy", "Fixed", "1 wk"]].map(([n, r, v], i) => (
              <div key={n} style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "9px 0", borderBottom: i < 4 ? "1px solid var(--border)" : "none" }}>
                <div><div style={{ fontSize: 12.5, fontWeight: 500 }}>{n}</div><div style={{ fontSize: 10.5, color: "var(--muted-fg)" }}>{r}</div></div>
                <span style={{ fontFamily: "var(--mono)", fontSize: 13, fontWeight: 700, color: "var(--primary)" }}>{v}</span>
              </div>
            ))}
            <div style={{ fontSize: 10.5, color: "var(--muted-fg)", marginTop: 12, display: "flex", gap: 6, alignItems: "center" }}>
              <span style={{ width: 5, height: 5, borderRadius: 99, background: "var(--c-green)" }} /> Changing buffers recalculates instantly — no re-run
            </div>
          </Card>
          <Card style={{ flex: 1, minHeight: 0 }}>
            <SectionLabel style={{ marginBottom: 12 }}>Manual edits (deltas)</SectionLabel>
            <div style={{ display: "flex", gap: 10, alignItems: "flex-start", padding: "11px 12px", borderRadius: 10,
              background: "color-mix(in oklab, var(--c-amber) 9%, transparent)", border: "1px solid color-mix(in oklab, var(--c-amber) 24%, transparent)" }}>
              <Icon name="edit" size={14} style={{ color: "var(--c-amber)", marginTop: 1 }} />
              <div style={{ flex: 1 }}>
                <div style={{ fontSize: 12.5, fontWeight: 600 }}>Build + Unit Test · +2 weeks</div>
                <div style={{ fontSize: 11.5, color: "var(--muted-fg)", marginTop: 2 }}>“Additional security requirements discovered.”</div>
                <div style={{ fontSize: 10.5, color: "var(--muted-fg)", marginTop: 4 }}>by architect@acme.io · stored as delta, not a new run</div>
              </div>
            </div>
            <Btn variant="outline" size="sm" icon="refresh" style={{ width: "100%", marginTop: 12 }}>Reset to calculated plan</Btn>
          </Card>
        </div>
      </div>
    </AppShell>
  );
}

// ══════════════════════════════════════════════════════════════
// C · Calendar + narrative
// ══════════════════════════════════════════════════════════════
function S3Calendar() {
  const uc = window.RPA_USECASES[0];
  // months Jul–Oct 2026, week-of indexing. We lay phases as bands over a week grid.
  const MONTHS = [
    { name: "July", weeks: 4, startW: 0 },
    { name: "August", weeks: 4, startW: 4 },
    { name: "September", weeks: 4, startW: 8 },
    { name: "October", weeks: 3, startW: 12 },
  ];
  const colW = 100 / S3_TOTAL;
  return (
    <AppShell activeStage="s3" useCase={uc}
      action={<><Pill color="var(--c-violet)" style={{ height: 30 }}><Icon name="spark" size={12} /> Narrative ready</Pill><Btn size="sm" icon="download">Client export</Btn></>}>
      <div style={{ height: "100%", overflow: "hidden", padding: "24px 28px", display: "grid", gridTemplateColumns: "1.5fr 1fr", gap: 22 }}>
        {/* calendar */}
        <div style={{ display: "flex", flexDirection: "column", gap: 14, minHeight: 0 }}>
          <h2 style={{ fontSize: 19, fontWeight: 700, margin: 0 }}>Calendar view</h2>
          <Card style={{ flex: 1, minHeight: 0, display: "flex", flexDirection: "column" }}>
            {/* month headers */}
            <div style={{ display: "flex", marginBottom: 4 }}>
              {MONTHS.map((m) => (
                <div key={m.name} style={{ width: `${m.weeks * colW}%`, padding: "0 4px" }}>
                  <div style={{ fontSize: 12, fontWeight: 700, color: "var(--fg)", paddingBottom: 6, borderBottom: "1px solid var(--border)" }}>{m.name} <span style={{ color: "var(--muted-fg)", fontWeight: 400 }}>2026</span></div>
                </div>
              ))}
            </div>
            {/* week cells row */}
            <div style={{ display: "flex", marginBottom: 14 }}>
              {Array.from({ length: S3_TOTAL }).map((_, i) => (
                <div key={i} style={{ width: `${colW}%`, padding: "0 2px" }}>
                  <div style={{ height: 30, borderRadius: 5, background: "var(--surface-2)", border: "1px solid var(--border)",
                    display: "flex", alignItems: "center", justifyContent: "center", fontSize: 9.5, color: "var(--muted-fg)", fontFamily: "var(--mono)" }}>{i + 1}</div>
                </div>
              ))}
            </div>
            {/* phase bands */}
            <div style={{ display: "flex", flexDirection: "column", gap: 7, position: "relative" }}>
              {S3_PLAN.map((p, idx) => (
                <div key={p.key} style={{ position: "relative", height: 30 }}>
                  <div style={{ position: "absolute", left: `${s3WeekOffset(idx) * colW}%`, width: `${p.weeks * colW}%`, height: "100%",
                    borderRadius: 6, background: `color-mix(in oklab, ${p.color} 26%, transparent)`, border: `1px solid ${p.color}`,
                    display: "flex", alignItems: "center", padding: "0 9px", gap: 7, overflow: "hidden" }}>
                    <span style={{ width: 6, height: 6, borderRadius: 99, background: p.color, flexShrink: 0 }} />
                    <span style={{ fontSize: 11, fontWeight: 600, color: "var(--fg)", whiteSpace: "nowrap" }}>{p.name}</span>
                  </div>
                </div>
              ))}
            </div>
            <div style={{ marginTop: "auto", paddingTop: 14, display: "flex", justifyContent: "space-between", fontSize: 11.5, color: "var(--muted-fg)" }}>
              <span>Kickoff <b style={{ color: "var(--fg)" }}>Jul 6</b></span>
              <span>Go-live <b style={{ color: "var(--c-green)" }}>Oct 16</b></span>
            </div>
          </Card>
        </div>

        {/* narrative */}
        <div style={{ display: "flex", flexDirection: "column", gap: 14, minHeight: 0 }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
            <SectionLabel>Timeline narrative</SectionLabel>
            <span style={{ fontSize: 11, color: "var(--muted-fg)", fontFamily: "var(--mono)" }}>Sonnet · background</span>
          </div>
          <Card style={{ flex: 1, minHeight: 0, display: "flex", flexDirection: "column", gap: 12,
            background: "linear-gradient(160deg, color-mix(in oklab, var(--c-violet) 8%, var(--surface)), var(--surface) 70%)" }}>
            <div style={{ display: "flex", alignItems: "center", gap: 9 }}>
              <span style={{ width: 30, height: 30, borderRadius: 8, display: "flex", alignItems: "center", justifyContent: "center",
                background: "color-mix(in oklab, var(--c-violet) 18%, transparent)", color: "var(--c-violet)" }}><Icon name="spark" size={16} /></span>
              <span style={{ fontSize: 13, fontWeight: 600 }}>Client-ready summary</span>
            </div>
            <p style={{ fontSize: 12.8, lineHeight: 1.65, color: "var(--fg-2)", margin: 0 }}>
              The Invoice Processing automation will be delivered over <b style={{ color: "var(--fg)" }}>15 weeks</b>, beginning Jul 6 and going live Oct 16, 2026. After a one-week Define phase, a two-week Design phase reflects the solution's <b style={{ color: "var(--fg)" }}>L-class complexity</b>.
            </p>
            <p style={{ fontSize: 12.8, lineHeight: 1.65, color: "var(--fg-2)", margin: 0 }}>
              The core <b style={{ color: "var(--fg)" }}>Build + Unit Testing</b> phase spans eight weeks — six from the complexity estimate plus a two-week adjustment for newly discovered security requirements. Integration testing and a two-week UAT precede a one-week deployment window.
            </p>
            <div style={{ marginTop: "auto", display: "flex", gap: 9 }}>
              <Btn variant="outline" size="sm" icon="refresh" style={{ flex: 1 }}>Regenerate</Btn>
              <Btn variant="subtle" size="sm" icon="download" style={{ flex: 1 }}>Copy to export</Btn>
            </div>
          </Card>
        </div>
      </div>
    </AppShell>
  );
}

Object.assign(window, { S3Gantt, S3Stepper, S3Calendar });
