#!/usr/bin/env python3
"""Build only explicitly published reports; no dataset, prompts, logs or model calls."""
from __future__ import annotations
import argparse
import hashlib
import html
import json
import posixpath
from pathlib import Path
import re
import shutil
from urllib.parse import urlsplit
from report_localization import localize_report_markdown
from report_visuals import native_figures,baseline_figures,audit_figures,historical_comparison_figures,flow_diagram,reset_visual_ids

ROOT=Path(__file__).resolve().parents[1]
REPOSITORY='https://github.com/wontaeJeong/ace-rtl-jev'
MARKDOWN={
    'reports/jev-native-plan/final-report.md':'native/index.html',
    'docs/jev_completion_status.md':'completion/index.html',
    'docs/jev_native_runbook.md':'runbook/index.html',
    'docs/jev_integration_audit.md':'audit/index.html',
    'reports/clean-baseline/comparison.md':'historical/baseline.html',
    'reports/jev-final/final-report.md':'historical/jev.html',
    'reports/jev-comparison/comparison.md':'historical/comparison.html',
}
COPIES={
    'reports/jev-native-plan/budget-snapshot.json':'data/budget-snapshot.json',
    'reports/jev-native-plan/verified-claims.json':'data/verified-claims.json',
}
METRICS=('reports/clean-baseline/metrics.json','reports/jev-final/metrics.json','reports/jev-comparison/metrics.json')
EXPECTED_FILES=set(MARKDOWN.values())|set(COPIES.values())|{'index.html','assets/site.css','.nojekyll','publication.json'}
CSS='''
:root{color-scheme:light;--md-sys-color-primary:#365e9d;--md-sys-color-on-primary:#fff;--md-sys-color-primary-container:#d8e2ff;--md-sys-color-on-primary-container:#071c38;--md-sys-color-surface:#faf9ff;--md-sys-color-surface-container:#eeedf4;--md-sys-color-surface-container-low:#f4f3fa;--md-sys-color-on-surface:#1b1b1f;--md-sys-color-on-surface-variant:#44474f;--md-sys-color-outline-variant:#c4c6d0;--md-sys-color-error:#ba1a1a;--md-sys-color-tertiary:#006a64;--md-sys-elevation-1:0 1px 3px #1b1b1f1f,0 1px 2px #1b1b1f14;--md-sys-elevation-2:0 3px 9px #1b1b1f16;--md-sys-shape-large:28px;--md-sys-shape-medium:16px}
*{box-sizing:border-box}html{scroll-behavior:smooth;scroll-padding-top:100px}body{margin:0;background:var(--md-sys-color-surface);color:var(--md-sys-color-on-surface);font:16px/1.85 "Roboto","Noto Sans KR","Apple SD Gothic Neo",system-ui,sans-serif;word-break:keep-all;overflow-wrap:anywhere}
a{color:var(--md-sys-color-primary);text-underline-offset:4px}a:focus-visible,summary:focus-visible{outline:3px solid var(--md-sys-color-tertiary);outline-offset:4px;border-radius:8px}.skip-link{position:absolute;left:16px;top:-100px;z-index:20;background:var(--md-sys-color-primary);color:white;padding:12px}.skip-link:focus{top:8px}
.app-bar{position:sticky;top:0;z-index:10;background:#faf9fff2;backdrop-filter:blur(14px);border-bottom:1px solid #c4c6d05c;box-shadow:var(--md-sys-elevation-1)}.app-bar-inner{max-width:1460px;margin:auto;min-height:76px;padding:12px 28px;display:flex;align-items:center;justify-content:space-between;gap:18px}.brand{display:flex;gap:12px;align-items:center;text-decoration:none;font-weight:750;color:var(--md-sys-color-on-surface)}.brand-mark{width:44px;height:44px;background:var(--md-sys-color-primary-container);color:var(--md-sys-color-on-primary-container);display:grid;place-items:center;border-radius:14px;font-size:14px;letter-spacing:1px}.brand small{display:block;color:var(--md-sys-color-on-surface-variant);font-size:12px;font-weight:450}
.app-nav{display:flex;gap:8px;flex-wrap:wrap}.app-nav a{display:flex;align-items:center;justify-content:center;min-height:44px;padding:9px 16px;border-radius:24px;text-decoration:none;color:var(--md-sys-color-on-surface-variant);font-size:14px;font-weight:600}.app-nav a:hover{background:var(--md-sys-color-surface-container)}.app-nav a[aria-current=page]{background:var(--md-sys-color-primary-container);color:var(--md-sys-color-on-primary-container)}
.page-container{max-width:1460px;margin:32px auto;padding:0 28px}.report-layout{display:grid;grid-template-columns:224px minmax(0,1fr);gap:28px;align-items:start}.document-outline{position:sticky;top:108px;background:var(--md-sys-color-surface-container-low);border-radius:var(--md-sys-shape-medium);padding:20px;font-size:13px;max-height:calc(100vh - 136px);overflow:auto}.document-outline h2{font-size:15px;margin:0 0 12px;letter-spacing:.01em}.document-outline a{display:block;padding:8px 10px;text-decoration:none;color:var(--md-sys-color-on-surface-variant);border-left:2px solid transparent}.document-outline a:hover{background:var(--md-sys-color-primary-container);border-left-color:var(--md-sys-color-primary);border-radius:4px}.document-outline .subheading{padding-left:22px;font-size:12px}
.report-content{min-width:0;background:white;border-radius:var(--md-sys-shape-large);padding:36px 42px;box-shadow:var(--md-sys-elevation-1)}.report-content h1{font-size:clamp(27px,3.4vw,42px);font-weight:650;letter-spacing:-.04em;line-height:1.4;margin:4px 0 26px}.report-content h2{font-size:23px;line-height:1.6;letter-spacing:-.03em;margin:44px 0 18px;padding-bottom:10px;border-bottom:1px solid #e1e2e9}.report-content h3{font-size:18px;margin-top:30px}.report-content p{max-width:82ch;margin:16px 0}.report-content li{margin:9px 0}.report-content ul{padding-left:24px}.eyebrow{font-size:12px;color:var(--md-sys-color-primary);font-weight:750;letter-spacing:.1em;margin:0 0 8px}
.notice{display:block;border:1px solid #e6c584;background:#fff7e6;border-radius:var(--md-sys-shape-medium);padding:20px 24px;margin:22px 0;color:#5c4100}.notice strong{display:block;font-size:18px;margin-bottom:8px}.muted,footer{color:var(--md-sys-color-on-surface-variant);font-size:13px}.cards,.metric-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:16px;margin:24px 0}.card,.metric-card{background:var(--md-sys-color-surface-container-low);border:1px solid #e1e2e9;border-radius:24px;padding:22px;min-width:0}.card{transition:box-shadow .2s,background .2s}.card:hover{background:var(--md-sys-color-primary-container);box-shadow:var(--md-sys-elevation-2)}.card h2{font-size:18px;border:0;padding:0;margin:8px 0 10px}.card a{text-decoration:none}.card p{font-size:14px;line-height:1.8;margin:0}.metric-card .metric-label{font-size:13px;color:var(--md-sys-color-on-surface-variant)}.metric-card .metric-value{display:block;font-size:30px;font-weight:700;line-height:1.4;font-variant-numeric:tabular-nums;margin:10px 0}.metric-card .metric-detail{font-size:12px;color:var(--md-sys-color-on-surface-variant)}
.chip{display:inline-flex;align-items:center;gap:6px;padding:4px 11px;border-radius:8px;font-size:12px;font-weight:650;line-height:1.6;white-space:nowrap}.chip-pass{background:#d8f3e7;color:#075438}.chip-fail{background:#ffdad6;color:#8f130b}.chip-unknown{background:#ffedc3;color:#624600}.chip-neutral{background:#e4e7ef;color:#404650}
.visual-card{margin:22px 0;padding:24px;border-radius:24px;background:var(--md-sys-color-surface-container-low);border:1px solid #dfe2ec;min-width:0}.visual-card svg{display:block;width:100%;height:auto;max-width:100%;font-family:inherit}.visual-card figcaption{font-size:13px;color:var(--md-sys-color-on-surface-variant);margin-top:16px;line-height:1.9}.visual-card h2,.visual-card h3{margin:0 0 14px;border:0;padding:0}.visual-card .legend{display:flex;gap:16px;flex-wrap:wrap}.visual-card table{margin-top:14px;font-size:12px}.legend-dot{display:inline-block;width:10px;height:10px;border-radius:3px;margin-right:6px}
.visual-card svg{max-width:680px;margin:0 auto}.visual-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px;margin:22px 0}.visual-grid .visual-card{margin:0;padding:20px 16px}.visual-legend{display:flex;gap:16px;flex-wrap:wrap;list-style:none;padding:0!important;font-size:12px}.visual-legend li{margin:6px 0}.visual-card caption{text-align:left;padding:10px 0;font-weight:600;font-size:12px}.visual-card table td,.visual-card table th{padding:9px;font-size:11px}
.table-wrap{overflow:auto;border:1px solid #dfe2ec;border-radius:16px;margin:18px 0;max-width:100%;scrollbar-color:#b4bfd7 transparent}.table-wrap:focus-visible{outline:3px solid var(--md-sys-color-primary)}table{width:100%;border-collapse:collapse;font-size:13px;line-height:1.8;font-variant-numeric:tabular-nums}th,td{text-align:left;vertical-align:top;border-bottom:1px solid #e1e2e9;padding:14px 15px}th{background:#ebeff9;color:#2d4166;font-weight:700;position:sticky;top:0}tbody tr:nth-child(even){background:#fafbfe}tbody tr:hover{background:#f1f5ff}td code{font-size:11px;word-break:break-all}td.num{text-align:right;white-space:nowrap}tr:last-child td{border-bottom:0}
code{font:13px/1.7 ui-monospace,SFMono-Regular,Consolas,monospace;background:#edf0f8;color:#24416e;padding:2px 5px;border-radius:5px;overflow-wrap:anywhere}pre{background:#182238;color:#edf2ff;padding:22px;overflow:auto;border-radius:16px;max-width:100%;font-size:12px}pre code{background:none;color:inherit;padding:0;overflow-wrap:normal}.case-details{margin:24px 0;border:1px solid #dfe2ec;border-radius:16px;padding:14px 18px}.case-details summary{cursor:pointer;font-weight:650;color:var(--md-sys-color-primary);min-height:44px;display:flex;align-items:center}.source-note{margin-top:40px;padding:18px;border-radius:12px;background:var(--md-sys-color-surface-container);font-size:12px;color:var(--md-sys-color-on-surface-variant)}footer{max-width:1460px;margin:0 auto;padding:24px 28px 40px;display:flex;gap:18px;flex-wrap:wrap}
@media(max-width:1100px){.report-layout{grid-template-columns:180px minmax(0,1fr);gap:18px}.report-content{padding:28px}.app-nav a{padding:8px 12px}}
@media(max-width:850px){.report-layout{display:block}.document-outline{position:static;max-height:none;margin-bottom:18px;padding:14px 18px}.document-outline a{display:inline-block;border:0;font-size:12px}.document-outline h2{margin-bottom:4px}.app-bar-inner{align-items:flex-start;flex-direction:column;gap:8px}.app-nav{width:100%;overflow:auto;flex-wrap:nowrap}.app-nav a{white-space:nowrap;min-height:40px}.page-container{margin:18px auto;padding:0 16px}.report-content{padding:24px;border-radius:24px}.visual-card{padding:18px}.metric-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media(max-width:1080px){.visual-grid{grid-template-columns:1fr}}
@media(max-width:850px){html{scroll-padding-top:152px}}
@media(max-width:480px){body{font-size:15px}.page-container{padding:0 10px}.app-bar-inner{padding:12px 16px}.report-content{padding:20px 16px}.report-content h1{font-size:27px}.report-content h2{font-size:20px}.metric-card{padding:16px}.metric-card .metric-value{font-size:24px}.visual-card{padding:12px}.cards{grid-template-columns:1fr}.notice{padding:16px}th,td{padding:10px;font-size:12px}footer{padding:20px 16px}}
@media(prefers-reduced-motion:reduce){html{scroll-behavior:auto}.card{transition:none}}
'''


