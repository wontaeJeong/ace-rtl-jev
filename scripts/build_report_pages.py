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

ROOT=Path(__file__).resolve().parents[1]
REPOSITORY='https://github.com/wontaeJeong/ace-rtl-jev'
MARKDOWN={
    'reports/jev-native-plan/final-report.md':'native/index.html',
    'docs/jev_completion_status.md':'completion/index.html',
    'docs/jev_native_runbook.md':'runbook/index.html',
    'docs/jev_integration_audit.md':'audit/index.html',
}
COPIES={
    'reports/jev-native-plan/budget-snapshot.json':'data/budget-snapshot.json',
    'reports/jev-native-plan/verified-claims.json':'data/verified-claims.json',
    'reports/clean-baseline/comparison.html':'historical/baseline.html',
    'reports/jev-final/final-report.html':'historical/jev.html',
    'reports/jev-comparison/comparison.html':'historical/comparison.html',
}
EXPECTED_FILES=set(MARKDOWN.values())|set(COPIES.values())|{'index.html','assets/site.css','.nojekyll','publication.json'}
CSS='''
:root{color-scheme:light;--ink:#17253c;--muted:#596b83;--accent:#195bd7;--line:#dbe4ef}
*{box-sizing:border-box}body{margin:0;background:#f5f7fc;color:var(--ink);font:16px/1.75 system-ui,-apple-system,sans-serif}
a{color:var(--accent);text-underline-offset:3px}header,main,footer{max-width:1150px;margin:auto;padding:24px}
header{display:flex;justify-content:space-between;gap:16px;flex-wrap:wrap}nav{display:flex;gap:18px;flex-wrap:wrap}
main{background:white;border:1px solid var(--line);border-radius:14px;padding:36px;margin-bottom:24px}
h1{font-size:clamp(26px,4vw,42px);line-height:1.3}h2{margin-top:36px;border-bottom:1px solid var(--line);padding-bottom:8px}
code{background:#edf2fa;padding:2px 5px;border-radius:4px;overflow-wrap:anywhere}pre{background:#142139;color:#eef4ff;padding:20px;overflow:auto;border-radius:8px}
pre code{background:none;padding:0;color:inherit;overflow-wrap:normal}.table-wrap{overflow-x:auto}table{width:100%;border-collapse:collapse;font-size:14px}
th,td{text-align:left;vertical-align:top;border-bottom:1px solid var(--line);padding:12px}th{background:#edf2fa}
.notice{border-left:4px solid #dc8720;background:#fff8eb;padding:18px}.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(250px,1fr));gap:16px}
.card{border:1px solid var(--line);border-radius:10px;padding:22px}.muted,footer{color:var(--muted);font-size:14px}
@media(max-width:650px){header,main,footer{padding:18px}main{border-radius:0}th,td{padding:8px}nav{gap:12px}}
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
    source=Path(source);lines=text.splitlines();output=[];index=0
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
            output.append('<div class="table-wrap"><table><thead><tr>'+''.join('<th>'+_inline(c.strip(),source)+'</th>' for c in cells(line))+'</tr></thead><tbody>')
            index+=2
            while index<len(lines) and lines[index].startswith('|'):
                output.append('<tr>'+''.join('<td>'+_inline(c.strip(),source)+'</td>' for c in cells(lines[index]))+'</tr>');index+=1
            output.append('</tbody></table></div>');continue
        heading=re.match(r'^(#{1,6})\s+(.+)$',line)
        if heading:
            level=len(heading[1]);output.append(f'<h{level}>'+_inline(heading[2],source)+f'</h{level}>');index+=1;continue
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
    nav=''.join('<a href="'+link(path)+'">'+label+'</a>' for path,label in
               [('index.html','보고서 목록'),('native/index.html','최신 검증'),('completion/index.html','완료·제한'),('runbook/index.html','사용법')])
    return '<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>'+html.escape(title)+' | ACE-RTL × JEV</title><link rel="stylesheet" href="'+link('assets/site.css')+'"></head><body><header><a href="'+link('index.html')+'"><strong>ACE-RTL × JEV</strong></a><nav>'+nav+'</nav></header><main>'+body+'</main><footer>Evidence first · only valid actual CVDP results establish PASS. <a href="'+REPOSITORY+'">Source repository</a></footer></body></html>'


def build_site(root,destination):
    root=Path(root).resolve();destination=Path(destination).resolve()
    if destination==root or root.is_relative_to(destination):raise ValueError('output must not contain the repository')
    if destination.exists() and any(p.is_symlink() for p in destination.rglob('*')):
        raise ValueError('output symlinks are not permitted')
    existing={p.relative_to(destination).as_posix() for p in destination.rglob('*') if p.is_file()} if destination.exists() else set()
    if existing-EXPECTED_FILES:raise ValueError('unexpected output files; refusing to publish or delete them')
    sources={}
    for name in MARKDOWN|COPIES:
        component=root
        for part in Path(name).parts:
            component=component/part
            if component.is_symlink():raise ValueError('published source symlinks are not permitted: '+name)
        path=(root/name).resolve()
        if not path.is_relative_to(root) or not path.is_file():raise ValueError('published source missing or outside repository: '+name)
        sources[name]=path
    destination.mkdir(parents=True,exist_ok=True)
    for name,target in MARKDOWN.items():
        content=sources[name].read_text();title=content.splitlines()[0].lstrip('# ')
        page=destination/target;page.parent.mkdir(parents=True,exist_ok=True)
        page.write_text(_page(title,render_markdown(content,source=Path(name)),target))
    for name,target in COPIES.items():
        page=destination/target;page.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(sources[name],page)
    (destination/'assets').mkdir(exist_ok=True)
    (destination/'assets/site.css').write_text(CSS)
    (destination/'.nojekyll').write_text('')
    cards=''.join('<section class="card"><h2><a href="'+path+'">'+title+'</a></h2><p>'+description+'</p></section>' for path,title,description in
        [('native/index.html','최신 native 검증 보고서','D/J 구현과 A/B/C 실측, 실제 PASS 및 차단 항목.'),
         ('completion/index.html','구현·리뷰 완료 조건','기능별 검증, 리뷰 수정, 미완료 실험과 데이터 제한.'),
         ('runbook/index.html','설정과 재실행 방법','기본 baseline_fixed, X 비활성화, bounded 예산과 사용법.'),
         ('historical/baseline.html','기존 전체 baseline','이전 측정 cohort의 원본 공개 대시보드.'),
         ('historical/jev.html','기존 budgeted JEV 보고서','최신 native 비교와 다른 과거 실험; 결과를 섞지 않습니다.'),
         ('historical/comparison.html','기존 비교 대시보드','과거 baseline/retrospective 비교 자료.')])
    body='<h1>ACE-RTL × JEV 검증 보고서</h1><p class="muted">Measured results · public summaries only</p><p class="notice"><strong>JEV 성능 개선은 입증되지 않았습니다.</strong> 최신 비교에서 B는 실제 PASS, C는 실패하며 총 토큰이 더 많았습니다. 실패·unknown·미실행 실험을 숨기지 않습니다.</p><p>구현 <a href="'+REPOSITORY+'/pull/4">PR #4</a>는 병합되었습니다. 보고서의 원본 측정 시점과 후속 검증을 구분합니다.</p><div class="cards">'+cards+'</div><h2>공개 검증 자료</h2><ul><li><a href="audit/index.html">Native 호출 경로 및 F01–F20 감사</a></li><li><a href="data/budget-snapshot.json">Campaign budget snapshot</a></li><li><a href="data/verified-claims.json">검증된 CVDP claim hashes</a></li></ul><p class="muted">Dataset/private checker/reference 구현, raw 실행 로그, 프롬프트와 .env 파일은 배포 대상이 아닙니다. 추가 모델 호출 없이 기존 공개 보고서만 게시합니다.</p>'
    (destination/'index.html').write_text(_page('보고서 목록',body,'index.html'))
    (destination/'publication.json').write_text(json.dumps({'schema':'public-report-site-1','sources':{
       name:hashlib.sha256(path.read_bytes()).hexdigest() for name,path in sources.items()},'files':sorted(EXPECTED_FILES)},indent=2))
    return destination


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',default='site');parser.add_argument('--root',default=str(ROOT))
    args=parser.parse_args();print(build_site(args.root,args.output))
