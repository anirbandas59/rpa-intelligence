/* ─────────────────────────────────────────────────────────────
   stage4.jsx — Sprint Tracker, three directions
   Exports: S4Swimlanes, S4Decompose, S4Export
   ───────────────────────────────────────────────────────────── */

const S4_PTS = { XS: 1, S: 2, M: 3, L: 5, XL: 8 };
const S4_CAP = 8; // story points per 2-week sprint
const S4_SIZE_COLOR = { XS: "var(--c-green)", S: "var(--c-blue)", M: "var(--c-yellow)", L: "var(--c-amber)", XL: "var(--c-red)" };

function s4BySprint() {
  const map = {};
  window.RPA_FEATURES.forEach((f) => { (map[f.sprint] = map[f.sprint] || []).push(f); });
  return map;
}

function FeatureCard({ f, compact }) {
  const c = S4_SIZE_COLOR[f.size];
  return (
    <div className="rpa-card-hover" style={{ borderRadius: 10, border: "1px solid var(--border)", background: "var(--surface-2)",
      padding: compact ? "9px 11px" : "11px 13px", borderLeft: `3px solid ${c}` }}>
      <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 8 }}>
        <span style={{ fontSize: 12.5, fontWeight: 600, lineHeight: 1.3 }}>{f.name}</span>
        <span style={{ flexShrink: 0, fontFamily: "var(--mono)", fontSize: 10, fontWeight: 700, color: c,
          background: `color-mix(in oklab, ${c} 15%, transparent)`, border: `1px solid color-mix(in oklab, ${c} 32%, transparent)`,
          borderRadius: 5, padding: "2px 6px" }}>{f.size}</span>
      </div>
      {!compact && <div style={{ fontSize: 11, color: "var(--muted-fg)", marginTop: 5, lineHeight: 1.4 }}>{f.desc}</div>}
      {f.deps.length > 0 && (
        <div style={{ display: "flex", alignItems: "center", gap: 5, marginTop: 7, fontSize: 10, color: "var(--muted-fg)" }}>
          <Icon name="link" size={10} /> depends on {f.deps[0].split(" ").slice(0, 2).join(" ")}…
        </div>
      )}
    </div>
  );
}

