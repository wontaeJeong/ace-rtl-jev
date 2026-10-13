#!/usr/bin/env python3
"""Offline reports for the bounded judgment audit and actual one-case E2E."""
import argparse
import csv
import json
from html import escape
from pathlib import Path

from experiment_reports import batch_metrics,load_batch,render_html,render_markdown,compare
from report_localization import localize_report_html,localize_report_markdown


def audit_metrics(data: dict, events: list[dict] | None=None) -> dict:
    rows=data['results'];manifest=data['manifest']
    complete=manifest.get('state')=='audit_completed' and len(rows)==manifest['selected_count']
    valid=[r for r in rows if r.get('status')=='ok']
    accepted=[r for r in valid if r.get('decision_accepted')]
    historical=sum(r['historical_primary_tokens'] for r in rows)
    historical_accepted=sum(r['historical_primary_tokens'] for r in accepted)
    accepted_tokens=sum(r['jev_usage']['total_tokens'] for r in accepted if r['jev_usage']['source']=='reported')
    if events is None:
        usages=[r.get('jev_usage') for r in valid];actual=sum(u['total_tokens'] for u in usages if u and u['source']=='reported')
        unknown=len(rows)-len(valid)+sum(u is None or u['source']!='reported' for u in usages)
        usd=sum(u.get('provider_cost',0) or 0 for u in usages if u and u.get('cost_currency')=='USD')
    else:
        usages=[e.get('usage') for e in events if e.get('provider')=='jev']
        actual=sum(u['total_tokens'] for u in usages if u and u['source']=='reported')
        unknown=sum(u is None or u['source']!='reported' for u in usages)
        usd=sum(u.get('provider_cost',0) or 0 for u in usages if u and u.get('cost_currency')=='USD')
    fallback=[r for r in rows if r.get('would_fallback') or r.get('status')!='ok']
    proxies=[r['primary_proxy_agreement'] for r in valid if r.get('primary_proxy_agreement') is not None]
    oracle=[r['all_pass_oracle_agreement'] for r in valid if r.get('all_pass_oracle_agreement') is not None]
    reduction=((historical_accepted-accepted_tokens)/historical_accepted*100 if complete and historical_accepted and all(r['jev_usage']['source']=='reported' for r in accepted) else None)
    return {'complete':complete,'selected_count':manifest['selected_count'],'executed_count':len(rows),'valid_decisions':len(valid),'decision_errors':len(rows)-len(valid),
            'accepted_decisions':len(accepted),'would_fallback_count':len(fallback),'actual_primary_fallback_calls':sum(r.get('actual_primary_fallback_calls',0) for r in rows),
            'accepted_already_all_pass_count':sum(r.get('official_evaluator_passed') is True for r in accepted),
            'historical_primary_tokens':historical,'actual_jev_tokens':actual,'unknown_jev_usage_calls':unknown,'actual_jev_usd_known':usd,
            'accepted_historical_primary_tokens':historical_accepted,'accepted_actual_jev_tokens':accepted_tokens,
            'accepted_point_token_reduction_percent':reduction,
            'hypothetical_tokens_with_historical_fallback':actual+sum(r['historical_primary_tokens'] for r in fallback) if complete and not unknown else None,
            'primary_proxy_labeled_count':len(proxies),'primary_proxy_agree_count':sum(proxies),'primary_proxy_agreement_rate':sum(proxies)/len(proxies) if proxies else None,
            'all_pass_oracle_count':len(oracle),'all_pass_resolved_count':sum(oracle),'all_pass_resolved_rate':sum(oracle)/len(oracle) if oracle else None}


