"""Static public-site boundaries and readable report rendering; no inference."""
from pathlib import Path
from html.parser import HTMLParser
import pytest

ROOT=Path(__file__).resolve().parents[1]


def test_renderer_preserves_tables_code_and_escapes_raw_html():
    from build_report_pages import render_markdown
    text='# Report\n\n| Arm | Result |\n|---|---|\n| B | **PASS** |\n\n```bash\necho <safe>\n```\n<script>bad()</script>\n'
    html=render_markdown(text,source=Path('reports/jev-native-plan/final-report.md'))
    assert '<table>' in html and '<strong>PASS</strong>' in html
    assert 'echo &lt;safe&gt;' in html
    assert '<script>' not in html and '&lt;script&gt;' in html


def test_build_only_exports_allowlisted_public_reports(tmp_path):
    from build_report_pages import build_site,EXPECTED_FILES
    output=tmp_path/'site'
    build_site(ROOT,output)
    files={p.relative_to(output).as_posix() for p in output.rglob('*') if p.is_file()}
    assert files==EXPECTED_FILES
    assert '성능 우위' in (output/'native/index.html').read_text()
    assert '286' in (output/'completion/index.html').read_text()
    assert not any('experiments/' in name or '.env' in name or 'outputs/' in name for name in files)
    assert (output/'.nojekyll').exists()


def test_generated_local_links_resolve_within_site(tmp_path):
    from build_report_pages import build_site
    output=tmp_path/'site';build_site(ROOT,output)
    class Links(HTMLParser):
        def __init__(self):super().__init__();self.hrefs=[];self.ids=set()
        def handle_starttag(self,tag,attrs):
            self.hrefs.extend(v for k,v in attrs if k in ('href','src'))
            self.ids.update(v for k,v in attrs if k=='id' or tag=='a' and k=='name')
    for page in output.rglob('*.html'):
        parser=Links();parser.feed(page.read_text())
        for href in parser.hrefs:
            if href.startswith(('https://','http://','mailto:')):continue
            name,_,fragment=href.partition('#')
            path=(page.parent/name).resolve() if name else page.resolve()
            assert path.is_relative_to(output.resolve()),(page,href)
            assert path.exists(),(page,href)
            if fragment:
                target=Links();target.feed(path.read_text())
                assert fragment in target.ids,(page,href)


def test_existing_unexpected_output_is_refused_not_removed(tmp_path):
    from build_report_pages import build_site
    output=tmp_path/'site';output.mkdir()
    private=output/'.env.local';private.write_text('private fixture')
    with pytest.raises(ValueError,match='unexpected'):
        build_site(ROOT,output)
    assert private.read_text()=='private fixture'


def test_output_symlink_cannot_overwrite_files_outside_public_site(tmp_path):
    from build_report_pages import build_site
    output=tmp_path/'site';output.mkdir()
    private=tmp_path/'private.txt';private.write_text('retain')
    (output/'index.html').symlink_to(private)
    with pytest.raises(ValueError,match='symlink'):
        build_site(ROOT,output)
    assert private.read_text()=='retain'


@pytest.mark.parametrize('parent_link',[False,True])
def test_source_symlinks_cannot_publish_private_in_repository_files(tmp_path,parent_link):
    from build_report_pages import build_site,MARKDOWN,COPIES
    root=tmp_path/'repository';root.mkdir()
    for name in MARKDOWN|COPIES:
        if name=='reports/jev-native-plan/final-report.md' or parent_link and name.startswith('reports/jev-native-plan/'):
            continue
        path=root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text('public fixture')
    private=root/'private';private.mkdir()
    (private/'final-report.md').write_text('private fixture must not be published')
    reports=root/'reports';reports.mkdir(exist_ok=True)
    if parent_link:
        (reports/'jev-native-plan').symlink_to(private,target_is_directory=True)
    else:
        target=reports/'jev-native-plan';target.mkdir(exist_ok=True)
        (target/'final-report.md').symlink_to(private/'final-report.md')
    with pytest.raises(ValueError,match='symlink'):
        build_site(root,tmp_path/'site')
    assert not (tmp_path/'site').exists()


def test_material_layout_has_korean_navigation_and_document_outline(tmp_path):
    from build_report_pages import build_site
    output=tmp_path/'site';build_site(ROOT,output)
    css=(output/'assets/site.css').read_text()
    assert '--md-sys-color-primary:' in css and '--md-sys-color-surface-container:' in css
    page=(output/'native/index.html').read_text()
    assert '문서 목차' in page and '본문으로 건너뛰기' in page
    assert 'class="app-bar"' in page and 'class="report-layout"' in page
    assert 'Evidence first' not in page and 'Source repository' not in page


def test_reports_have_measured_charts_and_accessible_flow_diagram(tmp_path):
    from build_report_pages import build_site
    output=tmp_path/'site';build_site(ROOT,output)
    page=(output/'native/index.html').read_text()
    assert page.count('<svg')>=3
    assert 'role="img"' in page and '<desc' in page
    assert '49,943' in page and '16,624' in page
    assert '속도 우열' in page or '속도 개선' in page
    assert '<svg' in (output/'historical/baseline.html').read_text()


def test_material_headings_have_unique_stable_section_anchors():
    from build_report_pages import render_markdown
    page=render_markdown('# 제목\n\n## 요약\n내용\n\n## 요약\n후속\n',source=Path('reports/jev-native-plan/final-report.md'))
    assert 'id="section-1"' in page and 'id="section-2"' in page


def test_repeated_builds_produce_identical_public_html_in_one_process(tmp_path):
    from build_report_pages import build_site
    first=tmp_path/'first';second=tmp_path/'second'
    build_site(ROOT,first);build_site(ROOT,second)
    for page in first.rglob('*.html'):
        assert page.read_bytes()==(second/page.relative_to(first)).read_bytes()