def _href(target,source):
    target=html.unescape(target)
    parsed=urlsplit(target)
    if parsed.scheme:
        return target if parsed.scheme in ('https','http','mailto') else '#unsafe-link'
    if target.startswith('#'):return target
    path,separator,fragment=target.partition('#')
    normalized=posixpath.normpath(posixpath.join(source.parent.as_posix(),path))
    if normalized.startswith('../') or normalized.startswith('/'):return '#unsafe-link'
    destination=MARKDOWN.get(normalized) or COPIES.get(normalized)
    current=MARKDOWN.get(source.as_posix(),'native/index.html')
    link=posixpath.relpath(destination,posixpath.dirname(current)) if destination else REPOSITORY+'/blob/main/'+normalized
    return link+(separator+fragment if separator else '')


def _inline(text,source):
    escaped=html.escape(text,quote=False)
    pattern=r'`([^`]+)`|\*\*(.+?)\*\*|\[([^\]]+)\]\(([^)]+)\)|(https://[^\s<]+)'
    def replace(match):
        if match[1] is not None:return '<code>'+match[1]+'</code>'
        if match[2] is not None:return '<strong>'+match[2]+'</strong>'
        label=match[3] or match[5]
        target=match[4] or match[5]
        trailing=''
        if match[5]:
            target=target.rstrip('.,;');trailing=match[5][len(target):];label=target
        return '<a href="'+html.escape(_href(target,source),quote=True)+'">'+label+'</a>'+trailing
    return re.sub(pattern,replace,escaped)


