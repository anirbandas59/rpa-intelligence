/* ─────────────────────────────────────────────────────────────
   hub.jsx — Project Hub, three layout directions
   Exports: HubRail, HubMatrix, HubCommand
   ───────────────────────────────────────────────────────────── */

const STAGES_FULL = [
  { id: "s1", n: "1", label: "Migration Assessment", icon: "target" },
  { id: "s2", n: "2", label: "Complexity", icon: "grid" },
  { id: "s3", n: "3", label: "Timeline", icon: "calendar" },
  { id: "s4", n: "4", label: "Sprint Tracker", icon: "layers" },
];

function ReadinessDots({ r }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 5 }}>
      {STAGES_FULL.map((s) => <StatusDot key={s.id} status={r[s.id]} size={7} />)}
    </div>
  );
}

// mini stage-specific visualization for nodes
function NodeViz({ stage, uc }) {
  if (stage === "s1") {
    const v = uc.s1;
    if (!v) return <span style={{ fontSize: 11, color: "var(--muted-fg)" }}>No score yet</span>;
    const c = window.RPA_BANDS[v.band].color;
    return (
      <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
        <div style={{ fontFamily: "var(--mono)", fontSize: 26, fontWeight: 700, color: c }}>{v.score}</div>
        <PriorityBadge band={v.band} />
      </div>
    );
  }
  if (stage === "s2") {
    const v = uc.s2;
    if (!v) return <span style={{ fontSize: 11, color: "var(--muted-fg)" }}>Not scored</span>;
    return (
      <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
        <ComplexityChip cls={v.class} size={30} />
        <div style={{ fontSize: 12, color: "var(--fg-2)" }}>{window.RPA_COMPLEXITY[v.class].effort}</div>
      </div>
    );
  }
  if (stage === "s3") {
    const v = uc.s3;
    if (!v) return <span style={{ fontSize: 11, color: "var(--muted-fg)" }}>No timeline</span>;
    return (
      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
        <MiniSpark values={[1, 1, v.effortWeeks, 1, 1.5, 0.5]} color="var(--primary)" w={70} h={22} />
        <span style={{ fontSize: 11.5, color: "var(--fg-2)" }}>~{v.effortWeeks + 4} wks</span>
      </div>
    );
  }
  const v = uc.s4;
  if (!v) return <span style={{ fontSize: 11, color: "var(--muted-fg)" }}>No sprints</span>;
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
      {Array.from({ length: v.sprintCount }).map((_, i) =>
        <span key={i} style={{ width: 14, height: 22, borderRadius: 3, background: "color-mix(in oklab, var(--primary) 35%, transparent)", border: "1px solid color-mix(in oklab, var(--primary) 45%, transparent)" }} />)}
      <span style={{ fontSize: 11.5, color: "var(--fg-2)", marginLeft: 2 }}>{v.sprintCount} sprints</span>
    </div>
  );
}

