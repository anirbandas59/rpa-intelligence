/* ─────────────────────────────────────────────────────────────
   stage2.jsx — Complexity, three directions
   Exports: S2BandPicker, S2DocReview, S2Matrix
   The band picker is genuinely live (mirrors scoring.ts).
   ───────────────────────────────────────────────────────────── */

const S2_WEIGHTS = {
  activities:     { XS: 2, S: 2, M: 4, L: 6, XL: 8 },
  business_rules: { XS: 2, S: 2, M: 4, L: 6, XL: 8 },
  layouts:        { XS: 1, S: 1, M: 2, L: 3, XL: 4 },
  interfaces:     { XS: 1, S: 1, M: 2, L: 3, XL: 4 },
  technology:     { XS: 1, S: 1, M: 2, L: 3, XL: 4 },
};
const S2_ATTRS = [
  { key: "activities", label: "Activities" },
  { key: "business_rules", label: "Business Rules" },
  { key: "layouts", label: "Layouts" },
  { key: "interfaces", label: "Interfaces" },
  { key: "technology", label: "Add. Technology" },
];
const S2_COLS = ["XS", "S", "M", "L", "XL"];

function s2Score(bands, weights = S2_WEIGHTS) {
  return Object.entries(bands).reduce((t, [k, b]) => t + (b ? (weights[k]?.[b] || 0) : 0), 0);
}
function s2IsXsSpecial(bands) {
  const e = Object.entries(bands).filter(([, b]) => b);
  return e.length <= 2 && e.every(([, b]) => b === "XS");
}
function s2Classify(score, bands) {
  if (bands && s2IsXsSpecial(bands)) return "XS";
  if (score >= 23) return "XL";
  if (score >= 16) return "L";
  if (score >= 9) return "M";
  if (score >= 7) return "S";
  return "XS";
}
const S2_CLASS_RANGE = { XS: "≤6", S: "7–8", M: "9–15", L: "16–22", XL: "23–28" };

// Result panel shared across directions
function S2Result({ bands, weights }) {
  const score = s2Score(bands, weights);
  const cls = s2Classify(score, bands);
  const c = window.RPA_COMPLEXITY[cls];
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      <Card style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 12, paddingTop: 24,
        background: `linear-gradient(160deg, color-mix(in oklab, ${c.color} 12%, var(--surface)), var(--surface) 75%)` }}>
        <SectionLabel>Complexity class</SectionLabel>
        <ComplexityChip cls={cls} size={76} />
        <div style={{ display: "flex", alignItems: "baseline", gap: 8 }}>
          <span style={{ fontFamily: "var(--mono)", fontSize: 30, fontWeight: 700 }}>{score}</span>
          <span style={{ fontSize: 13, color: "var(--muted-fg)" }}>/ 28 pts</span>
        </div>
        {/* score scale ladder */}
        <div style={{ width: "100%", marginTop: 4 }}>
          <div style={{ display: "flex", height: 8, borderRadius: 99, overflow: "hidden", gap: 2 }}>
            {["XS", "S", "M", "L", "XL"].map((k) => (
              <div key={k} style={{ flex: k === cls ? 1.6 : 1, background: k === cls ? window.RPA_COMPLEXITY[k].color : "var(--track)",
                transition: "flex .3s, background .3s" }} />
            ))}
          </div>
          <div style={{ display: "flex", justifyContent: "space-between", marginTop: 6, fontSize: 9.5, color: "var(--muted-fg)", fontFamily: "var(--mono)" }}>
            {["XS", "S", "M", "L", "XL"].map((k) => <span key={k} style={{ color: k === cls ? window.RPA_COMPLEXITY[k].color : "var(--muted-fg)", fontWeight: k === cls ? 700 : 400 }}>{k}</span>)}
          </div>
        </div>
      </Card>
      <Card>
        <SectionLabel style={{ marginBottom: 12 }}>Effort estimate</SectionLabel>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <div>
            <div style={{ fontFamily: "var(--mono)", fontSize: 26, fontWeight: 700, color: c.color }}>{c.effort}</div>
            <div style={{ fontSize: 11, color: "var(--muted-fg)", marginTop: 2 }}>build + unit testing</div>
          </div>
          <Icon name="clock" size={30} style={{ color: "var(--muted-fg)", opacity: 0.5 }} />
        </div>
        <div style={{ marginTop: 14, paddingTop: 12, borderTop: "1px solid var(--border)", display: "flex", justifyContent: "space-between", fontSize: 12 }}>
          <span style={{ color: "var(--muted-fg)" }}>Class range</span>
          <span style={{ fontFamily: "var(--mono)" }}>{S2_CLASS_RANGE[cls]} pts</span>
        </div>
      </Card>
      <Btn icon="play" style={{ width: "100%" }}>Run &amp; snapshot weights</Btn>
      <div style={{ fontSize: 10.5, color: "var(--muted-fg)", textAlign: "center", display: "flex", alignItems: "center", justifyContent: "center", gap: 6 }}>
        <span style={{ width: 5, height: 5, borderRadius: 99, background: "var(--c-green)" }} /> Deterministic · zero LLM · instant
      </div>
    </div>
  );
}