def render_markdown(text,*,source):
    """Restricted report Markdown; raw HTML is text, not an executable template."""
    source=Path(source);lines=text.splitlines();output=[];index=0;section=0
    while index<len(lines):
        line=lines[index]
        if not line.strip():index+=1;continue
        if line.startswith('```'):
            index+=1;code=[]
            while index<len(lines) and not lines[index].startswith('```'):
                code.append(lines[index]);index+=1
            output.append('<pre><code>'+html.escape('\n'.join(code))+'</code></pre>');index+=1;continue
        if line.startswith('|') and index+1<len(lines) and re.fullmatch(r'[|:\-\s]+',lines[index+1]):
            cells=lambda row:row.strip().strip('|').split('|')
            output.append('<div class="table-wrap" tabindex="0" role="region" aria-label="보고서 수치 표"><table><thead><tr>'+''.join('<th scope="col">'+_inline(c.strip(),source)+'</th>' for c in cells(line))+'</tr></thead><tbody>')
            index+=2
            while index<len(lines) and lines[index].startswith('|'):
                rendered=[]
                for cell in cells(lines[index]):
                    value=cell.strip();classes=' class="num"' if re.fullmatch(r'[+\-]?[\d,.]+%?',value) else ''
                    content=_inline(value,source)
                    if value in ('성공','통과','실패','시간 초과','미실행','자료 없음','미확인'):
                        tone='pass' if value in ('성공','통과') else 'fail' if value=='실패' else 'unknown'
                        content=f'<span class="chip chip-{tone}">{content}</span>'
                    rendered.append('<td'+classes+'>'+content+'</td>')
                output.append('<tr>'+''.join(rendered)+'</tr>');index+=1
            output.append('</tbody></table></div>');continue
        heading=re.match(r'^(#{1,6})\s+(.+)$',line)
        if heading:
            level=len(heading[1]);anchor=''
            if level in (2,3):section+=1;anchor=f' id="section-{section}"'
            output.append(f'<h{level}{anchor}>'+_inline(heading[2],source)+f'</h{level}>');index+=1;continue
        if line.startswith('- '):
            output.append('<ul>')
            while index<len(lines) and lines[index].startswith('- '):
                output.append('<li>'+_inline(lines[index][2:],source)+'</li>');index+=1
            output.append('</ul>');continue
        paragraph=[line];index+=1
        while index<len(lines) and lines[index].strip() and not lines[index].startswith(('#','- ','|','```')):
            paragraph.append(lines[index]);index+=1
        output.append('<p>'+_inline(' '.join(paragraph),source)+'</p>')
    return '\n'.join(output)


