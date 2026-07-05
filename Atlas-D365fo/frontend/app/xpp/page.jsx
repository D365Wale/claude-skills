"use client";

import { useState } from "react";

function download(filename, obj) {
  const blob = new Blob([JSON.stringify(obj, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

export default function XppPage() {
  const [group, setGroup] = useState("");
  const [source, setSource] = useState("");
  const [parsed, setParsed] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function ingest() {
    setBusy(true);
    setError("");
    setParsed(null);
    try {
      const resp = await fetch("/atlas/xpp/ingest", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ service_group: group, sources: [source] }),
      });
      if (!resp.ok) throw new Error((await resp.json()).detail || resp.statusText);
      setParsed(await resp.json());
    } catch (e) {
      setError(String(e.message || e));
    } finally {
      setBusy(false);
    }
  }

  async function exportSpec(path, filename) {
    setError("");
    try {
      const resp = await fetch(`/atlas${path}`);
      if (!resp.ok) throw new Error((await resp.json()).detail || resp.statusText);
      download(filename, await resp.json());
    } catch (e) {
      setError(String(e.message || e));
    }
  }

  return (
    <>
      <h1>X++ Service Catalog</h1>
      <p className="subtitle">
        Paste raw X++ source — no Visual Studio or AOT access needed. ATLAS extracts
        data contracts and service operations, then exports the documentation D365
        never generates.
      </p>

      <label className="field">Service group name (from AOT registration)</label>
      <input
        type="text"
        placeholder="e.g. HERJournalServiceGroup"
        value={group}
        onChange={(e) => setGroup(e.target.value)}
      />

      <label className="field">
        X++ source ([DataContractAttribute] classes + service class)
      </label>
      <textarea
        placeholder="[DataContractAttribute]&#10;public class MyRequestContract&#10;{ ... }"
        value={source}
        onChange={(e) => setSource(e.target.value)}
      />

      <div className="row">
        <button onClick={ingest} disabled={busy || !group.trim() || !source.trim()}>
          Parse X++
        </button>
        {parsed && (
          <>
            <button
              className="secondary"
              onClick={() => exportSpec("/xpp/openapi", `${group}-openapi.json`)}
            >
              Download OpenAPI 3.0
            </button>
            <button
              className="secondary"
              onClick={() => exportSpec("/xpp/postman", `${group}-postman.json`)}
            >
              Download Postman collection
            </button>
          </>
        )}
      </div>

      {error && <p className="error">{error}</p>}

      {parsed && (
        <>
          <p className="ok">
            Parsed {Object.keys(parsed.services).length} service(s),{" "}
            {Object.keys(parsed.contracts).length} contract(s).
          </p>
          {Object.entries(parsed.services).map(([svc, ops]) => (
            <div className="card" key={svc}>
              <div className="card-head">
                <h3>{svc}</h3>
                <span className="badge action">service</span>
              </div>
              <div className="chips">
                {ops.map((op) => (
                  <span className="chip" key={op}>
                    POST /api/services/{group}/{svc}/{op}
                  </span>
                ))}
              </div>
            </div>
          ))}
          {Object.entries(parsed.contracts).map(([name, members]) => (
            <div className="card" key={name}>
              <div className="card-head">
                <h3>{name}</h3>
                <span className="badge entity">contract</span>
              </div>
              <div className="chips">
                {members.map((m) => (
                  <span className="chip" key={m}>
                    {m}
                  </span>
                ))}
              </div>
            </div>
          ))}
        </>
      )}
    </>
  );
}
