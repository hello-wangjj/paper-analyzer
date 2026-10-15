"""OMML 公式与 md_to_docx 双轨（OMML → PNG）。"""
from __future__ import annotations

import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SHARED = ROOT / "tools"
if str(SHARED) not in sys.path:
    sys.path.insert(0, str(SHARED))


class MathToOmmlTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            import latex2mathml
        except ImportError:
            raise unittest.SkipTest("latex2mathml not installed")

    def test_latex_to_omml_has_omath(self):
        from lxml import etree
        from math_to_omml import latex_to_omml

        el = latex_to_omml(r"s = \alpha x + \beta y", display=True)
        s = etree.tostring(el, encoding="unicode")
        self.assertIn("oMath", s)

    def test_try_fails_gracefully(self):
        from math_to_omml import try_latex_to_omml

        # 极怪输入仍应返回 None 而非抛错
        self.assertIsNone(try_latex_to_omml(r"\unknownmacro{???{{{"))

    def test_left_right_min_converts(self):
        from lxml import etree
        from math_to_omml import latex_to_omml

        el = latex_to_omml(
            r"\min\left(1,\frac{p_{mem}}{\max(1,d_{mem})}\right)",
            display=True,
        )
        self.assertIn("oMath", etree.tostring(el, encoding="unicode"))

    def test_score_with_left_right_converts(self):
        from math_to_omml import try_latex_to_omml

        latex = (
            r"Score(\mathbf{d},\mathbf{p}) = w_{cpu}\cdot d_{cpu}\cdot p_{cpu} + "
            r"w_{mem}\cdot \min\left(1,\frac{p_{mem}}{\max(1,d_{mem})}\right) + "
            r"w_{io}\cdot(1-p_{io\_busy})\cdot d_{io} - \lambda\cdot n_{inflight}"
        )
        self.assertIsNotNone(try_latex_to_omml(latex, display=True))

    def test_script_children_map_sub_sup(self):
        """回归（2026-10-15）：sSup 上标曾误写入 m:sub，被 Word 按 schema 丢弃。

        v7 交底书 16 处 sSup 有 15 处上标丢失；sSub / sSubSup 一并钉死子元素次序。
        """
        from lxml import etree
        from math_to_omml import latex_to_omml

        def kids_of(latex, kind):
            el = latex_to_omml(latex, display=True)
            match = [e for e in el.iter() if etree.QName(e).localname == kind]
            self.assertEqual(len(match), 1, f"{latex} 应产出恰好 1 个 {kind}")
            return [etree.QName(c).localname for c in match[0]], "".join(
                match[0].itertext()
            )

        kids, text = kids_of(r"x^2", "sSup")
        self.assertEqual(kids, ["e", "sup"])
        self.assertIn("2", text)
        kids, text = kids_of(r"x_1", "sSub")
        self.assertEqual(kids, ["e", "sub"])
        self.assertIn("1", text)
        kids, text = kids_of(r"x_1^2", "sSubSup")
        self.assertEqual(kids, ["e", "sub", "sup"])
        self.assertIn("1", text)
        self.assertIn("2", text)


class MdToDocxOmmlTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            import latex2mathml
            from docx import Document
        except ImportError:
            raise unittest.SkipTest("latex2mathml/python-docx missing")

    def test_block_equation_writes_omml(self):
        from md_to_docx import convert_md_to_docx

        md = "前文\n\n$$\ns = \\alpha x + \\beta y\n$$\n\n后文\n"
        doc = convert_md_to_docx(md, base_dir=None, prefer_omml=True)
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "t.docx"
            doc.save(str(out))
            with zipfile.ZipFile(out) as zf:
                xml = zf.read("word/document.xml").decode("utf-8")
        self.assertIn("oMath", xml)
        self.assertIn("oMathPara", xml)
        from md_to_docx import get_math_stats

        st = get_math_stats()
        self.assertGreaterEqual(st.omml, 1)
        self.assertEqual(st.text, 0)

    def test_omml_fail_records_text_fallback(self):
        from md_to_docx import convert_md_to_docx, get_math_stats

        convert_md_to_docx(
            "$$\n\\unknownmacro{???{{{\n$$\n",
            base_dir=None,
            prefer_omml=True,
        )
        st = get_math_stats()
        self.assertGreaterEqual(st.text, 1)
        self.assertTrue(any("unknownmacro" in x for x in st.text_latex))

    def test_no_omml_falls_back_without_crash(self):
        from md_to_docx import convert_md_to_docx

        md = "$$\na+b\n$$\n"
        doc = convert_md_to_docx(md, base_dir=None, prefer_omml=False)
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "t.docx"
            doc.save(str(out))
            self.assertTrue(out.is_file())


if __name__ == "__main__":
    unittest.main()
