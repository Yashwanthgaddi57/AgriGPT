"use client";

import * as React from "react";
import { Camera, FileScan, Info, Loader2, Stethoscope } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Progress } from "@/components/ui/progress";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import {
  useAnalyzeDisease,
  useDiseaseAnalytics,
  useDiseaseReports,
  useUpdateDiseaseFollowup,
} from "@/hooks/use-api";
import { apiErrorMessage } from "@/lib/api";
import { trackEvent, EVENTS } from "@/lib/events";
import { useToast } from "@/hooks/use-toast";
import { formatDate } from "@/lib/utils";

const SEVERITY_VARIANT: Record<string, "success" | "warning" | "danger" | "destructive"> = {
  low: "success",
  medium: "warning",
  high: "danger",
  critical: "destructive",
};

const STATUS_OPTIONS = ["open", "monitoring", "treated", "resolved"] as const;
const STATUS_VARIANT: Record<string, "warning" | "secondary" | "success" | "outline"> = {
  open: "warning",
  monitoring: "secondary",
  treated: "success",
  resolved: "outline",
};

export default function DiseasePage() {
  const [file, setFile] = React.useState<File | null>(null);
  const [preview, setPreview] = React.useState<string | null>(null);
  const [crop, setCrop] = React.useState("");
  const [page, setPage] = React.useState(1);
  const [compareIds, setCompareIds] = React.useState<string[]>([]);
  const analyze = useAnalyzeDisease();
  const { data: reports } = useDiseaseReports(page);
  const { data: analytics } = useDiseaseAnalytics();
  const updateFollowup = useUpdateDiseaseFollowup();
  const { toast } = useToast();

  const onFile = (f: File | null) => {
    setFile(f);
    if (f) setPreview(URL.createObjectURL(f));
  };

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!file || !crop) {
      toast({ title: "Missing info", description: "Pick a photo and enter the crop name." });
      return;
    }
    if (file.size > 10 * 1024 * 1024) {
      toast({
        title: "Image too large",
        description: "Your image is too large. Please upload a smaller image (max 10MB).",
        variant: "destructive",
      });
      return;
    }
    try {
      trackEvent(EVENTS.diseaseScanStarted, { crop });
      await analyze.mutateAsync({ image: file, crop });
      trackEvent(EVENTS.diseaseScanCompleted, {
        crop,
        healthy: analyze.data?.is_healthy ?? null,
      });
      toast({ title: "Analysis complete", variant: "success" });
    } catch (err) {
      toast({
        title: "Analysis failed",
        description: apiErrorMessage(err) || "Something went wrong while analyzing your crop. Please try again.",
        variant: "destructive",
      });
    }
  };

  const latest = analyze.data;
  const inconclusive = latest && latest.confidence < 40;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="font-display text-[22px] font-medium leading-tight tracking-[0.32px]">Crop Health Scan</h1>
        <p className="text-sm text-muted-foreground">
          Upload a crop photo — get possible issues with confidence levels,
          immediate actions and prevention. AI-assisted, not a diagnosis.
        </p>
      </div>

      <Tabs defaultValue="scan">
        <TabsList>
          <TabsTrigger value="scan">Scan</TabsTrigger>
          <TabsTrigger value="history">My Crop Health</TabsTrigger>
          <TabsTrigger value="analytics">Analytics</TabsTrigger>
        </TabsList>

        <TabsContent value="scan" className="mt-4 grid gap-6 lg:grid-cols-2">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-base">
                <Camera className="h-4 w-4 text-leaf-600" /> Upload crop photo
              </CardTitle>
              <CardDescription>JPEG/PNG/WebP up to 10MB. Clear, well-lit close-ups work best.</CardDescription>
            </CardHeader>
            <CardContent>
              <form onSubmit={submit} className="space-y-4">
                <div
                  className="flex cursor-pointer flex-col items-center justify-center gap-2 rounded-xl border-2 border-dashed p-8 text-center transition-colors hover:border-leaf-400 hover:bg-leaf-50"
                  onClick={() => document.getElementById("leaf-input")?.click()}
                  role="button"
                  tabIndex={0}
                  onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && document.getElementById("leaf-input")?.click()}
                  aria-label="Select a crop photo"
                >
                  {preview ? (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img src={preview} alt="Crop preview" className="max-h-48 rounded-lg object-contain" />
                  ) : (
                    <>
                      <FileScan className="h-10 w-10 text-leaf-600" />
                      <p className="text-sm font-medium">Click to select a photo</p>
                      <p className="text-xs text-muted-foreground">or drag & drop</p>
                    </>
                  )}
                </div>
                <input
                  id="leaf-input"
                  type="file"
                  accept="image/jpeg,image/png,image/webp"
                  className="hidden"
                  onChange={(e) => onFile(e.target.files?.[0] ?? null)}
                />
                <div className="space-y-2">
                  <Label>Crop name</Label>
                  <Input
                    required
                    placeholder="e.g. cotton, tomato, wheat"
                    value={crop}
                    onChange={(e) => setCrop(e.target.value)}
                  />
                </div>
                <Button type="submit" className="w-full gap-2" disabled={analyze.isPending}>
                  {analyze.isPending ? (
                    <><Loader2 className="h-4 w-4 animate-spin" /> Analyzing image…</>
                  ) : (
                    <>Analyze crop health</>
                  )}
                </Button>
              </form>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-base">Analysis</CardTitle>
              <CardDescription>AI assessment — verify with a local expert before treatment</CardDescription>
            </CardHeader>
            <CardContent>
              {!latest && !analyze.isPending && (
                <p className="py-8 text-center text-sm text-muted-foreground">
                  Results appear here after your first scan.
                </p>
              )}
              {analyze.isPending && (
                <div className="space-y-3 py-4">
                  <SkeletonLine />
                  <SkeletonLine />
                  <SkeletonLine />
                </div>
              )}
              {latest && (
                <div className="space-y-4">
                  {/* Inconclusive state */}
                  {inconclusive ? (
                    <div className="rounded-xl border border-amber-500/30 bg-amber-50 p-4">
                      <p className="flex items-center gap-2 font-medium text-amber-700 dark:text-amber-600">
                        <Info className="h-4 w-4" /> Inconclusive image
                      </p>
                      <p className="mt-1 text-sm text-muted-foreground">
                        The image is inconclusive. Please upload a clearer,
                        well-lit close-up of the affected leaves, or consult an
                        agronomist for an on-site assessment.
                      </p>
                    </div>
                  ) : (
                    <div className="flex items-center justify-between">
                      <div>
                        <p className="text-xs uppercase tracking-wide text-muted-foreground">Possible issue</p>
                        <h3 className="text-lg font-bold">{latest.disease_name}</h3>
                      </div>
                      <Badge variant={latest.is_healthy ? "success" : SEVERITY_VARIANT[latest.severity] ?? "warning"}>
                        {latest.is_healthy ? "Healthy" : `${latest.severity} severity`}
                      </Badge>
                    </div>
                  )}

                  <div className="grid grid-cols-2 gap-3 text-sm">
                    <div>
                      <p className="text-muted-foreground">Crop</p>
                      <p className="font-medium capitalize">{latest.crop}</p>
                    </div>
                    <div>
                      <p className="text-muted-foreground">Confidence</p>
                      <p className="font-medium">{latest.confidence.toFixed(1)}%</p>
                    </div>
                  </div>

                  <div>
                    <div className="mb-1 flex justify-between text-xs text-muted-foreground">
                      <span>Severity score</span><span>{latest.severity_score.toFixed(0)}/100</span>
                    </div>
                    <Progress value={latest.severity_score} />
                  </div>

                  {!inconclusive && (
                    <p className="rounded-lg bg-muted p-3 text-xs text-muted-foreground">
                      This is an AI-assisted possibility, not a certain
                      diagnosis. Similar symptoms can have other causes — see
                      below. Confirm with your local agriculture officer before
                      purchasing or applying treatments.
                    </p>
                  )}

                  <Section title="Symptoms detected" body={latest.symptoms} />
                  <Section title="Cause" body={latest.cause} />

                  {(latest.alternatives?.length ?? 0) > 0 && (
                    <div>
                      <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                        These symptoms may also be associated with
                      </p>
                      <ul className="mt-1 list-inside list-disc text-sm text-muted-foreground">
                        {latest.alternatives!.map((a: string) => <li key={a}>{a}</li>)}
                      </ul>
                    </div>
                  )}

                  <Section title="Immediate actions" body={latest.treatment} />
                  <Section title="Prevention" body={latest.prevention} />
                  <Section title="Spread risk" body={latest.spread_risk} />

                  <p className="flex items-start gap-2 rounded-lg border border-amber-500/25 bg-amber-50 p-3 text-xs text-muted-foreground">
                    <Stethoscope className="mt-0.5 h-3.5 w-3.5 shrink-0 text-amber-600" />
                    When to seek expert help: if symptoms spread despite
                    treatment, or before any chemical treatment on a large
                    area, consult your local agriculture officer or a licensed
                    agronomist.
                  </p>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="history" className="mt-4 space-y-4">
          {(reports?.items ?? []).length === 0 ? (
            <Card><CardContent className="py-10 text-center text-sm text-muted-foreground">No scans yet.</CardContent></Card>
          ) : (
            <>
              <p className="text-xs text-muted-foreground">
                Select any two scans to compare side by side.
              </p>
              <div className="grid gap-4 md:grid-cols-2">
                {(reports?.items ?? []).map((r) => (
                  <Card
                    key={r.id}
                    className={compareIds.includes(r.id) ? "ring-1 ring-leaf-500" : ""}
                  >
                  <CardContent className="flex gap-4 pt-6">
                    <button
                      className="mt-1 self-start text-[11px] text-leaf-600 underline"
                      onClick={() =>
                        setCompareIds((prev) =>
                          prev.includes(r.id)
                            ? prev.filter((id) => id !== r.id)
                            : [...prev, r.id].slice(-2)
                        )
                      }
                      aria-pressed={compareIds.includes(r.id)}
                    >
                      {compareIds.includes(r.id) ? "✓ Selected for comparison" : "Compare"}
                    </button>
                    {r.image_url && (
                      // eslint-disable-next-line @next/next/no-img-element
                      <img src={r.image_url} alt={r.crop} className="h-20 w-20 rounded-lg object-cover" />
                    )}
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center justify-between gap-2">
                        <p className="truncate font-medium">{r.disease_name}</p>
                        <Badge variant={r.is_healthy ? "success" : SEVERITY_VARIANT[r.severity] ?? "warning"}>
                          {r.is_healthy ? "healthy" : r.severity}
                        </Badge>
                      </div>
                      <p className="text-sm capitalize text-muted-foreground">
                        {r.crop} · confidence {r.confidence.toFixed(0)}%
                      </p>
                      <p className="mt-1 line-clamp-2 text-xs text-muted-foreground">{r.treatment}</p>
                      <div className="mt-2 flex flex-wrap items-center gap-2">
                        <span className="text-xs text-muted-foreground">{formatDate(r.created_at)}</span>
                        {!r.is_healthy && (
                          <FollowupControls
                            reportId={r.id}
                            status={(r.followup_status ?? "open") as "open" | "monitoring" | "treated" | "resolved"}
                            notes={r.notes ?? ""}
                            onSave={(status, notes) =>
                              updateFollowup.mutate(
                                { reportId: r.id, followup_status: status, notes },
                                {
                                  onSuccess: () => toast({ title: "Follow-up updated", variant: "success" }),
                                  onError: (e) => toast({ title: "Update failed", description: apiErrorMessage(e), variant: "destructive" }),
                                }
                              )
                            }
                            saving={updateFollowup.isPending}
                          />
                        )}
                      </div>
                    </div>
                  </CardContent>
                </Card>
              ))}
              </div>
              {compareIds.length === 2 && (() => {
                const [a, b] = compareIds.map((id) =>
                  (reports?.items ?? []).find((r) => r.id === id)
                );
                if (!a || !b) return null;
                return (
                  <Card className="border-leaf-300">
                    <CardHeader className="pb-2">
                      <CardTitle className="text-base">Scan comparison</CardTitle>
                      <CardDescription>Side-by-side of the two selected scans</CardDescription>
                    </CardHeader>
                    <CardContent className="grid gap-4 sm:grid-cols-2">
                      {[a, b].map((r) => (
                        <div key={r.id} className="rounded-lg border p-3">
                          <p className="font-medium">{r.disease_name}</p>
                          <p className="text-sm capitalize text-muted-foreground">{r.crop} · {formatDate(r.created_at)}</p>
                          <div className="mt-2 space-y-1 text-sm">
                            <p>Confidence: {r.confidence.toFixed(0)}%</p>
                            <p>Severity: <span className="capitalize">{r.is_healthy ? "healthy" : r.severity}</span> ({r.severity_score.toFixed(0)}/100)</p>
                            <p>Status: {r.followup_status ?? (r.is_healthy ? "—" : "open")}</p>
                          </div>
                        </div>
                      ))}
                    </CardContent>
                  </Card>
                );
              })()}
            </>
          )}
          {reports && reports.total > 10 && (
            <div className="flex justify-center gap-2">
              <Button variant="outline" size="sm" disabled={page === 1} onClick={() => setPage(page - 1)}>Prev</Button>
              <Button variant="outline" size="sm" disabled={page * 10 >= reports.total} onClick={() => setPage(page + 1)}>Next</Button>
            </div>
          )}
        </TabsContent>

        <TabsContent value="analytics" className="mt-4 space-y-4">
          {!analytics ? (
            <Card><CardContent className="py-10 text-center text-sm text-muted-foreground">No analytics yet.</CardContent></Card>
          ) : (
            <>
              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
                <StatCard label="Total scans" value={String(analytics.total_reports)} />
                <StatCard label="Diseased" value={String(analytics.diseased_count)} />
                <StatCard label="Healthy" value={String(analytics.healthy_count)} />
                <StatCard label="Open issues" value={String(analytics.open_issues)} />
              </div>
              <Card>
                <CardHeader className="pb-2"><CardTitle className="text-base">Top possible issues detected</CardTitle></CardHeader>
                <CardContent className="space-y-2">
                  {analytics.top_diseases.length === 0 && <p className="text-sm text-muted-foreground">Nothing yet.</p>}
                  {analytics.top_diseases.map((d: { name: string; count: number }) => (
                    <div key={d.name} className="flex items-center gap-3">
                      <span className="w-44 truncate text-sm">{d.name}</span>
                      <div className="h-2 flex-1 rounded-full bg-muted">
                        <div
                          className="h-2 rounded-full bg-red-400"
                          style={{ width: `${(d.count / Math.max(...analytics.top_diseases.map((x: { count: number }) => x.count))) * 100}%` }}
                        />
                      </div>
                      <span className="text-sm font-medium">{d.count}</span>
                    </div>
                  ))}
                </CardContent>
              </Card>
            </>
          )}
        </TabsContent>
      </Tabs>
    </div>
  );
}