def _page(title,body,destination):
    parent=posixpath.dirname(destination) or '.'
    link=lambda path:posixpath.relpath(path,parent)
    nav=''.join('<a href="'+link(path)+'"'+(' aria-current="page"' if path==destination else '')+'>'+label+'</a>' for path,label in
               [('index.html','보고서 목록'),('native/index.html','최신 검증'),('completion/index.html','완료·제한'),('runbook/index.html','사용법')])
    headings=re.findall(r'<h([23]) id="([^"]+)">(.*?)</h[23]>',body)
    outline='<aside class="document-outline"><h2>문서 목차</h2><nav aria-label="문서 목차">'+''.join(
         '<a href="#'+identifier+'"'+(' class="subheading"' if level=='3' else '')+'>'+re.sub(r'<[^>]+>','',heading)+'</a>'
         for level,identifier,heading in headings)+'</nav></aside>' if headings else ''
    layout='report-layout' if headings else 'overview-layout'
    return '<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="theme-color" content="#365e9d"><title>'+html.escape(title)+' | ACE-RTL × JEV</title><link rel="stylesheet" href="'+link('assets/site.css')+'"></head><body><a class="skip-link" href="#report-content">본문으로 건너뛰기</a><header class="app-bar"><div class="app-bar-inner"><a class="brand" href="'+link('index.html')+'"><span class="brand-mark" aria-hidden="true">RTL</span><span>ACE-RTL × JEV<small>측정과 근거 중심의 검증 보고서</small></span></a><nav class="app-nav" aria-label="주 메뉴">'+nav+'</nav></div></header><div class="page-container"><div class="'+layout+'">'+outline+'<main id="report-content" class="report-content"><div class="eyebrow">실제 측정 · 공개 근거</div>'+body+'</main></div></div><footer><span>유효한 실제 CVDP 평가 결과만 통과의 근거로 사용합니다.</span><a href="'+REPOSITORY+'">소스 저장소</a><a href="'+link('publication.json')+'">공개 자료 목록·원문 해시</a></footer></body></html>'


