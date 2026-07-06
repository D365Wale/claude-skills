"use client";

import { useState } from "react";

export default function ERPage() {
  const [xml, setXml] = useState("");
  const [summary, setSummary] = useState(null);
  const [report, setReport] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [fieldQuery, setFieldQuery] = useState("");
  const [bindingHits, setBindingHits] = useState(null);
  const [formulaQuery, setFormulaQuery] = useState("");
  const [formulaHits, setFormulaHits] = useState(null);

  async function validate() {
    setBusy(true);
    setError("");
    setSummary(null);
    setReport(null);
    setBindingHits(null);
    try {
      const ing = await fetch("/atlas/er/ingest", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ er_xml: xml }),
      });
      if (!ing.ok) throw new Error((await ing.json()).detail || ing.statusText);
      setSummary(await ing.json());

      const rep = await fetch("/atlas/er/report");
      if (!rep.ok) throw new Error((await rep.json()).detail || rep.statusText);
      setReport(await rep.json());
    } catch (e) {
      setError(String(e.message || e));
    } finally {
      setBusy(false);
    }
  }

  async function suggestBinding() {
    setError("");
    try {
      const resp = await fetch(
        `/atlas/er/suggest?field=${encodeURIComponent(fieldQuery)}&top_k=3`
      );
      if (!resp.ok) throw new Error((await resp.json()).detail || resp.statusText);
      setBindingHits((await resp.json()).suggestions);
    } catch (e) {
      setError(String(e.message || e));
    }
  }

  async function searchFormulas() {
    setError("");
    try {
      const resp = await fetch(
        `/atlas/er/formulas?q=${encodeURIComponent(formulaQuery)}&top_k=3`
      );
      if (!resp.ok) throw new Error((await resp.json()).detail || resp.statusText);
      setFormulaHits((await resp.json()).patterns);
    } catch (e) {
      setError(String(e.message || e));
    }
  }

  return (
    <>
      <h1>ER Config Validator + Assist</h1>
      <p className="subtitle">
        Paste an exported Electronic Reporting configuration. ATLAS validates every
        binding and expression, suggests fixes, and helps you find the right data
        source path — at design time, not runtime.
      </p>

      <label className="field">Exported ER configuration XML</label>
      <textarea
        placeholder="<ERConfiguration ...>"
        value={xml}
        onChange={(e) => setXml(e.target.value)}
      />

      <div className="row">
        <button onClick={validate} disabled={busy || !xml.trim()}>
          Validate config
        </button>
      </div>

      {error && <p className="error">{error}</p>}

      {summary && report && (
        <>
          <p className={report.errors > 0 ? "error" : "ok"}>
            {summary.name} ({summary.type}) — {summary.model_nodes} model nodes,{" "}
            {summary.format_elements} format elements · {report.errors} error(s),{" "}
            {report.warnings} warning(s)
          </p>

          {report.findings.map((f, i) => (
            <div className="card" key={i}>
              <div className="card-head">
                <h3>{f.location}</h3>
                <span className={`badge ${f.severity === "error" ? "enum" : "action"}`}>
                  {f.severity}
                </span>
                <span className="score">{f.kind}</span>
              </div>
              <p className="meta">{f.detail}</p>
              {f.suggestion && <p className="ok">💡 {f.suggestion}</p>}
            </div>
          ))}

          <div className="card">
            <div className="card-head">
              <h3>Suggest a binding</h3>
              <span className="badge action">assist</span>
            </div>
            <p className="meta">
              Describe the field in plain language — ATLAS ranks the model paths.
            </p>
            <div className="row">
              <input
                type="text"
                placeholder='e.g. "creditor account number"'
                value={fieldQuery}
                onChange={(e) => setFieldQuery(e.target.value)}
              />
              <button
                className="secondary"
                onClick={suggestBinding}
                disabled={!fieldQuery.trim()}
              >
                Suggest
              </button>
            </div>
            {bindingHits && (
              <div className="chips">
                {bindingHits.map((h) => (
                  <span className="chip" key={h.path}>
                    {h.path} · {h.score}
                  </span>
                ))}
              </div>
            )}
          </div>

          <div className="card">
            <div className="card-head">
              <h3>Model tree</h3>
              <span className="badge entity">data model</span>
            </div>
            {report.model_paths.map((p) => {
              const depth = p.split(".").length - 2;
              return (
                <p className="meta" key={p} style={{ paddingLeft: `${depth * 18}px` }}>
                  {depth > 0 ? "└ " : ""}
                  {p.split(".").pop()}{" "}
                  <span className="score">{p}</span>
                </p>
              );
            })}
          </div>
        </>
      )}

      <div className="card">
        <div className="card-head">
          <h3>Formula library</h3>
          <span className="badge action">assist</span>
        </div>
        <p className="meta">Search common GER expression patterns by intent.</p>
        <div className="row">
          <input
            type="text"
            placeholder='e.g. "format a date" / "sum line amounts"'
            value={formulaQuery}
            onChange={(e) => setFormulaQuery(e.target.value)}
          />
          <button
            className="secondary"
            onClick={searchFormulas}
            disabled={!formulaQuery.trim()}
          >
            Search
          </button>
        </div>
        {formulaHits &&
          formulaHits.map((f) => (
            <div key={f.pattern}>
              <p className="meta">{f.intent}</p>
              <pre className="code">{f.pattern}</pre>
            </div>
          ))}
      </div>
    </>
  );
}