function FollowupControls({
  reportId,
  status,
  notes,
  onSave,
  saving,
}: {
  reportId: string;
  status: "open" | "monitoring" | "treated" | "resolved";
  notes: string;
  onSave: (status: "open" | "monitoring" | "treated" | "resolved", notes: string) => void;
  saving: boolean;
}) {
  const [value, setValue] = React.useState(status);
  const [noteText, setNoteText] = React.useState(notes);
  const [open, setOpen] = React.useState(false);

  return (
    <div className="w-full">
      <div className="flex items-center gap-2">
        <Badge variant={STATUS_VARIANT[value] ?? "secondary"}>{value}</Badge>
        <button
          className="text-xs text-leaf-600 underline"
          onClick={() => setOpen((v) => !v)}
          aria-expanded={open}
        >
          {open ? "Hide" : "Update"}
        </button>
      </div>
      {open && (
        <div className="mt-2 space-y-2">
          <div className="flex flex-wrap gap-1.5">
            {STATUS_OPTIONS.map((s) => (
              <button
                key={s}
                onClick={() => setValue(s)}
                className={`rounded-full border px-2.5 py-1 text-xs capitalize transition-colors ${
                  value === s ? "border border-leaf-500 bg-leaf-50 text-leaf-700" : "text-muted-foreground hover:border-leaf-300"
                }`}
              >
                {s}
              </button>
            ))}
          </div>
          <Textarea
            rows={2}
            placeholder="Notes: what did you observe or apply?"
            value={noteText}
            onChange={(e) => setNoteText(e.target.value)}
            maxLength={2000}
          />
          <Button size="sm" disabled={saving} onClick={() => onSave(value, noteText)}>
            {saving ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : "Save follow-up"}
          </Button>
        </div>
      )}
    </div>
  );
}

function Section({ title, body }: { title: string; body: string | null }) {
  if (!body) return null;
  return (
    <div>
      <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">{title}</p>
      <p className="mt-1 text-sm">{body}</p>
    </div>
  );
}

function StatCard({ label, value }: { label: string; value: string }) {
  return (
    <Card><CardContent className="pt-6">
      <p className="text-sm text-muted-foreground">{label}</p>
      <p className="font-display text-[22px] font-medium leading-tight tracking-[0.32px]">{value}</p>
    </CardContent></Card>
  );
}

function SkeletonLine() {
  return <div className="h-4 w-full animate-pulse rounded bg-muted" />;
}
