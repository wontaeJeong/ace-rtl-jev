# Completed clean baseline — not a JEV optimization result

Batch: `baseline-20261011T103810Z-97717`.

| Measurement | Observed value |
|---|---:|
| Evaluated eligible CVDP cases | 292 / 292 |
| Success | 239 |
| Candidate failure | 52 |
| Native service timeout | 1 |
| Success rate | 81.8493% |
| Batch wall time, excluding warmup | 4,367.250 s (72 min 47 s) |
| Mean individual case runtime | 109.631 s |
| Sum of individual case runtimes | 32,012.218 s |
| Primary API calls, including retries/errors | 1,311 |
| Reported prompt tokens | 14,235,838 |
| Reported completion tokens | 2,302,443 |
| Known reported token subtotal | 16,538,281 |
| Calls with unavailable token usage | 33 |
| Mean API call latency, including failed calls | 17.161 s |
| Cases with missing whole-case runtime | 0 |
| Watcher orphan-cleanup events | 0 |
| JEV evaluation calls | 0 |

The known token subtotal is **not** the complete billed total: 33 failed requests have no provider usage. No zero-cost assumption or token/time-saving claim is made. Primary currency cost is unavailable without verified provider prices/billing. Warmup is stored separately and still costs tokens; exclusion from evaluation is not exclusion from financial accounting.

Case runtimes overlap with eight concurrent workers; their sum is not batch wall time. Conditions: one attempt, up to five iterations; request timeout 60 s, LLM subprocess 90 s, evaluator service 300 s, whole case 1,800 s. Actual native evaluator pass is the only success criterion. All 292 case records and before/after timers are preserved.

The first original-flow cohort (four workers, before portable lifecycle fixes) is independently retained: 240 success / 46 failure / 6 timeout and 16,470,984 known tokens with 26 unavailable-usage calls. Its batch/one-case times are unavailable. The two baseline cohorts have different concurrency/lifecycle conditions and cannot demonstrate JEV gains. Their known token subtotals sum to 33,009,265, excluding separately stored warmups/smokes and unavailable usage; this is not a complete project bill.

Files: `comparison.md` (baseline table; improved mode explicitly **Not run**), `metrics.json`, `cases.csv`. Raw evidence: `experiments/runs/baseline-20261011T103810Z-97717/`; durable driver logs: `experiments/driver-logs/`. Native working copies remain local/Git-ignored because they embed private benchmark harness source.

**Later cost-controlled checkpoint:** design, offline checks, budget admission and counted JEV fallback were subsequently implemented/reviewed. One frozen 48-judgment/one-case E2E campaign finished; see `reports/jev-final/`. The new case passed but total tokens increased 9.33%, so JEV is not recommended as default. No full292 JEV run or extra tuning is queued. Reports now include self-contained HTML as well as Markdown/JSON/CSV.