// ══════════════════════════════════════════════════════════════
// A · Live band picker (INTERACTIVE)
// ══════════════════════════════════════════════════════════════
function S2BandPicker() {
  const uc = window.RPA_USECASES[0];
  const { useState } = React;
  const [bands, setBands] = useState({ activities: "XL", business_rules: "XL", layouts: "L", interfaces: "S", technology: "S" });
  const [sources, setSources] = useState({ ...uc.s2.sources });
  const set = (attr, band) => {
    setBands((b) => ({ ...b, [attr]: band }));
    setSources((s) => ({ ...s, [attr]: s[attr] === "ai_extracted" ? "corrected" : (s[attr] || "manual") }));
  };
  return (
    <AppShell activeStage="s2" useCase={uc}
      action={<><Staleness inline text="Inputs changed — re-run" /><Btn variant="subtle" size="sm" icon="history">Runs</Btn></>}>
      <div style={{ height: "100%", overflow: "hidden", padding: "24px 28px", display: "grid", gridTemplateColumns: "1fr 320px", gap: 22 }}>
        <div style={{ display: "flex", flexDirection: "column", gap: 16, minHeight: 0 }}>
          <div>
            <h2 style={{ fontSize: 19, fontWeight: 700, margin: 0 }}>Attribute bands</h2>
            <p style={{ fontSize: 12.5, color: "var(--muted-fg)", margin: "4px 0 0" }}>Click a cell to set each attribute. The score recomputes live — try it.</p>
          </div>
          <Card pad={0} style={{ overflow: "hidden" }}>
            {/* header */}
            <div style={{ display: "grid", gridTemplateColumns: "1.5fr repeat(5, 1fr) 0.7fr", alignItems: "center",
              padding: "12px 18px", borderBottom: "1px solid var(--border)" }}>
              <span style={{ fontSize: 10.5, fontWeight: 700, letterSpacing: 0.5, color: "var(--muted-fg)", textTransform: "uppercase" }}>Attribute</span>
              {S2_COLS.map((c) => <span key={c} style={{ textAlign: "center", fontFamily: "var(--mono)", fontSize: 12, fontWeight: 700, color: window.RPA_COMPLEXITY[c].color }}>{c}</span>)}
              <span style={{ textAlign: "right", fontSize: 10.5, fontWeight: 700, color: "var(--muted-fg)" }}>WT</span>
            </div>
            {S2_ATTRS.map((a, idx) => (
              <div key={a.key} style={{ display: "grid", gridTemplateColumns: "1.5fr repeat(5, 1fr) 0.7fr", alignItems: "center",
                padding: "12px 18px", borderBottom: idx < S2_ATTRS.length - 1 ? "1px solid var(--border)" : "none" }}>
                <span style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 13, fontWeight: 500 }}>
                  {a.label} <SourceBadge source={sources[a.key]} />
                </span>
                {S2_COLS.map((c) => {
                  const active = bands[a.key] === c;
                  const col = window.RPA_COMPLEXITY[c].color;
                  return (
                    <div key={c} style={{ display: "flex", justifyContent: "center" }}>
                      <button onClick={() => set(a.key, c)} style={{
                        width: 42, height: 34, borderRadius: 8, cursor: "pointer", fontFamily: "var(--mono)", fontSize: 12, fontWeight: 700,
                        color: active ? "#0b0b12" : "var(--muted-fg)",
                        background: active ? col : "var(--surface-2)",
                        border: `1px solid ${active ? col : "var(--border)"}`,
                        boxShadow: active ? `0 0 12px color-mix(in oklab, ${col} 45%, transparent)` : "none",
                        transition: "all .14s" }}>{S2_WEIGHTS[a.key][c]}</button>
                    </div>
                  );
                })}
                <span style={{ textAlign: "right", fontFamily: "var(--mono)", fontSize: 14, fontWeight: 700, color: "var(--fg)" }}>{S2_WEIGHTS[a.key][bands[a.key]]}</span>
              </div>
            ))}
            {/* total row */}
            <div style={{ display: "grid", gridTemplateColumns: "1.5fr repeat(5, 1fr) 0.7fr", alignItems: "center",
              padding: "12px 18px", background: "var(--surface-2)", borderTop: "1px solid var(--border)" }}>
              <span style={{ fontSize: 12, fontWeight: 700, letterSpacing: 0.5, color: "var(--muted-fg)", textTransform: "uppercase" }}>Total score</span>
              <span style={{ gridColumn: "2 / 7" }} />
              <span style={{ textAlign: "right", fontFamily: "var(--mono)", fontSize: 17, fontWeight: 700, color: "var(--primary)" }}>{s2Score(bands)}</span>
            </div>
          </Card>
          {/* input source tabs */}
          <Card style={{ display: "flex", alignItems: "center", gap: 12 }}>
            <SectionLabel>Source</SectionLabel>
            <div style={{ display: "flex", gap: 6 }}>
              {[["doc", "Document", "doc"], ["text", "Paste text", "list"], ["manual", "Manual bands", "edit"]].map(([k, l, ic], i) => (
                <span key={k} style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 12, fontWeight: 500, padding: "6px 11px", borderRadius: 8,
                  color: i === 2 ? "var(--fg)" : "var(--muted-fg)",
                  background: i === 2 ? "color-mix(in oklab, var(--primary) 13%, transparent)" : "transparent",
                  border: `1px solid ${i === 2 ? "color-mix(in oklab, var(--primary) 28%, transparent)" : "var(--border)"}` }}>
                  <Icon name={ic} size={13} /> {l}
                </span>
              ))}
            </div>
            <span style={{ flex: 1 }} />
            <span style={{ fontSize: 11, color: "var(--muted-fg)" }}>XS special case: ≤2 attrs, all XS</span>
          </Card>
        </div>
        <S2Result bands={bands} />
      </div>
    </AppShell>
  );
}

