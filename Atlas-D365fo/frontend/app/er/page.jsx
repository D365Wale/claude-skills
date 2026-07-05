"use client";

import { useState } from "react";

export default function ERPage() {
  const [xml, setXml] = useState("");
  const [summary, setSummary] = useState(null);
  const [report, setReport] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function validate() {
    setBusy(true);
    setError("");
    setSummary(null);
    setReport(null);
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

  return (
    <>
      <h1>ER Config Validator</h1>
      <p className="subtitle">
        Paste an exported Electronic Reporting configuration. ATLAS checks every
        binding against the data model and lints expressions — catching at design
        time what D365 only surfaces at runtime.
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
            </div>
          ))}

          {report.format_elements.map((el) => (
            <div className="card" key={el.name}>
              <div className="card-head">
                <h3>{el.name}</h3>
                <span className="badge entity">{el.type || "element"}</span>
              </div>
              {el.bindings.length > 0 && (
                <div className="chips">
                  {el.bindings.map((b) => (
                    <span className="chip" key={b}>
                      {b}
                    </span>
                  ))}
                </div>
              )}
              {el.formulas.map((f, i) => (
                <p className="meta" key={i}>
                  ƒ {f}
                </p>
              ))}
            </div>
          ))}
        </>
      )}
    </>
  );
}
