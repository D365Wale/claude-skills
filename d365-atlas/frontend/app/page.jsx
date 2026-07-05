"use client";

import { useCallback, useEffect, useState } from "react";

export default function SearchPage() {
  const [health, setHealth] = useState(null);
  const [query, setQuery] = useState("");
  const [results, setResults] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [generated, setGenerated] = useState(null); // {target, code}

  const refreshHealth = useCallback(async () => {
    try {
      const resp = await fetch("/atlas/health");
      setHealth(await resp.json());
    } catch {
      setHealth(null);
    }
  }, []);

  useEffect(() => {
    refreshHealth();
  }, [refreshHealth]);

  async function loadSample() {
    setBusy(true);
    setError("");
    try {
      const xml = await (await fetch("/sample_edmx.xml")).text();
      const resp = await fetch("/atlas/ingest", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ edmx_xml: xml }),
      });
      if (!resp.ok) throw new Error((await resp.json()).detail || resp.statusText);
      await refreshHealth();
    } catch (e) {
      setError(String(e.message || e));
    } finally {
      setBusy(false);
    }
  }

  async function runSearch(e) {
    e?.preventDefault();
    if (!query.trim()) return;
    setBusy(true);
    setError("");
    setGenerated(null);
    try {
      const resp = await fetch(`/atlas/search?q=${encodeURIComponent(query)}&top_k=6`);
      if (!resp.ok) throw new Error((await resp.json()).detail || resp.statusText);
      setResults((await resp.json()).results);
    } catch (e) {
      setError(String(e.message || e));
    } finally {
      setBusy(false);
    }
  }

  async function generateClient(entityName) {
    setBusy(true);
    setError("");
    try {
      const resp = await fetch("/atlas/generate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ entity_name: entityName }),
      });
      if (!resp.ok) throw new Error((await resp.json()).detail || resp.statusText);
      setGenerated(await resp.json());
    } catch (e) {
      setError(String(e.message || e));
    } finally {
      setBusy(false);
    }
  }

  const docs = health?.documents ?? 0;

  return (
    <>
      <h1>Metadata Search</h1>
      <p className="subtitle">
        Semantic search over D365 F&O entities, enums, and service actions.
      </p>

      {docs === 0 && (
        <div className="notice">
          <p>
            No metadata ingested yet. Load the bundled sample (realistic D365 entity
            shapes) or connect a live environment via <code>D365_*</code> env vars on
            the backend.
          </p>
          <div className="row">
            <button onClick={loadSample} disabled={busy}>
              Load sample metadata
            </button>
          </div>
        </div>
      )}

      <form className="searchbar" onSubmit={runSearch}>
        <input
          type="text"
          placeholder='e.g. "service that posts journal entries"'
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
        <button type="submit" disabled={busy || docs === 0}>
          Search
        </button>
      </form>

      {error && <p className="error">{error}</p>}
      {health && (
        <p className="meta">
          {docs} documents indexed · embedder {health.embedder} · store {health.store}
        </p>
      )}

      {results?.map((r) => (
        <div className="card" key={`${r.kind}:${r.name}`}>
          <div className="card-head">
            <h3>{r.name}</h3>
            <span className={`badge ${r.kind}`}>{r.kind}</span>
            <span className="score">score {r.score}</span>
          </div>
          {r.entity_set && <p className="meta">OData set: /data/{r.entity_set}</p>}
          {r.keys.length > 0 && <p className="meta">Keys: {r.keys.join(", ")}</p>}
          {r.kind === "entity" && <p className="meta">{r.field_count} fields</p>}
          {Object.keys(r.members).length > 0 && (
            <div className="chips">
              {Object.entries(r.members).map(([name, value]) => (
                <span className="chip" key={name}>
                  {name} = {value}
                </span>
              ))}
            </div>
          )}
          {r.kind === "entity" && (
            <div className="row">
              <button
                className="secondary"
                onClick={() => generateClient(r.name)}
                disabled={busy}
              >
                Generate Python client
              </button>
            </div>
          )}
        </div>
      ))}

      {generated && (
        <div className="card">
          <div className="card-head">
            <h3>Generated client — {generated.target}</h3>
          </div>
          <pre className="code">{generated.code}</pre>
        </div>
      )}
    </>
  );
}