// ══════════════════════════════════════════════════════════════
// B · Document → AI review
// ══════════════════════════════════════════════════════════════
function S2DocReview() {
  const uc = window.RPA_USECASES[0];
  const v = uc.s2;
  const EXTRACT_NOTE = {
    activities: "6 distinct process steps incl. OCR, validation, 3-way match",
    business_rules: "Tolerance thresholds, approval matrix, duplicate detection",
    layouts: "3 screens — portal, ERP entry, approval card",
    interfaces: "ERP API + mailbox connector",
    technology: "AI Builder OCR add-on",
  };
  return (
    <AppShell activeStage="s2" useCase={uc}
      action={<><Pill color="var(--primary)" style={{ height: 30 }}><Icon name="spark" size={12} /> Extracted by Haiku</Pill><Btn size="sm" icon="check">Accept &amp; run</Btn></>}>
      <div style={{ height: "100%", overflow: "hidden", padding: "24px 28px", display: "grid", gridTemplateColumns: "1fr 1.15fr", gap: 22 }}>
        {/* document */}
        <div style={{ display: "flex", flexDirection: "column", gap: 14, minHeight: 0 }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
            <SectionLabel>Source document</SectionLabel>
            <span style={{ display: "flex", alignItems: "center", gap: 7, fontSize: 12, color: "var(--fg-2)" }}>
              <Icon name="doc" size={14} style={{ color: "var(--primary)" }} /> invoice_process_spec.pdf
            </span>
          </div>
          <Card pad={20} style={{ flex: 1, minHeight: 0, overflow: "hidden", fontFamily: "var(--sans)", lineHeight: 1.7, fontSize: 12.5, color: "var(--fg-2)" }}>
            <div style={{ fontWeight: 700, fontSize: 14, color: "var(--fg)", marginBottom: 10 }}>Invoice Processing — Process Definition</div>
            <p style={{ margin: "0 0 10px" }}>The bot logs into the supplier portal and <mark style={{ background: "color-mix(in oklab, var(--c-teal) 22%, transparent)", color: "var(--fg)", padding: "1px 3px", borderRadius: 3 }}>downloads all pending invoices</mark>, then <mark style={{ background: "color-mix(in oklab, var(--c-teal) 22%, transparent)", color: "var(--fg)", padding: "1px 3px", borderRadius: 3 }}>extracts data using OCR</mark> across structured and semi-structured layouts.</p>
            <p style={{ margin: "0 0 10px" }}>Extracted values are <mark style={{ background: "color-mix(in oklab, var(--primary) 24%, transparent)", color: "var(--fg)", padding: "1px 3px", borderRadius: 3 }}>validated against purchase orders</mark> using configurable tolerance thresholds and an approval matrix. Duplicates are flagged and routed to exception handling.</p>
            <p style={{ margin: "0 0 10px" }}>Validated invoices are <mark style={{ background: "color-mix(in oklab, var(--c-amber) 22%, transparent)", color: "var(--fg)", padding: "1px 3px", borderRadius: 3 }}>posted to the ERP via its REST API</mark>; exceptions await human approval through an adaptive card before archival.</p>
            <p style={{ margin: 0, color: "var(--muted-fg)" }}>Three primary interfaces are involved: the supplier portal (UI), the ERP entry screen, and the approval card surface…</p>
          </Card>
          <div style={{ display: "flex", gap: 9 }}>
            <Btn variant="outline" size="sm" icon="upload" style={{ flex: 1 }}>Replace document</Btn>
            <Btn variant="outline" size="sm" icon="list" style={{ flex: 1 }}>Paste text instead</Btn>
          </div>
        </div>

        {/* extracted bands review */}
        <div style={{ display: "flex", flexDirection: "column", gap: 14, minHeight: 0 }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
            <SectionLabel>Extracted bands — review &amp; correct</SectionLabel>
            <span style={{ fontSize: 11, color: "var(--muted-fg)" }}>tap a band to override</span>
          </div>
          <Card pad={0} style={{ flex: 1, minHeight: 0, overflow: "hidden", display: "flex", flexDirection: "column" }}>
            {S2_ATTRS.map((a, idx) => (
              <div key={a.key} style={{ padding: "13px 18px", borderBottom: idx < S2_ATTRS.length - 1 ? "1px solid var(--border)" : "none" }}>
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 9 }}>
                  <span style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 13, fontWeight: 600 }}>{a.label} <SourceBadge source={v.sources[a.key]} /></span>
                  {v.sources[a.key] === "corrected" && <button style={{ fontSize: 11, color: "var(--primary)", background: "none", border: "none", cursor: "pointer", fontFamily: "inherit" }}>Reset to AI</button>}
                </div>
                <div style={{ display: "flex", gap: 5, marginBottom: 8 }}>
                  {S2_COLS.map((c) => {
                    const active = v.bands[a.key] === c;
                    const col = window.RPA_COMPLEXITY[c].color;
                    return <div key={c} style={{ flex: 1, height: 28, borderRadius: 7, display: "flex", alignItems: "center", justifyContent: "center",
                      fontFamily: "var(--mono)", fontSize: 11, fontWeight: 700, cursor: "pointer",
                      color: active ? "#0b0b12" : "var(--muted-fg)", background: active ? col : "var(--surface-2)",
                      border: `1px solid ${active ? col : "var(--border)"}` }}>{c}</div>;
                  })}
                </div>
                <div style={{ fontSize: 11, color: "var(--muted-fg)", display: "flex", gap: 6, alignItems: "flex-start" }}>
                  <Icon name="spark" size={11} style={{ color: "var(--primary)", marginTop: 1, flexShrink: 0 }} /> {EXTRACT_NOTE[a.key]}
                </div>
              </div>
            ))}
            <div style={{ marginTop: "auto", padding: "13px 18px", background: "var(--surface-2)", borderTop: "1px solid var(--border)",
              display: "flex", alignItems: "center", justifyContent: "space-between" }}>
              <span style={{ display: "flex", alignItems: "center", gap: 10 }}>
                <span style={{ fontSize: 12, color: "var(--muted-fg)" }}>Computed</span>
                <ComplexityChip cls={v.class} size={28} />
                <span style={{ fontFamily: "var(--mono)", fontSize: 13, fontWeight: 700 }}>{v.score} pts</span>
              </span>
              <span style={{ fontSize: 12, color: "var(--fg-2)" }}>{window.RPA_COMPLEXITY[v.class].effort}</span>
            </div>
          </Card>
        </div>
      </div>
    </AppShell>
  );
}