def _native_rows(markdown):
    rows=[]
    for line in markdown.splitlines():
        if not re.match(r'^\|\s*[ABC]:',line):continue
        cells=[c.strip() for c in line.strip().strip('|').split('|')]
        if len(cells)!=7:raise ValueError('최신 A/B/C 표의 열 수가 일치하지 않습니다')
        def number(value):
            cleaned=value.replace(',','')
            if cleaned in ('미확인','자료 없음','미실행'):return None
            parsed=float(cleaned)
            return int(parsed) if parsed.is_integer() else parsed
        arm=cells[0][0]
        outcome=cells[1]
        status='infra_error' if '차단' in outcome or 'blocked' in outcome.lower() else 'task_failed' if '실패' in outcome or 'failure' in outcome.lower() else 'verified_pass' if '통과' in outcome or 'PASS' in outcome else 'unknown'
        rows.append({'arm':arm,'status':status,
             'wall_seconds':number(cells[2]),'primary_calls':number(cells[3]),'primary_tokens':number(cells[4]),
             'jev_calls':number(cells[5]),'jev_tokens':number(cells[6])})
    if {r['arm'] for r in rows}!={'A','B','C'}:raise ValueError('최신 A/B/C 측정 자료가 없습니다')
    return rows


def _visuals(destination,sources):
    metrics=lambda name:json.loads(sources[name].read_text())
    if destination=='native/index.html':
        return '<section class="visual-grid" aria-label="측정 비교 그래프">'+native_figures(_native_rows(sources['reports/jev-native-plan/final-report.md'].read_text()))+'</section>'+flow_diagram()
    if destination=='historical/baseline.html':return baseline_figures(metrics(METRICS[0]))
    if destination=='historical/jev.html':
        data=metrics(METRICS[1]);comparison={'baseline':data['baseline_e2e'],'jev':data['jev_e2e']}
        return audit_figures(data)+historical_comparison_figures(comparison)
    if destination=='historical/comparison.html':return historical_comparison_figures(metrics(METRICS[2]))
    if destination in ('audit/index.html','runbook/index.html'):return flow_diagram()
    return ''