// ══════════════════════════════════════════════════════════════
// A · Sprint swimlanes
// ══════════════════════════════════════════════════════════════
function S4Swimlanes() {
  const uc = window.RPA_USECASES[0];
  const sprints = s4BySprint();
  const sprintNums = Object.keys(sprints).map(Number).sort();
  return (
    <AppShell activeStage="s4" useCase={uc}
      action={<><Btn variant="subtle" size="sm" icon="plus">Add feature</Btn><Btn variant="subtle" size="sm" icon="refresh">Re-balance</Btn><Btn size="sm" icon="download">Export tracker</Btn></>}>
      <div style={{ height: "100%", overflow: "hidden", padding: "24px 28px", display: "flex", flexDirection: "column", gap: 16 }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <div>
            <h2 style={{ fontSize: 19, fontWeight: 700, margin: 0 }}>Sprint plan</h2>
            <p style={{ fontSize: 12.5, color: "var(--muted-fg)", margin: "4px 0 0" }}>{window.RPA_FEATURES.length} features · 4 sprints × 2 weeks · bin-packed by size after Sonnet decomposition</p>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <span style={{ fontSize: 12, color: "var(--muted-fg)" }}>Sprint length</span>
            <Pill color="var(--primary)" style={{ height: 28 }}>2 weeks</Pill>
            <span style={{ fontSize: 11, color: "var(--muted-fg)" }}>from S3 window ÷ length</span>
          </div>
        </div>

        <div style={{ flex: 1, minHeight: 0, display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 14 }}>
          {sprintNums.map((n) => {
            const feats = sprints[n];
            const pts = feats.reduce((t, f) => t + S4_PTS[f.size], 0);
            const fill = Math.min(1, pts / S4_CAP);
            const over = pts > S4_CAP;
            return (
              <div key={n} style={{ display: "flex", flexDirection: "column", gap: 11, minHeight: 0 }}>
                <Card pad={13} style={{ flexShrink: 0 }}>
                  <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 9 }}>
                    <span style={{ fontSize: 13, fontWeight: 700 }}>Sprint {n}</span>
                    <span style={{ fontFamily: "var(--mono)", fontSize: 11, color: over ? "var(--c-red)" : "var(--muted-fg)" }}>{pts}/{S4_CAP} pts</span>
                  </div>
                  <div style={{ height: 6, borderRadius: 99, background: "var(--track)", overflow: "hidden" }}>
                    <div style={{ width: `${fill * 100}%`, height: "100%", borderRadius: 99,
                      background: over ? "var(--c-red)" : fill > 0.85 ? "var(--c-amber)" : "var(--primary)" }} />
                  </div>
                  <div style={{ fontSize: 10, color: "var(--muted-fg)", marginTop: 7 }}>{feats.length} features</div>
                </Card>
                <div style={{ flex: 1, display: "flex", flexDirection: "column", gap: 9, padding: 4, borderRadius: 12,
                  background: "color-mix(in oklab, var(--surface) 50%, transparent)", border: "1px dashed var(--border)" }}>
                  {feats.map((f) => <FeatureCard key={f.name} f={f} />)}
                  {feats.length < 2 && (
                    <div style={{ flex: 1, minHeight: 40, borderRadius: 9, border: "1px dashed var(--border)",
                      display: "flex", alignItems: "center", justifyContent: "center", fontSize: 11, color: "var(--muted-fg)" }}>
                      <Icon name="plus" size={13} style={{ marginRight: 5 }} /> capacity free
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>

        {/* size legend + rerun note */}
        <Card style={{ display: "flex", alignItems: "center", gap: 16 }}>
          <SectionLabel>Feature size</SectionLabel>
          <div style={{ display: "flex", gap: 13 }}>
            {Object.entries(S4_PTS).map(([s, p]) => (
              <span key={s} style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 11.5, color: "var(--fg-2)" }}>
                <span style={{ width: 9, height: 9, borderRadius: 2, background: S4_SIZE_COLOR[s] }} />{s} = {p}pt
              </span>
            ))}
          </div>
          <span style={{ flex: 1 }} />
          <span style={{ fontSize: 11, color: "var(--muted-fg)", display: "flex", alignItems: "center", gap: 6 }}>
            <Icon name="refresh" size={12} /> Change sprint length → re-run redistributes features · each run versioned
          </span>
        </Card>
      </div>
    </AppShell>
  );
}

// ══════════════════════════════════════════════════════════════
// B · Decomposition + AI
// ══════════════════════════════════════════════════════════════
function S4Decompose() {
  const uc = window.RPA_USECASES[0];
  return (
    <AppShell activeStage="s4" useCase={uc}
      action={<><Pill color="var(--c-violet)" style={{ height: 30 }}><Icon name="spark" size={12} /> Sonnet 4.5</Pill><Btn size="sm" icon="refresh">Re-run decomposition</Btn></>}>
      <div style={{ height: "100%", overflow: "hidden", padding: "24px 28px", display: "grid", gridTemplateColumns: "1.45fr 1fr", gap: 22 }}>
        {/* feature list */}
        <div style={{ display: "flex", flexDirection: "column", gap: 14, minHeight: 0 }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
            <div>
              <h2 style={{ fontSize: 18, fontWeight: 700, margin: 0 }}>Decomposed features</h2>
              <p style={{ fontSize: 12, color: "var(--muted-fg)", margin: "3px 0 0" }}>Sonnet read the S2 documents and split the process into deliverables.</p>
            </div>
            <Btn variant="subtle" size="sm" icon="plus">Add manually</Btn>
          </div>
          <Card pad={0} style={{ flex: 1, minHeight: 0, overflow: "hidden", display: "flex", flexDirection: "column" }}>
            <div style={{ display: "grid", gridTemplateColumns: "2.2fr 0.6fr 0.7fr 0.8fr", padding: "10px 16px", borderBottom: "1px solid var(--border)",
              fontSize: 10, fontWeight: 700, letterSpacing: 0.5, color: "var(--muted-fg)", textTransform: "uppercase" }}>
              <span>Feature</span><span style={{ textAlign: "center" }}>Size</span><span style={{ textAlign: "center" }}>Deps</span><span style={{ textAlign: "right" }}>Sprint</span>
            </div>
            {window.RPA_FEATURES.map((f, idx) => (
              <div key={f.name} className="rpa-card-hover" style={{ display: "grid", gridTemplateColumns: "2.2fr 0.6fr 0.7fr 0.8fr", padding: "12px 16px",
                alignItems: "center", borderBottom: idx < window.RPA_FEATURES.length - 1 ? "1px solid var(--border)" : "none" }}>
                <div style={{ minWidth: 0, paddingRight: 8 }}>
                  <div style={{ fontSize: 12.5, fontWeight: 600 }}>{f.name}</div>
                  <div style={{ fontSize: 10.5, color: "var(--muted-fg)", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{f.desc}</div>
                </div>
                <span style={{ textAlign: "center", display: "flex", justifyContent: "center" }}>
                  <span style={{ fontFamily: "var(--mono)", fontSize: 11, fontWeight: 700, color: S4_SIZE_COLOR[f.size],
                    background: `color-mix(in oklab, ${S4_SIZE_COLOR[f.size]} 14%, transparent)`, borderRadius: 5, padding: "2px 7px" }}>{f.size}</span>
                </span>
                <span style={{ textAlign: "center", fontSize: 11.5, color: "var(--muted-fg)" }}>{f.deps.length || "—"}</span>
                <span style={{ textAlign: "right", fontFamily: "var(--mono)", fontSize: 12, fontWeight: 700, color: "var(--primary)" }}>S{f.sprint}</span>
              </div>
            ))}
          </Card>
        </div>

        {/* right: controls + agent */}
        <div style={{ display: "flex", flexDirection: "column", gap: 16, minHeight: 0 }}>
          <Card>
            <SectionLabel style={{ marginBottom: 14 }}>Run configuration</SectionLabel>
            <div style={{ display: "flex", flexDirection: "column", gap: 13 }}>
              {[["Sprint length", "2 weeks", "from S3"], ["Sprint count", "4 sprints", "from_s3"], ["Process source", "S2 documents", "from_s2"], ["Capacity / sprint", "8 points", "manual"]].map(([l, v, src]) => (
                <div key={l} style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                  <span style={{ fontSize: 12.5, color: "var(--fg-2)" }}>{l}</span>
                  <span style={{ display: "flex", alignItems: "center", gap: 7 }}>
                    <span style={{ fontSize: 12.5, fontWeight: 600, fontFamily: "var(--mono)" }}>{v}</span>
                    <SourceBadge source={src.startsWith("from") ? src : src} />
                  </span>
                </div>
              ))}
            </div>
            <div style={{ marginTop: 14, paddingTop: 13, borderTop: "1px solid var(--border)", display: "flex", gap: 9 }}>
              <Btn variant="outline" size="sm" icon="link" style={{ flex: 1 }}>Reload from S3</Btn>
              <Btn size="sm" icon="refresh" style={{ flex: 1 }}>Re-run</Btn>
            </div>
          </Card>
          <div style={{ flex: 1, minHeight: 0 }}>
            <AgentFeed log={window.RPA_AGENT_LOG.slice(0, 9)} title="Decomposition trace" height={240} compact />
          </div>
        </div>
      </div>
    </AppShell>
  );
}

// ══════════════════════════════════════════════════════════════
// C · Tracker export preview (xlsx 3 sheets)
// ══════════════════════════════════════════════════════════════
function S4Export() {
  const uc = window.RPA_USECASES[0];
  const { useState } = React;
  const [tab, setTab] = useState("features");
  const sprints = s4BySprint();
  const TABS = [["features", "Features"], ["sprints", "Sprint Plan"], ["summary", "Summary"]];
  return (
    <AppShell activeStage="s4" useCase={uc} breadcrumb={["RPA Migration Project", "Stage 4 · Export"]}
      action={<><Btn variant="subtle" size="sm" icon="history">Run #3</Btn><Btn size="sm" icon="download">Download .xlsx</Btn></>}>
      <div style={{ height: "100%", overflow: "hidden", padding: "24px 28px", display: "flex", flexDirection: "column", gap: 16 }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <div>
            <h2 style={{ fontSize: 19, fontWeight: 700, margin: 0 }}>Tracker export preview</h2>
            <p style={{ fontSize: 12.5, color: "var(--muted-fg)", margin: "4px 0 0" }}>Pre-filled 3-sheet workbook · extends the Project 2 template · maintained offline after download</p>
          </div>
          <span style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 12, color: "var(--c-green)" }}>
            <Icon name="check" size={14} /> Ready · 7 features across 4 sprints
          </span>
        </div>

        {/* spreadsheet frame */}
        <Card pad={0} style={{ flex: 1, minHeight: 0, overflow: "hidden", display: "flex", flexDirection: "column" }}>
          {/* file bar */}
          <div style={{ display: "flex", alignItems: "center", gap: 9, padding: "10px 14px", borderBottom: "1px solid var(--border)", background: "var(--surface-2)" }}>
            <Icon name="download" size={14} style={{ color: "var(--c-green)" }} />
            <span style={{ fontSize: 12.5, fontWeight: 600, fontFamily: "var(--mono)" }}>invoice_processing_tracker.xlsx</span>
            <span style={{ flex: 1 }} />
            <span style={{ fontSize: 11, color: "var(--muted-fg)" }}>generated {new Date().toLocaleDateString("en-US", { month: "short", day: "numeric" })}</span>
          </div>
          {/* content */}
          <div style={{ flex: 1, minHeight: 0, overflow: "hidden", padding: "2px 0" }}>
            {tab === "features" && (
              <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
                <thead>
                  <tr style={{ background: "var(--surface-2)" }}>
                    {["#", "Feature", "Description", "Size", "Pts", "Dependencies", "Sprint"].map((h, i) => (
                      <th key={h} style={{ textAlign: i >= 3 && i <= 4 ? "center" : "left", padding: "9px 14px", fontSize: 10.5, fontWeight: 700,
                        color: "var(--muted-fg)", textTransform: "uppercase", letterSpacing: 0.4, borderBottom: "1px solid var(--border)" }}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {window.RPA_FEATURES.map((f, i) => (
                    <tr key={f.name} style={{ borderBottom: "1px solid var(--border)" }}>
                      <td style={{ padding: "10px 14px", fontFamily: "var(--mono)", color: "var(--muted-fg)" }}>{i + 1}</td>
                      <td style={{ padding: "10px 14px", fontWeight: 600 }}>{f.name}</td>
                      <td style={{ padding: "10px 14px", color: "var(--muted-fg)", maxWidth: 280, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{f.desc}</td>
                      <td style={{ padding: "10px 14px", textAlign: "center" }}>
                        <span style={{ fontFamily: "var(--mono)", fontWeight: 700, color: S4_SIZE_COLOR[f.size] }}>{f.size}</span>
                      </td>
                      <td style={{ padding: "10px 14px", textAlign: "center", fontFamily: "var(--mono)", color: "var(--fg-2)" }}>{S4_PTS[f.size]}</td>
                      <td style={{ padding: "10px 14px", color: "var(--muted-fg)", fontSize: 11 }}>{f.deps[0] || "—"}</td>
                      <td style={{ padding: "10px 14px", fontFamily: "var(--mono)", fontWeight: 700, color: "var(--primary)" }}>Sprint {f.sprint}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
            {tab === "sprints" && (
              <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
                <thead>
                  <tr style={{ background: "var(--surface-2)" }}>
                    {["Sprint", "Window", "Features", "Points", "Load"].map((h, i) => (
                      <th key={h} style={{ textAlign: i >= 3 ? "center" : "left", padding: "9px 14px", fontSize: 10.5, fontWeight: 700,
                        color: "var(--muted-fg)", textTransform: "uppercase", letterSpacing: 0.4, borderBottom: "1px solid var(--border)" }}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {Object.keys(sprints).map(Number).sort().map((n) => {
                    const feats = sprints[n];
                    const pts = feats.reduce((t, f) => t + S4_PTS[f.size], 0);
                    const windows = ["Jul 27 – Aug 7", "Aug 10 – Aug 21", "Aug 24 – Sep 4", "Sep 7 – Sep 18"];
                    return (
                      <tr key={n} style={{ borderBottom: "1px solid var(--border)" }}>
                        <td style={{ padding: "12px 14px", fontWeight: 700 }}>Sprint {n}</td>
                        <td style={{ padding: "12px 14px", color: "var(--fg-2)", fontFamily: "var(--mono)", fontSize: 11.5 }}>{windows[n - 1]}</td>
                        <td style={{ padding: "12px 14px", color: "var(--fg-2)" }}>{feats.map((f) => f.name.split(" ").slice(0, 2).join(" ")).join(", ")}</td>
                        <td style={{ padding: "12px 14px", textAlign: "center", fontFamily: "var(--mono)", fontWeight: 700 }}>{pts}</td>
                        <td style={{ padding: "12px 14px" }}>
                          <div style={{ height: 7, borderRadius: 99, background: "var(--track)", overflow: "hidden", width: 90, margin: "0 auto" }}>
                            <div style={{ width: `${Math.min(100, (pts / S4_CAP) * 100)}%`, height: "100%", background: pts > S4_CAP ? "var(--c-red)" : "var(--primary)" }} />
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            )}
            {tab === "summary" && (
              <div style={{ padding: 22, display: "grid", gridTemplateColumns: "repeat(2,1fr)", gap: 16 }}>
                {[["Use case", uc.name], ["Complexity", "L · 6 weeks build"], ["Total features", "7"], ["Total points", "23"], ["Sprints", "4 × 2 weeks"], ["Delivery window", "Jul 27 – Sep 18"]].map(([l, v]) => (
                  <div key={l} style={{ padding: "14px 16px", borderRadius: 10, background: "var(--surface-2)", border: "1px solid var(--border)" }}>
                    <div style={{ fontSize: 11, color: "var(--muted-fg)" }}>{l}</div>
                    <div style={{ fontSize: 16, fontWeight: 700, marginTop: 4 }}>{v}</div>
                  </div>
                ))}
              </div>
            )}
          </div>
          {/* sheet tabs */}
          <div style={{ display: "flex", gap: 2, padding: "8px 12px", borderTop: "1px solid var(--border)", background: "var(--surface-2)" }}>
            {TABS.map(([k, l]) => (
              <button key={k} onClick={() => setTab(k)} style={{ fontFamily: "inherit", cursor: "pointer",
                fontSize: 11.5, fontWeight: 600, padding: "6px 14px", borderRadius: 7,
                color: tab === k ? "var(--c-green)" : "var(--muted-fg)",
                background: tab === k ? "color-mix(in oklab, var(--c-green) 13%, transparent)" : "transparent",
                border: `1px solid ${tab === k ? "color-mix(in oklab, var(--c-green) 28%, transparent)" : "transparent"}` }}>{l}</button>
            ))}
          </div>
        </Card>

        <div style={{ display: "flex", alignItems: "center", gap: 10, fontSize: 11.5, color: "var(--muted-fg)" }}>
          <Icon name="alert" size={13} style={{ color: "var(--muted-fg)" }} />
          Export only — no further app interaction after download. The developer maintains the tracker offline.
        </div>
      </div>
    </AppShell>
  );
}

Object.assign(window, { S4Swimlanes, S4Decompose, S4Export });