// ══════════════════════════════════════════════════════════════
// C · Weight matrix editor + run compare
// ══════════════════════════════════════════════════════════════
function S2Matrix() {
  const uc = window.RPA_USECASES[0];
  const { useState } = React;
  const [weights, setWeights] = useState(JSON.parse(JSON.stringify(S2_WEIGHTS)));
  const bands = uc.s2.bands;
  const bump = (attr, col, d) => setWeights((w) => ({ ...w, [attr]: { ...w[attr], [col]: Math.max(0, w[attr][col] + d) } }));
  const liveScore = s2Score(bands, weights);
  const liveClass = s2Classify(liveScore, bands);
  const baseScore = uc.s2.score;
  const changed = JSON.stringify(weights) !== JSON.stringify(S2_WEIGHTS);

  const RUNS = [
    { n: 3, model: "Manual weights v2", time: "Today · 14:22", cls: "L", score: 21, active: true },
    { n: 2, model: "Haiku extract · default", time: "Today · 11:05", cls: "L", score: 21 },
    { n: 1, model: "Haiku extract · default", time: "Yesterday", cls: "M", score: 14 },
  ];

  return (
    <AppShell activeStage="s2" useCase={uc} breadcrumb={["RPA Migration Project", "Stage 2 · Weights & history"]}
      action={<><Btn variant="subtle" size="sm" icon="refresh">Reset matrix</Btn><Btn size="sm" icon="play" disabled={!changed}>Re-run with new weights</Btn></>}>
      <div style={{ height: "100%", overflow: "hidden", padding: "24px 28px", display: "grid", gridTemplateColumns: "1.5fr 1fr", gap: 22 }}>
        {/* editable matrix */}
        <div style={{ display: "flex", flexDirection: "column", gap: 14, minHeight: 0 }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
            <div>
              <h2 style={{ fontSize: 18, fontWeight: 700, margin: 0 }}>Weight matrix</h2>
              <p style={{ fontSize: 12, color: "var(--muted-fg)", margin: "3px 0 0" }}>Project-level. Edits preview live before you commit a re-run.</p>
            </div>
            {changed && <Pill color="var(--c-amber)"><Icon name="edit" size={11} /> Unsaved edits</Pill>}
          </div>
          <Card pad={0} style={{ overflow: "hidden" }}>
            <div style={{ display: "grid", gridTemplateColumns: "1.4fr repeat(5, 1fr)", padding: "11px 16px", borderBottom: "1px solid var(--border)" }}>
              <span style={{ fontSize: 10.5, fontWeight: 700, color: "var(--muted-fg)", textTransform: "uppercase" }}>Attribute</span>
              {S2_COLS.map((c) => <span key={c} style={{ textAlign: "center", fontFamily: "var(--mono)", fontSize: 12, fontWeight: 700, color: window.RPA_COMPLEXITY[c].color }}>{c}</span>)}
            </div>
            {S2_ATTRS.map((a, idx) => (
              <div key={a.key} style={{ display: "grid", gridTemplateColumns: "1.4fr repeat(5, 1fr)", alignItems: "center",
                padding: "10px 16px", borderBottom: idx < S2_ATTRS.length - 1 ? "1px solid var(--border)" : "none" }}>
                <span style={{ fontSize: 12.5, fontWeight: 500 }}>{a.label}</span>
                {S2_COLS.map((c) => {
                  const isSel = bands[a.key] === c;
                  const edited = weights[a.key][c] !== S2_WEIGHTS[a.key][c];
                  return (
                    <div key={c} style={{ display: "flex", justifyContent: "center" }}>
                      <div style={{ display: "flex", alignItems: "center", gap: 4, padding: "4px 6px", borderRadius: 8,
                        background: isSel ? "color-mix(in oklab, var(--primary) 14%, transparent)" : "transparent",
                        border: `1px solid ${isSel ? "color-mix(in oklab, var(--primary) 30%, transparent)" : "transparent"}` }}>
                        <button onClick={() => bump(a.key, c, -1)} style={{ width: 16, height: 16, borderRadius: 4, border: "1px solid var(--border)", background: "var(--surface-2)", color: "var(--muted-fg)", cursor: "pointer", fontSize: 11, lineHeight: 1, padding: 0 }}>−</button>
                        <span style={{ fontFamily: "var(--mono)", fontSize: 13, fontWeight: 700, width: 14, textAlign: "center", color: edited ? "var(--c-amber)" : "var(--fg)" }}>{weights[a.key][c]}</span>
                        <button onClick={() => bump(a.key, c, 1)} style={{ width: 16, height: 16, borderRadius: 4, border: "1px solid var(--border)", background: "var(--surface-2)", color: "var(--muted-fg)", cursor: "pointer", fontSize: 11, lineHeight: 1, padding: 0 }}>+</button>
                      </div>
                    </div>
                  );
                })}
              </div>
            ))}
          </Card>
          {/* live recompute strip */}
          <Card style={{ display: "flex", alignItems: "center", gap: 20 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 11 }}>
              <ComplexityChip cls={liveClass} size={40} />
              <div>
                <div style={{ fontSize: 11, color: "var(--muted-fg)" }}>Live recompute · {uc.name.split(" ")[0]} bands</div>
                <div style={{ fontSize: 13, fontWeight: 600 }}>{window.RPA_COMPLEXITY[liveClass].effort} effort</div>
              </div>
            </div>
            <div style={{ flex: 1 }} />
            <div style={{ textAlign: "right" }}>
              <div style={{ display: "flex", alignItems: "baseline", gap: 8 }}>
                <span style={{ fontFamily: "var(--mono)", fontSize: 24, fontWeight: 700, color: liveScore !== baseScore ? "var(--c-amber)" : "var(--fg)" }}>{liveScore}</span>
                {liveScore !== baseScore && <span style={{ fontSize: 12, color: "var(--muted-fg)" }}>was {baseScore}</span>}
              </div>
              <div style={{ fontSize: 10.5, color: "var(--muted-fg)" }}>total score</div>
            </div>
          </Card>
        </div>

        {/* run history + compare */}
        <div style={{ display: "flex", flexDirection: "column", gap: 14, minHeight: 0 }}>
          <SectionLabel>Run history</SectionLabel>
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            {RUNS.map((r) => (
              <div key={r.n} style={{ display: "flex", alignItems: "center", gap: 12, padding: "11px 13px", borderRadius: 11,
                background: r.active ? "color-mix(in oklab, var(--primary) 10%, transparent)" : "var(--surface)",
                border: `1px solid ${r.active ? "color-mix(in oklab, var(--primary) 32%, transparent)" : "var(--border)"}` }}>
                <span style={{ fontFamily: "var(--mono)", fontSize: 12, fontWeight: 700, color: r.active ? "var(--primary)" : "var(--muted-fg)" }}>#{r.n}</span>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: 12.5, fontWeight: 500 }}>{r.model}</div>
                  <div style={{ fontSize: 10.5, color: "var(--muted-fg)" }}>{r.time}</div>
                </div>
                <ComplexityChip cls={r.cls} size={24} />
                <span style={{ fontFamily: "var(--mono)", fontSize: 13, fontWeight: 700 }}>{r.score}</span>
              </div>
            ))}
          </div>
          {/* compare */}
          <SectionLabel style={{ marginTop: 6 }}>Compare #1 ↔ #2</SectionLabel>
          <Card style={{ flex: 1, minHeight: 0 }}>
            <div style={{ display: "grid", gridTemplateColumns: "1.3fr 1fr 1fr", gap: 8, fontSize: 11, color: "var(--muted-fg)", paddingBottom: 9, borderBottom: "1px solid var(--border)" }}>
              <span>Attribute</span><span style={{ textAlign: "center" }}>Run #1</span><span style={{ textAlign: "center" }}>Run #2</span>
            </div>
            {S2_ATTRS.map((a) => {
              const before = { activities: "M", business_rules: "M", layouts: "S", interfaces: "S", technology: "S" }[a.key];
              const after = uc.s2.bands[a.key];
              const diff = before !== after;
              return (
                <div key={a.key} style={{ display: "grid", gridTemplateColumns: "1.3fr 1fr 1fr", gap: 8, alignItems: "center", padding: "9px 0", borderBottom: "1px solid var(--border)" }}>
                  <span style={{ fontSize: 12, color: "var(--fg-2)" }}>{a.label}</span>
                  <span style={{ textAlign: "center" }}><ComplexityChip cls={before} size={22} /></span>
                  <span style={{ textAlign: "center", display: "flex", alignItems: "center", justifyContent: "center", gap: 5 }}>
                    <ComplexityChip cls={after} size={22} />
                    {diff && <Icon name="arrowR" size={11} style={{ color: "var(--c-amber)" }} />}
                  </span>
                </div>
              );
            })}
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", paddingTop: 11 }}>
              <span style={{ fontSize: 12, fontWeight: 600 }}>Class changed</span>
              <span style={{ display: "flex", alignItems: "center", gap: 7 }}>
                <ComplexityChip cls="M" size={24} /><Icon name="arrowR" size={12} style={{ color: "var(--c-amber)" }} /><ComplexityChip cls="L" size={24} />
              </span>
            </div>
          </Card>
        </div>
      </div>
    </AppShell>
  );
}

Object.assign(window, { S2BandPicker, S2DocReview, S2Matrix });