def build_site(root,destination):
    reset_visual_ids()
    root=Path(root).resolve();destination=Path(destination).resolve()
    if destination==root or root.is_relative_to(destination):raise ValueError('output must not contain the repository')
    if destination.exists() and any(p.is_symlink() for p in destination.rglob('*')):
        raise ValueError('output symlinks are not permitted')
    existing={p.relative_to(destination).as_posix() for p in destination.rglob('*') if p.is_file()} if destination.exists() else set()
    if existing-EXPECTED_FILES:raise ValueError('unexpected output files; refusing to publish or delete them')
    sources={}
    for name in list(MARKDOWN)+list(COPIES)+list(METRICS):
        component=root
        for part in Path(name).parts:
            component=component/part
            if component.is_symlink():raise ValueError('published source symlinks are not permitted: '+name)
        path=(root/name).resolve()
        if not path.is_relative_to(root) or not path.is_file():raise ValueError('published source missing or outside repository: '+name)
        sources[name]=path
    destination.mkdir(parents=True,exist_ok=True)
    for name,target in MARKDOWN.items():
        content=localize_report_markdown(sources[name].read_text());title=content.splitlines()[0].lstrip('# ')
        rendered=render_markdown(content,source=Path(name))
        figures=_visuals(target,sources)
        first=re.search(r'</h1>',rendered)
        if first:rendered=rendered[:first.end()]+figures+rendered[first.end():]
        else:rendered=figures+rendered
        if target.startswith('historical/'):
            rendered='<p class="notice"><strong>과거 실험 자료</strong>최신 네이티브 A/B/C와 별도 실행입니다. 표본·조건·사용량 미확인 항목을 구분해 해석하십시오.</p>'+rendered
        page=destination/target;page.parent.mkdir(parents=True,exist_ok=True)
        page.write_text(_page(title,rendered,target))
    for name,target in COPIES.items():
        page=destination/target;page.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(sources[name],page)
    (destination/'assets').mkdir(exist_ok=True)
    (destination/'assets/site.css').write_text(CSS)
    (destination/'.nojekyll').write_text('')
    cards=''.join('<section class="card"><span class="chip chip-neutral">'+category+'</span><h2><a href="'+path+'">'+title+'</a></h2><p>'+description+'</p></section>' for path,title,description,category in
        [('native/index.html','최신 네이티브 검증','토큰 구성·실험 결과 그래프와 실제 평가 흐름을 한눈에 확인합니다.','최신 실측'),
         ('completion/index.html','구현과 남은 한계','기능별 완료 조건, 검토 수정, 미완료 실험과 데이터 제한입니다.','구현 범위'),
         ('runbook/index.html','설정과 재실행','기본 기준 실행과 제한 예산, 안전한 사용 방법을 안내합니다.','사용 안내'),
         ('historical/baseline.html','전체 기준 실행 292건','성공·실패·시간 초과 분포와 미확인 사용량을 구분합니다.','과거 실험'),
         ('historical/jev.html','제한 예산 판단 검증','판단 48건의 선별 과정과 과거 1건의 실제 평가를 시각화합니다.','과거 실험'),
         ('historical/comparison.html','과거 측정 비교','주 모델·JEV 토큰 구성과 조건이 다른 시간 지표의 한계를 보여줍니다.','과거 실험')])
    rows=_native_rows(sources['reports/jev-native-plan/final-report.md'].read_text())
    b=next(r for r in rows if r['arm']=='B');c=next(r for r in rows if r['arm']=='C')
    total=lambda row:row['primary_tokens']+row['jev_tokens'] if row['primary_tokens'] is not None and row['jev_tokens'] is not None else None
    fmt=lambda value:f'{value:,}' if value is not None else '미확인'
    difference=(total(c)/total(b)-1)*100 if total(c) is not None and total(b) else None
    outcome_labels={'verified_pass':'실제 통과','task_failed':'실제 실패','infra_error':'기반 환경 차단','unknown':'미확인'}
    metrics='<div class="metric-grid">'+''.join('<section class="metric-card"><span class="metric-label">'+label+'</span><strong class="metric-value">'+value+'</strong><span class="metric-detail">'+detail+'</span></section>' for label,value,detail in
        [('B · 수정된 기준 실행',outcome_labels[b['status']],'실제 CVDP 평가 결과 · 과제 1건'),
         ('C · JEV 핵심 경로',outcome_labels[c['status']],'실제 CVDP 평가 결과 · 과제 1건'),
         ('C 전체 사용 토큰',fmt(total(c)),f'B {fmt(total(b))} 토큰 대비 '+(f'{difference:+.1f}%' if difference is not None else '차이 미확인'))])+'</div>'
    body='<h1>ACE-RTL × JEV<br>측정으로 확인하는 검증 결과</h1><p class="muted">최신 구현 검증과 과거 실험을 분리하여 보고합니다. 모든 수치와 그림은 기존 공개 측정 자료를 사용합니다.</p>'+metrics+'<div class="notice"><strong>JEV 성능 개선은 입증되지 않았습니다.</strong>최신 비교에서 B는 실제 통과했지만 C는 실패했고 전체 사용 토큰도 증가했습니다. 짧은 실패 종료 시간을 속도 향상으로 보지 않습니다. 미확인과 미실행을 0 또는 성공으로 집계하지 않습니다.</div><h2 id="overview-visuals">최신 실험 한눈에 보기</h2>'+native_figures(rows)+'<h2 id="report-library">보고서와 근거 탐색</h2><div class="cards">'+cards+'</div><h2 id="evidence-links">공개 검증 자료</h2><ul><li><a href="audit/index.html">네이티브 호출 경로 및 F01–F20 점검</a></li><li><a href="data/budget-snapshot.json">실험 예산 원장 요약</a></li><li><a href="data/verified-claims.json">검증된 CVDP 통과 주장 해시</a></li></ul><div class="source-note">비공개 데이터셋·검사기·참조 구현, 원시 실행 로그, 프롬프트와 .env 파일은 배포 대상이 아닙니다. 추가 모델 호출 없이 기존 공개 보고서만 표시합니다. 코드 식별자·API 경로·해시는 원문을 보존합니다.</div>'
    (destination/'index.html').write_text(_page('보고서 목록',body,'index.html'))
    (destination/'publication.json').write_text(json.dumps({'schema':'public-report-site-1','sources':{
       name:hashlib.sha256(path.read_bytes()).hexdigest() for name,path in sources.items()},'files':sorted(EXPECTED_FILES)},indent=2))
    return destination


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',default='site');parser.add_argument('--root',default=str(ROOT))
    args=parser.parse_args();print(build_site(args.root,args.output))
