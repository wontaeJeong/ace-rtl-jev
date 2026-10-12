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
    assert 'JEV superiority' in (output/'native/index.html').read_text()
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