// ══════════════════════════════════════════════════════════════
// A · Pipeline Rail
// ══════════════════════════════════════════════════════════════
function HubRail() {
  const uc = window.RPA_USECASES[0];
  const ucs = window.RPA_USECASES;
  return (
    <AppShell activeStage={null} useCase={uc}
      breadcrumb={["RPA Migration Project"]}
      action={<><Btn variant="subtle" size="sm" icon="upload">Import</Btn><Btn size="sm" icon="plus">New use case</Btn></>}>
      <div style={{ height: "100%", overflow: "hidden", padding: "26px 30px", display: "flex", flexDirection: "column", gap: 22 }}>
        {/* hero */}
        <div style={{ display: "flex", alignItems: "flex-end", justifyContent: "space-between" }}>
          <div>
            <h1 className="rpa-gradient-text" style={{ fontSize: 30, fontWeight: 700, letterSpacing: -0.6, margin: 0 }}>RPA Migration Project</h1>
            <p style={{ fontSize: 13.5, color: "var(--muted-fg)", margin: "6px 0 0" }}>Four-stage delivery intelligence across {ucs.length} use cases · 2 quick wins identified</p>
          </div>
          <div style={{ display: "flex", gap: 26 }}>
            {[["6", "use cases"], ["2", "quick wins"], ["48", "build weeks"], ["14", "features"]].map(([n, l]) => (
              <div key={l}>
                <div style={{ fontFamily: "var(--mono)", fontSize: 24, fontWeight: 700 }}>{n}</div>
                <div style={{ fontSize: 11, color: "var(--muted-fg)" }}>{l}</div>
              </div>
            ))}
          </div>
        </div>

        {/* pipeline rail */}
        <div>
          <SectionLabel style={{ marginBottom: 12 }}>Assessment pipeline · {uc.name}</SectionLabel>
          <div style={{ display: "flex", alignItems: "stretch", gap: 0 }}>
            {STAGES_FULL.map((s, i) => (
              <React.Fragment key={s.id}>
                <div className="rpa-card-hover" style={{ flex: 1, borderRadius: 14, padding: 16, background: "var(--surface)",
                  border: `1px solid ${uc.readiness[s.id] === "running" ? "color-mix(in oklab, var(--primary) 40%, transparent)" : "var(--border)"}`,
                  position: "relative" }}>
                  <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 14 }}>
                    <span style={{ display: "flex", alignItems: "center", gap: 8 }}>
                      <span style={{ fontFamily: "var(--mono)", fontSize: 10.5, fontWeight: 700, color: "var(--primary)",
                        border: "1px solid color-mix(in oklab, var(--primary) 30%, transparent)", borderRadius: 5, padding: "2px 5px" }}>S{s.n}</span>
                      <Icon name={s.icon} size={15} style={{ color: "var(--muted-fg)" }} />
                    </span>
                    <span style={{ display: "flex", alignItems: "center", gap: 5, fontSize: 11, color: window.RPA_STATUS[uc.readiness[s.id]].color }}>
                      <StatusDot status={uc.readiness[s.id]} size={7} /> {window.RPA_STATUS[uc.readiness[s.id]].label}
                    </span>
                  </div>
                  <div style={{ fontSize: 13.5, fontWeight: 600, marginBottom: 14, lineHeight: 1.25 }}>{s.label}</div>
                  <div style={{ minHeight: 38, display: "flex", alignItems: "center" }}><NodeViz stage={s.id} uc={uc} /></div>
                  <Btn variant={uc.readiness[s.id] === "not_ready" ? "outline" : "subtle"} size="sm" iconR="arrowR" style={{ width: "100%", marginTop: 14 }}>
                    {uc.readiness[s.id] === "running" ? "View progress" : "Open"}
                  </Btn>
                </div>
                {i < STAGES_FULL.length - 1 && (
                  <div style={{ width: 28, display: "flex", alignItems: "center", justifyContent: "center", color: "var(--muted-fg)" }}>
                    <Icon name="chevR" size={16} style={{ opacity: 0.5 }} />
                  </div>
                )}
              </React.Fragment>
            ))}
          </div>
        </div>

        {/* portfolio table */}
        <div style={{ flex: 1, minHeight: 0, display: "flex", flexDirection: "column" }}>
          <SectionLabel style={{ marginBottom: 10 }}>All use cases</SectionLabel>
          <div style={{ borderRadius: 13, border: "1px solid var(--border)", overflow: "hidden", background: "var(--surface)" }}>
            <div style={{ display: "grid", gridTemplateColumns: "1.9fr 0.9fr 0.7fr 1fr 0.9fr", gap: 0, padding: "9px 16px",
              fontSize: 10.5, fontWeight: 700, letterSpacing: 0.6, color: "var(--muted-fg)", textTransform: "uppercase", borderBottom: "1px solid var(--border)" }}>
              <span>Use case</span><span>Priority</span><span>Complexity</span><span>Pipeline</span><span style={{ textAlign: "right" }}>Progress</span>
            </div>
            {window.RPA_USECASES.map((u, idx) => {
              const done = STAGES_FULL.filter((s) => u.readiness[s.id] === "complete").length;
              return (
                <div key={u.id} style={{ display: "grid", gridTemplateColumns: "1.9fr 0.9fr 0.7fr 1fr 0.9fr", gap: 0, padding: "12px 16px",
                  alignItems: "center", borderBottom: idx < 5 ? "1px solid var(--border)" : "none",
                  background: idx === 0 ? "color-mix(in oklab, var(--primary) 6%, transparent)" : "transparent" }}>
                  <div style={{ minWidth: 0, paddingRight: 12 }}>
                    <div style={{ fontSize: 13, fontWeight: 600, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{u.name}</div>
                    <div style={{ fontSize: 11, color: "var(--muted-fg)", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{u.platform} · {u.install}</div>
                  </div>
                  <div>{u.s1 ? <PriorityBadge band={u.s1.band} /> : <span style={{ fontSize: 11, color: "var(--muted-fg)" }}>—</span>}</div>
                  <div>{u.s2 ? <ComplexityChip cls={u.s2.class} size={26} /> : <span style={{ fontSize: 11, color: "var(--muted-fg)" }}>—</span>}</div>
                  <div><ReadinessDots r={u.readiness} /></div>
                  <div style={{ display: "flex", alignItems: "center", justifyContent: "flex-end", gap: 8 }}>
                    <div style={{ width: 52, height: 5, borderRadius: 99, background: "var(--track)", overflow: "hidden" }}>
                      <div style={{ width: `${(done / 4) * 100}%`, height: "100%", background: "var(--c-green)" }} />
                    </div>
                    <span style={{ fontFamily: "var(--mono)", fontSize: 11, color: "var(--muted-fg)" }}>{done}/4</span>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </AppShell>
  );
}

// ══════════════════════════════════════════════════════════════
// B · Portfolio Matrix (priority × complexity)
// ══════════════════════════════════════════════════════════════
function HubMatrix() {
  const uc = window.RPA_USECASES[0];
  // y axis: priority score (high top); x axis: complexity (low left)
  const COMPLEX_X = { XS: 0, S: 1, M: 2, L: 3, XL: 4 };
  const plotted = window.RPA_USECASES.filter((u) => u.s1);
  return (
    <AppShell activeStage={null} useCase={uc} breadcrumb={["RPA Migration Project"]}
      action={<><Btn variant="subtle" size="sm" icon="filter">Filter</Btn><Btn size="sm" icon="plus">New use case</Btn></>}>
      <div style={{ height: "100%", padding: "26px 30px", display: "flex", flexDirection: "column", gap: 20, overflow: "hidden" }}>
        <div>
          <h1 className="rpa-gradient-text" style={{ fontSize: 28, fontWeight: 700, letterSpacing: -0.5, margin: 0 }}>Portfolio Map</h1>
          <p style={{ fontSize: 13, color: "var(--muted-fg)", margin: "5px 0 0" }}>Value vs. effort — where to invest first. Bubble size = build weeks.</p>
        </div>
        <div style={{ flex: 1, display: "grid", gridTemplateColumns: "1.55fr 1fr", gap: 22, minHeight: 0 }}>
          {/* matrix */}
          <div style={{ borderRadius: 14, border: "1px solid var(--border)", background: "var(--surface)", padding: "20px 22px 16px 50px", position: "relative", display: "flex", flexDirection: "column" }}>
            <div style={{ position: "absolute", left: 14, top: "50%", transform: "rotate(-90deg) translateX(50%)", transformOrigin: "left center",
              fontSize: 10.5, fontWeight: 700, letterSpacing: 1, color: "var(--muted-fg)", whiteSpace: "nowrap" }}>MIGRATION SCORE →</div>
            <div style={{ flex: 1, position: "relative", borderLeft: "1px solid var(--border)", borderBottom: "1px solid var(--border)", margin: "4px 4px 22px 4px" }}>
              {/* quadrant tint: top-left = quick win zone */}
              <div style={{ position: "absolute", left: 0, top: 0, width: "45%", height: "42%", background: "color-mix(in oklab, var(--c-green) 8%, transparent)", borderRight: "1px dashed var(--border)", borderBottom: "1px dashed var(--border)" }} />
              <div style={{ position: "absolute", left: 8, top: 8, fontSize: 10, fontWeight: 700, color: "var(--c-green)", letterSpacing: 0.5, opacity: 0.8 }}>QUICK WINS</div>
              {/* gridlines */}
              {[0.25, 0.5, 0.75].map((g) => <div key={g} style={{ position: "absolute", left: 0, right: 0, top: `${g * 100}%`, borderTop: "1px dashed color-mix(in oklab, var(--border) 60%, transparent)" }} />)}
              {plotted.map((u) => {
                const x = (COMPLEX_X[u.s2 ? u.s2.class : "M"] / 4) * 88 + 4;
                const y = (1 - u.s1.score / 100) * 86 + 2;
                const wk = u.s2 ? u.s2.effortMax : 5;
                const sz = 26 + wk * 3;
                const c = window.RPA_BANDS[u.s1.band].color;
                return (
                  <div key={u.id} title={u.name} style={{ position: "absolute", left: `${x}%`, top: `${y}%`, transform: "translate(-50%,-50%)" }}>
                    <div style={{ width: sz, height: sz, borderRadius: 99, background: `color-mix(in oklab, ${c} 24%, transparent)`,
                      border: `1.5px solid ${c}`, display: "flex", alignItems: "center", justifyContent: "center",
                      fontFamily: "var(--mono)", fontSize: 11, fontWeight: 700, color: c, boxShadow: `0 0 14px color-mix(in oklab, ${c} 30%, transparent)` }}>{u.s1.score}</div>
                  </div>
                );
              })}
            </div>
            <div style={{ display: "flex", justifyContent: "space-between", paddingLeft: 4, fontSize: 10.5, fontWeight: 700, letterSpacing: 1, color: "var(--muted-fg)" }}>
              <span>COMPLEXITY →</span>
              <span style={{ display: "flex", gap: 30 }}>{["XS", "S", "M", "L", "XL"].map((c) => <span key={c}>{c}</span>)}</span>
            </div>
          </div>
          {/* ranked recommendations */}
          <div style={{ display: "flex", flexDirection: "column", gap: 12, minHeight: 0 }}>
            <SectionLabel>Recommended sequence</SectionLabel>
            <div style={{ display: "flex", flexDirection: "column", gap: 9, overflow: "hidden" }}>
              {[...plotted].sort((a, b) => b.s1.score - a.s1.score).map((u, i) => (
                <div key={u.id} className="rpa-card-hover" style={{ display: "flex", alignItems: "center", gap: 12, padding: "11px 13px", borderRadius: 11,
                  background: "var(--surface)", border: "1px solid var(--border)" }}>
                  <span style={{ fontFamily: "var(--mono)", fontSize: 15, fontWeight: 700, color: "var(--muted-fg)", width: 20 }}>{i + 1}</span>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontSize: 12.5, fontWeight: 600, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{u.name}</div>
                    <div style={{ display: "flex", gap: 6, marginTop: 4 }}>
                      <PriorityBadge band={u.s1.band} />
                      {u.s2 && <ComplexityChip cls={u.s2.class} size={20} />}
                    </div>
                  </div>
                  <ReadinessDots r={u.readiness} />
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </AppShell>
  );
}

// ══════════════════════════════════════════════════════════════
// C · Command Center (ops dashboard + agent)
// ══════════════════════════════════════════════════════════════
function HubCommand() {
  const uc = window.RPA_USECASES[0];
  return (
    <AppShell activeStage={null} useCase={uc} breadcrumb={["RPA Migration Project", "Command center"]}
      action={<><Btn variant="subtle" size="sm" icon="bot">Autonomous run</Btn><Btn size="sm" icon="plus">New use case</Btn></>}>
      <div style={{ height: "100%", display: "grid", gridTemplateColumns: "270px 1fr 312px", overflow: "hidden" }}>
        {/* use-case list */}
        <div style={{ borderRight: "1px solid var(--border)", display: "flex", flexDirection: "column", overflow: "hidden" }}>
          <div style={{ padding: "16px 16px 10px" }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8, padding: "8px 11px", borderRadius: 9, border: "1px solid var(--border)", background: "var(--surface)" }}>
              <Icon name="search" size={14} style={{ color: "var(--muted-fg)" }} />
              <span style={{ fontSize: 12.5, color: "var(--muted-fg)" }}>Search use cases…</span>
            </div>
          </div>
          <div style={{ flex: 1, overflow: "hidden", padding: "0 10px", display: "flex", flexDirection: "column", gap: 4 }}>
            {window.RPA_USECASES.map((u, i) => (
              <div key={u.id} className="rpa-card-hover" style={{ padding: "11px 12px", borderRadius: 10, cursor: "pointer",
                background: i === 0 ? "color-mix(in oklab, var(--primary) 12%, transparent)" : "transparent",
                border: `1px solid ${i === 0 ? "color-mix(in oklab, var(--primary) 28%, transparent)" : "transparent"}` }}>
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8 }}>
                  <span style={{ fontSize: 12.5, fontWeight: 600, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{u.name}</span>
                  {u.s1 && <PriorityBadge band={u.s1.band} />}
                </div>
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginTop: 8 }}>
                  <ReadinessDots r={u.readiness} />
                  <span style={{ fontSize: 10.5, color: "var(--muted-fg)" }}>{u.platform}</span>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* center detail */}
        <div style={{ overflow: "hidden", padding: "22px 26px", display: "flex", flexDirection: "column", gap: 18 }}>
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
              <h2 style={{ fontSize: 21, fontWeight: 700, margin: 0, letterSpacing: -0.3 }}>{uc.name}</h2>
              <PriorityBadge band={uc.s1.band} />
            </div>
            <p style={{ fontSize: 12.5, color: "var(--muted-fg)", margin: "5px 0 0" }}>{uc.desc}</p>
          </div>
          {/* stage status grid */}
          <div style={{ display: "grid", gridTemplateColumns: "repeat(2,1fr)", gap: 12 }}>
            {STAGES_FULL.map((s) => (
              <div key={s.id} className="rpa-card-hover" style={{ borderRadius: 12, padding: 15, background: "var(--surface)", border: "1px solid var(--border)" }}>
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 12 }}>
                  <span style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 12.5, fontWeight: 600 }}>
                    <Icon name={s.icon} size={15} style={{ color: "var(--muted-fg)" }} />{s.label}
                  </span>
                  <span style={{ display: "flex", alignItems: "center", gap: 5, fontSize: 10.5, color: window.RPA_STATUS[uc.readiness[s.id]].color }}>
                    <StatusDot status={uc.readiness[s.id]} size={6} /> {window.RPA_STATUS[uc.readiness[s.id]].label}
                  </span>
                </div>
                <NodeViz stage={s.id} uc={uc} />
              </div>
            ))}
          </div>
          <div style={{ borderRadius: 12, padding: "14px 16px", background: "color-mix(in oklab, var(--c-amber) 9%, transparent)", border: "1px solid color-mix(in oklab, var(--c-amber) 26%, transparent)", display: "flex", alignItems: "center", gap: 11 }}>
            <Icon name="zap" size={17} style={{ color: "var(--c-amber)" }} />
            <div style={{ flex: 1 }}>
              <div style={{ fontSize: 12.5, fontWeight: 600, color: "var(--fg)" }}>Sprint tracker is generating</div>
              <div style={{ fontSize: 11.5, color: "var(--muted-fg)" }}>Sonnet is decomposing the process into features — about 20s remaining.</div>
            </div>
            <Btn variant="subtle" size="sm">View</Btn>
          </div>
        </div>

        {/* agent rail */}
        <div style={{ borderLeft: "1px solid var(--border)", padding: 16, overflow: "hidden", display: "flex", flexDirection: "column", gap: 12, background: "var(--sidebar)" }}>
          <AgentFeed log={window.RPA_AGENT_LOG} title="Orchestrator" height={520} compact />
        </div>
      </div>
    </AppShell>
  );
}

Object.assign(window, { HubRail, HubMatrix, HubCommand });
