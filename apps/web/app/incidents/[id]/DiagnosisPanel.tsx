"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { formatUtc, type Diagnosis } from "@/lib/api";

type Profile = "test" | "primary";

export function DiagnosisPanel({
  incidentId,
  diagnoses,
}: {
  incidentId: string;
  diagnoses: Diagnosis[];
}) {
  const router = useRouter();
  const [running, setRunning] = useState<Profile | null>(null);
  const [error, setError] = useState<string | null>(null);
  const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

  async function generate(profile: Profile) {
    setRunning(profile);
    setError(null);
    try {
      const response = await fetch(`${apiUrl}/api/v1/incidents/${incidentId}/diagnoses`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ profile }),
      });
      if (!response.ok) {
        const body = (await response.json().catch(() => null)) as { detail?: string } | null;
        throw new Error(body?.detail ?? `Diagnosis failed with HTTP ${response.status}`);
      }
      router.refresh();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to generate diagnosis");
    } finally {
      setRunning(null);
    }
  }

  const newestFirst = [...diagnoses].reverse();

  return (
    <section className="diagnosis-section" aria-labelledby="diagnosis-heading">
      <div className="section-heading diagnosis-heading">
        <div>
          <p className="eyebrow">Evidence-bound AI</p>
          <h2 id="diagnosis-heading">Groq diagnosis</h2>
          <p>Every claim is schema-validated and limited to evidence stored on this incident.</p>
        </div>
        <div className="diagnosis-actions">
          <button disabled={running !== null} onClick={() => generate("test")} type="button">
            {running === "test" ? "Analyzing…" : "Test with 20B"}
          </button>
          <button className="primary" disabled={running !== null} onClick={() => generate("primary")} type="button">
            {running === "primary" ? "Analyzing…" : "Analyze with 120B"}
          </button>
        </div>
      </div>
      {error && <p className="diagnosis-error" role="alert">{error}</p>}
      {newestFirst.length === 0 ? (
        <div className="empty-state">
          <h3>No diagnosis generated</h3>
          <p>Start with GPT-OSS 20B to validate the evidence package and response contract.</p>
        </div>
      ) : (
        <div className="diagnosis-list">
          {newestFirst.map((diagnosis) => {
            const result = diagnosis.response_payload;
            return (
              <article className="diagnosis-card" key={diagnosis.id}>
                <div className="diagnosis-meta">
                  <span className={`diagnosis-status diagnosis-status-${diagnosis.status}`}>{diagnosis.status.replaceAll("_", " ")}</span>
                  <code>{diagnosis.model}</code>
                  <span>{formatUtc(diagnosis.created_at)} UTC</span>
                </div>
                {diagnosis.status === "completed" && result ? (
                  <>
                    <h3>{result.summary}</h3>
                    <div className="diagnosis-body">
                      <div>
                        <small>Probable cause</small>
                        <p>{result.probable_cause?.statement ?? "The supplied evidence was insufficient for a probable cause."}</p>
                      </div>
                      <div>
                        <small>Recommended action</small>
                        <p>{result.recommended_action.type.replaceAll("_", " ")}</p>
                      </div>
                    </div>
                    <div className="diagnosis-footer">
                      <span>Confidence {diagnosis.confidence == null ? "—" : `${Math.round(diagnosis.confidence * 100)}%`}</span>
                      <span>{diagnosis.cited_evidence_ids.length} evidence references</span>
                      <span>{diagnosis.latency_ms == null ? "—" : `${diagnosis.latency_ms} ms`}</span>
                      <span>{(diagnosis.input_tokens ?? 0) + (diagnosis.output_tokens ?? 0)} tokens</span>
                      <strong>Human review required</strong>
                    </div>
                  </>
                ) : (
                  <p className="diagnosis-error">{diagnosis.error_message ?? "Diagnosis is pending."}</p>
                )}
              </article>
            );
          })}
        </div>
      )}
    </section>
  );
}
