"""RTF/HTML normalisation, sanitising for Qt and snippet trimming."""

from __future__ import annotations

from esword4linux.core.text import snippet, to_plain, to_rich


def test_rtf_to_plain():
    raw = r"{\pard\sa150\cf10\fs40\b\qc ¡ABRID EL DEPÓSITO! \par}"
    plain = to_plain(raw)
    assert "ABRID EL DEPÓSITO" in plain
    assert "pard" not in plain


def test_rtf_to_rich_keeps_bold():
    raw = r"{\pard \b La creación}\par\pard En el principio creó Dios"
    rich = to_rich(raw)
    assert "<b>" in rich
    assert "En el principio" in rich


def test_html_sanitized():
    raw = '<p onclick="x()">Hola <script>alert(1)</script><b>mundo</b></p>'
    rich = to_rich(raw)
    assert "<script" not in rich
    assert "alert" not in rich
    assert "<b>mundo</b>" in rich


def test_ref_tag_becomes_anchor():
    raw = "<p>Ver <ref>Juan 3:16</ref>.</p>"
    rich = to_rich(raw)
    assert 'href="ref:Juan 3:16"' in rich


def test_disallowed_tags_never_survive_raw():
    """A disallowed tag never comes out as executable HTML; the text is kept."""
    rich = to_rich("<marquee>texto</marquee>")
    assert "texto" in rich
    assert "<marquee>" not in rich


def test_script_removed_entirely():
    rich = to_rich("<p>antes</p><script>alert(1)</script><p>después</p>")
    assert "antes" in rich and "después" in rich
    assert "alert" not in rich


def test_br_run_collapsed():
    rich = to_rich("a" + "<br>" * 8 + "b")
    assert rich.count("<br>") <= 2


def test_plain_passthrough_escaped():
    rich = to_rich("Juan 3:16 <b>no es html</b>")
    assert "<b>no es html</b>" in rich or "&lt;b&gt;" in rich


def test_snippet_truncates():
    text = "palabra " * 100
    out = snippet(text, 60)
    assert len(out) <= 61
    assert out.endswith("…")