def generate(study_dir: Path, output: Path) -> dict:
    study=json.loads((study_dir/'study.json').read_text());audit=json.loads((study_dir/'audit.json').read_text())
    events=[json.loads(p.read_text()) for p in (study_dir/'audit-calls').glob('*.json')]
    metrics=audit_metrics(audit,events)
    baseline=load_batch(Path(study['baseline_projection'])) if study.get('baseline_projection') else None
    improved=load_batch(Path(study['e2e_batch'])) if study.get('e2e_batch') else None
    payload={'audit':metrics,'campaign_budget':study['budget'],'baseline_e2e':batch_metrics(baseline) if baseline else None,
             'jev_e2e':batch_metrics(improved) if improved else None,'e2e_changes':compare(baseline,improved) if baseline else None,
             'full_292_case_jev_evaluation':'NOT RUN','repetitions_ablation':'NOT RUN'}
    eb,ej=payload['baseline_e2e'],payload['jev_e2e']
    token_change=((ej['total_tokens']-eb['total_tokens'])/eb['total_tokens']*100 if eb and ej and eb['total_tokens'] and ej['total_tokens'] is not None else None)
    observed=(f"실측 case 토큰 {eb['total_tokens']} → {ej['total_tokens']} ({token_change:+.2f}%), 평균 case 시간 {eb['average_case_seconds']:.3f} → {ej['average_case_seconds']:.3f} s. 실제 primary fallback {ej['primary']['fallback_calls']}회."
              if eb and ej and token_change is not None and eb['average_case_seconds'] is not None and ej['average_case_seconds'] is not None else '완전한 E2E 비용/시간 비교를 만들 수 없다.')
    output.mkdir(parents=True,exist_ok=True)
    (output/'metrics.json').write_text(json.dumps(payload,indent=2))
    lines=['# ACE-RTL JEV-like 최종 제한 예산 검증 보고서','',
           '**범위:** 기존 292-case Baseline 재사용, 판단 지점 48개 + 실제 CVDP 1개 E2E. 전체 292개 개선 버전 평가는 실행하지 않았다.',
           '**결과를 구분한다:** 판단 API 비용 실험은 전체 RTL 성공률 실험이 아니다. 1-case 결과는 일반화·통계적 우위를 입증하지 않는다.','',
           '**핵심 결론:** 소규모 실측은 전체 JEV 기본 적용의 개선을 입증하지 않는다. '+observed+' 원래 batch 동시 실행 조건이 달라 시간 차이를 통제된 속도 차이로 해석하지 않는다.',
            f"판단 감사는 {metrics['executed_count']}회 중 {metrics['valid_decisions']}개 schema-valid /{metrics['decision_errors']}개 decision error, 수용 {metrics['accepted_decisions']}개 /would-fallback {metrics['would_fallback_count']}개였다. 옛 primary 문장 휴리스틱과 {metrics['primary_proxy_labeled_count']}개 중 {metrics['primary_proxy_agree_count']}개 일치(ground truth 아님), 공식 all-pass {metrics['all_pass_oracle_count']}개 중 {metrics['all_pass_resolved_count']}개 resolved였다. 수용 부분집합 토큰 감소만으로 전체 최적화를 주장하지 않는다.",
            f"수용 판단 {metrics['accepted_decisions']}개 중 {metrics['accepted_already_all_pass_count']}개는 이미 공식 evaluator가 all-pass인 상태였다. 따라서 단순히 성공을 확인하는 데 모델을 쓰지 않는 결정적 terminal 처리부터 오프라인 검토할 가치가 있다. 해당 개선은 이번에 구현/추가 실험하지 않았으며 절감을 실제 성과로 계산하지 않는다.",
           '따라서 baseline을 기본으로 유지하고 JEV 경로를 실험적 opt-in으로 둔다. 남은 예산을 이유로 재시도·추가 cohort를 실행하지 않았다.','',
           '## 1. 판단 지점 실측','', '| 항목 | 결과 |','|---|---:|']
    for key in ('selected_count','executed_count','valid_decisions','decision_errors','accepted_decisions','would_fallback_count','historical_primary_tokens','actual_jev_tokens','actual_jev_usd_known','unknown_jev_usage_calls','accepted_point_token_reduction_percent','primary_proxy_labeled_count','primary_proxy_agree_count','all_pass_oracle_count','all_pass_resolved_count'):
        lines.append(f'| {key} | {metrics[key]} |')
    lines+=['','각 snapshot의 원래 주력 LLM 요청을 생성 후보·실제 emitted 보고서·role metadata로 재구성하고 원본 API event SHA256의 정확한 일치를 요구했다. 원본 판단 토큰은 과거 실제 측정이며 새 주력 호출로 재측정하지 않았다.',
            'JEV는 bounded state와 finite-label 출력만 사용한다. 기존 주력 LLM의 풍부한 변경 분석/설명과 정보량이 같지 않으므로 토큰 감소에는 정확도·정보 손실 trade-off가 있다.',
            'accepted_point_token_reduction_percent는 **확신 기준을 통과한 판단 부분집합만의** 원본 기록 대비 실제 JEV 토큰 감소이며 전체 agent 절감률이 아니다. 실패·불확실 판단의 실제 JEV 비용은 모두 포함했다.',
            'primary_proxy_agreement는 추출한 옛 primary 문장과의 휴리스틱 일치이며 ground truth가 아니다. all-pass subset에서는 공식 evaluator가 통과한 경우 resolved인지 제한적으로 확인했다.',
            '감사 단계에서는 추가 주력 fallback을 구매하지 않았다. would-fallback과 actual fallback을 혼동하지 않는다. 다음 값은 실제 지출이 아닌 **원본 fallback 토큰을 재사용한 시나리오 추정**이다:',
            f"`hypothetical_tokens_with_historical_fallback = {metrics['hypothetical_tokens_with_historical_fallback']}`.",
            '', '## 2. 실제 CVDP E2E','']
    if baseline and improved:lines.append(render_markdown(baseline,improved))
    else:lines.append('실행/수집 미완료. 성공이나 절감을 가정하지 않는다.')
    lines+=['','## 3. 비용 제어와 원본 보존','',
            '주력 API 12회/예약 300,000 tokens, JEV 64회/예약 1,000,000 tokens/USD 0.10 노출 한도. 공유 SQLite가 warmup·재시도·실제 fallback까지 포함한다. redirect 재전송을 차단하고, token 정보 없는 실패도 예약을 유지하며, 답변이 잘못돼도 유효한 USD 영수증은 정산한다.',
            '입력 UTF-8 bytes + wrapper/output allowance 예약은 opaque provider의 절대 요금 보증이 아니다. 주력 가격 API는 model ID만 제공하여 정확한 주력 USD와 전체 비용을 만들지 않았다. JEV receipt USD는 OpenRouter 공식 문서로 확인했다. 서버측 credit cap이 필요하면 운영자가 설정해야 한다.',
            'Baseline은 다시 실행하지 않았다. 292-case clean baseline은 239 success / 52 failure / 1 timeout, 4,367.250 s, 알려진 16,538,281 tokens +33 usage-unknown calls로 보존돼 있다.',
            '', '## 4. 해석·한계·후속 방향','',
            '1-case E2E에서 토큰이 늘거나 지연이 증가하면 그대로 보고한다. 원래 292-case batch와 달리 새로운 한 케이스만 실행했으므로 historical per-case 시간 차이를 통제된 batch speedup으로 주장하지 않는다.',
            '판단 실패/낮은 confidence/낮은 proxy agreement가 많으면 원래 주력 경로를 유지하는 것이 합리적이다. 코드 생성과 깊은 수정 추론은 대체하지 않았다. 비용이 남았다는 이유로 추가 실험을 임의로 확대하지 않는다.',
            '추가 설계: 목표 오류 식별과 report compaction 품질을 먼저 오프라인 보완하고, 더 큰 paired cohort/반복/ablation은 별도 예산을 정한 뒤 수행한다. 현재 그런 실험은 NOT RUN이다.',
            '', '## 5. 재현 경로','',f'- Study: `{study_dir}`',f"- Actual E2E: `{study.get('e2e_batch','not run')}`",'- CLI / 설정: `docs/experiments/jev-guide.md`','- 원본 JSON/CSV/API events와 budget JSON snapshots는 저장소에, private harness/입력과 SQLite binary는 로컬 ignored 영역에 유지한다.','']
    text=localize_report_markdown('\n'.join(lines));(output/'final-report.md').write_text(text,encoding='utf-8')
    audit_table=''.join('<tr><th>'+escape(localize_report_markdown(k))+'</th><td>'+escape(str(v))+'</td></tr>' for k,v in metrics.items())
    e2e_html=render_html(baseline,improved) if baseline and improved else '<p>Actual E2E not complete.</p>'
    # Embed existing escaped report body, not untrusted raw markup/data.
    if '<main>' in e2e_html:e2e_html=e2e_html.split('<main>',1)[1].split('</main>',1)[0]
    html='''<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>ACE-RTL JEV budgeted evaluation</title><style>body{font:15px system-ui;background:#f3f6fb;color:#17243c;margin:0}main{max-width:1200px;margin:auto;padding:32px}section,.card{background:white;padding:20px;border:1px solid #dfe6f1;border-radius:12px;margin:16px 0}.notice{background:#fff4d6;padding:18px;border-left:4px solid #b78500}table{border-collapse:collapse;width:100%}th,td{text-align:left;padding:9px;border-bottom:1px solid #e5eaf2}pre{white-space:pre-wrap;overflow-wrap:anywhere}.cards{display:flex;gap:12px;flex-wrap:wrap}.card b{display:block;font-size:23px}.scroll{overflow:auto}</style></head><body><main><h1>JEV-like 제한 예산 검증</h1><p class="notice">판단 지점 48개 + 실제 CVDP 1개. 전체 292-case JEV, 반복, ablation은 NOT RUN. 부분집합 토큰 절감을 전체 효과로 일반화하지 않으며 미확인 비용은 0으로 처리하지 않는다.</p><section><h2>판단 지점 실측</h2><table>'''+audit_table+'''</table></section>'''+e2e_html+'''<details><summary>전체 보고서 / 방법 / 한계</summary><pre>'''+escape(text)+'''</pre></details></main></body></html>'''
    html=html.replace('<h1>JEV-like 제한 예산 검증</h1>',
                      '<h1>JEV-like 제한 예산 검증</h1><p class="notice"><strong>Baseline 기본 유지 · JEV는 실험적 opt-in</strong><br>'+escape(observed)+'</p>')
    (output/'final-report.html').write_text(localize_report_html(html),encoding='utf-8')
    with (output/'judgments.csv').open('w',newline='') as f:
        fields=['snapshot_id','case_id','category','iteration','status','historical_primary_tokens','jev_tokens','jev_choice','confidence','decision_accepted','would_fallback','primary_proxy_agreement']
        writer=csv.DictWriter(f,fieldnames=fields,lineterminator='\n');writer.writeheader()
        for r in audit['results']:
            row={k:r.get(k) for k in fields};row.update(jev_tokens=(r.get('jev_usage') or {}).get('total_tokens'),jev_choice=(r.get('jev_answer') or {}).get('choice'),confidence=(r.get('jev_answer') or {}).get('confidence'))
            writer.writerow(row)
    return payload


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--study',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();result=generate(args.study,args.output);print(json.dumps(result,indent=2))
