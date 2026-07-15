"""LaTeX → OMML 转换器：将 LaTeX 公式转为 Word 原生公式（OMML）。

不生成图片，公式在 Word 中可编辑、可缩放、自动适配字体大小。

流程：LaTeX → MathML（latex2mathml）→ OMML（lxml）→ 嵌入 python-docx 段落
"""
from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import Any

from lxml import etree

# OMML namespace
_M_NS = "http://schemas.openxmlformats.org/officeDocument/2006/math"
_NSMAP = {"m": _M_NS}


def _tag(local: str) -> str:
    return f"{{{_M_NS}}}{local}"


# ── MathML text extraction ──────────────────────────────────────────────────

def _text_of(node: ET.Element) -> str:
    """Extract text content from a MathML element (including children)."""
    parts: list[str] = []
    if node.text:
        parts.append(node.text)
    for child in node:
        parts.append(_text_of(child))
        if child.tail:
            parts.append(child.tail)
    return "".join(parts)


# ── Core recursive converter ────────────────────────────────────────────────

def _mml_to_omml(node: ET.Element) -> list[etree._Element]:
    """Convert a single MathML element to a list of OMML elements."""
    tag = node.tag.split("}")[-1] if "}" in node.tag else node.tag

    if tag == "math":
        # Root: recurse into children (skip outer mrow wrapper)
        results: list[etree._Element] = []
        for child in node:
            results.extend(_mml_to_omml(child))
        return results

    if tag == "mrow":
        results = []
        for child in node:
            results.extend(_mml_to_omml(child))
        return results

    if tag == "mi":
        # Identifier: Greek letters, variables, or upright text (mathvariant=normal)
        text = _text_of(node)
        mathvariant = node.get("mathvariant", "")
        r = etree.Element(_tag("r"))
        if mathvariant == "normal":
            rpr = etree.SubElement(r, _tag("rPr"))
            sty = etree.SubElement(rpr, _tag("sty"))
            sty.set(_tag("val"), "p")  # plain/upright
        t = etree.SubElement(r, _tag("t"))
        t.text = text
        return [r]

    if tag == "mn":
        # Number
        text = _text_of(node)
        r = etree.Element(_tag("r"))
        t = etree.SubElement(r, _tag("t"))
        t.text = text
        return [r]

    if tag == "mo":
        # Operator or fence
        text = _text_of(node)
        fence = node.get("fence", "")

        if fence == "true":
            # Fence character (parenthesis, brace) — render as text run
            r = etree.Element(_tag("r"))
            t = etree.SubElement(r, _tag("t"))
            t.text = text
            return [r]

        r = etree.Element(_tag("r"))
        t = etree.SubElement(r, _tag("t"))
        t.text = text
        return [r]

    if tag == "mtext":
        # Text content
        text = _text_of(node)
        r = etree.Element(_tag("r"))
        t = etree.SubElement(r, _tag("t"))
        t.text = text
        return [r]

    if tag == "mfrac":
        # Fraction: <m:f><m:num>...</m:num><m:den>...</m:den></m:f>
        children = list(node)
        if len(children) < 2:
            return _fallback_text(node)
        f = etree.Element(_tag("f"))
        num = etree.SubElement(f, _tag("num"))
        den = etree.SubElement(f, _tag("den"))
        for elem in _mml_to_omml(children[0]):
            num.append(elem)
        for elem in _mml_to_omml(children[1]):
            den.append(elem)
        return [f]

    if tag == "msqrt":
        # Square root: <m:rad><m:deg/><m:e>...</m:e></m:rad>
        rad = etree.Element(_tag("rad"))
        radpr = etree.SubElement(rad, _tag("radPr"))
        deghide = etree.SubElement(radpr, _tag("degHide"))
        deghide.set(_tag("val"), "1")
        etree.SubElement(rad, _tag("deg"))
        e = etree.SubElement(rad, _tag("e"))
        for child in node:
            for elem in _mml_to_omml(child):
                e.append(elem)
        return [rad]

    if tag == "mroot":
        # n-th root: <m:rad><m:deg>index</m:deg><m:e>radicand</m:e></m:rad>
        children = list(node)
        if len(children) < 2:
            return _fallback_text(node)
        rad = etree.Element(_tag("rad"))
        deg = etree.SubElement(rad, _tag("deg"))
        for elem in _mml_to_omml(children[1]):
            deg.append(elem)
        e = etree.SubElement(rad, _tag("e"))
        for elem in _mml_to_omml(children[0]):
            e.append(elem)
        return [rad]

    if tag == "msub":
        # Subscript: <m:sSub><m:e>base</m:e><m:sub>sub</m:sub></m:sSub>
        children = list(node)
        if len(children) < 2:
            return _fallback_text(node)
        ssub = etree.Element(_tag("sSub"))
        e = etree.SubElement(ssub, _tag("e"))
        sub = etree.SubElement(ssub, _tag("sub"))
        for elem in _mml_to_omml(children[0]):
            e.append(elem)
        for elem in _mml_to_omml(children[1]):
            sub.append(elem)
        return [ssub]

    if tag == "msup":
        # Superscript: <m:sSup><m:e>base</m:e><m:sup>sup</m:sup></m:sSup>
        children = list(node)
        if len(children) < 2:
            return _fallback_text(node)
        ssup = etree.Element(_tag("sSup"))
        e = etree.SubElement(ssup, _tag("e"))
        sup = etree.SubElement(ssup, _tag("sup"))
        for elem in _mml_to_omml(children[0]):
            e.append(elem)
        for elem in _mml_to_omml(children[1]):
            sup.append(elem)
        return [ssup]

    if tag == "msubsup":
        # Sub-superscript: <m:sSubSup><m:e>base</m:e><m:sub>sub</m:sub><m:sup>sup</m:sup>
        children = list(node)
        if len(children) < 3:
            return _fallback_text(node)
        ssubsup = etree.Element(_tag("sSubSup"))
        e = etree.SubElement(ssubsup, _tag("e"))
        sub = etree.SubElement(ssubsup, _tag("sub"))
        sup = etree.SubElement(ssubsup, _tag("sup"))
        for elem in _mml_to_omml(children[0]):
            e.append(elem)
        for elem in _mml_to_omml(children[1]):
            sub.append(elem)
        for elem in _mml_to_omml(children[2]):
            sup.append(elem)
        return [ssubsup]

    if tag == "munder":
        # Under: <m:sPre><m:e>base</m:e><m:lim>under</m:lim></m:sPre>
        # (approximation using sPre)
        children = list(node)
        if len(children) < 2:
            return _fallback_text(node)
        spre = etree.Element(_tag("sPre"))
        e = etree.SubElement(spre, _tag("e"))
        lim = etree.SubElement(spre, _tag("lim"))
        for elem in _mml_to_omml(children[0]):
            e.append(elem)
        for elem in _mml_to_omml(children[1]):
            lim.append(elem)
        return [spre]

    if tag == "mover":
        # Over: <m:sPre><m:lim>over</m:lim><m:e>base</m:e></m:sPre>
        children = list(node)
        if len(children) < 2:
            return _fallback_text(node)
        spre = etree.Element(_tag("sPre"))
        lim = etree.SubElement(spre, _tag("lim"))
        e = etree.SubElement(spre, _tag("e"))
        for elem in _mml_to_omml(children[1]):
            lim.append(elem)
        for elem in _mml_to_omml(children[0]):
            e.append(elem)
        return [spre]

    if tag == "mfenced":
        # Fenced: <m:d><m:dPr><m:begChr/><m:endChr/></m:dPr><m:e>...</m:e></m:d>
        open_ch = node.get("open", "(")
        close_ch = node.get("close", ")")
        d = etree.Element(_tag("d"))
        dpr = etree.SubElement(d, _tag("dPr"))
        beg = etree.SubElement(dpr, _tag("begChr"))
        beg.set(_tag("val"), open_ch)
        end = etree.SubElement(dpr, _tag("endChr"))
        end.set(_tag("val"), close_ch)
        for child in node:
            e = etree.SubElement(d, _tag("e"))
            for elem in _mml_to_omml(child):
                e.append(elem)
        return [d]

    if tag == "mtable":
        # Table/matrix: <m:m><m:mr><m:e>...</m:e></m:mr></m:m>
        m = etree.Element(_tag("m"))
        for row in node:
            row_tag = row.tag.split("}")[-1] if "}" in row.tag else row.tag
            if row_tag in ("mtr", "mlabeledtr"):
                mr = etree.SubElement(m, _tag("mr"))
                for cell in row:
                    cell_tag = cell.tag.split("}")[-1] if "}" in cell.tag else cell.tag
                    if cell_tag == "mtd":
                        me = etree.SubElement(mr, _tag("e"))
                        for elem in _mml_to_omml(cell):
                            me.append(elem)
        return [m]

    if tag == "mtd":
        # Table cell: recurse into children
        results = []
        for child in node:
            results.extend(_mml_to_omml(child))
        return results

    if tag == "mstyle":
        # Style wrapper: just recurse
        results = []
        for child in node:
            results.extend(_mml_to_omml(child))
        return results

    if tag == "mspace":
        # Space: add a space character
        r = etree.Element(_tag("r"))
        t = etree.SubElement(r, _tag("t"))
        t.text = " "
        return [r]

    if tag == "ms":
        # String literal
        text = _text_of(node)
        r = etree.Element(_tag("r"))
        t = etree.SubElement(r, _tag("t"))
        t.text = text
        return [r]

    if tag == "semantics":
        # Annotation wrapper: process first child (the presentation MathML)
        children = list(node)
        if children:
            return _mml_to_omml(children[0])
        return []

    if tag in ("annotation", "annotation-xml"):
        return []

    # Fallback: extract text
    return _fallback_text(node)


def _fallback_text(node: ET.Element) -> list[etree._Element]:
    """Fallback: render the MathML subtree as a plain text run."""
    text = _text_of(node)
    if not text.strip():
        return []
    r = etree.Element(_tag("r"))
    t = etree.SubElement(r, _tag("t"))
    t.text = text
    return [r]


# ── Public API ──────────────────────────────────────────────────────────────

def latex_to_omml(latex: str, *, display: bool = True) -> etree._Element:
    """Convert a LaTeX math string to an OMML ``oMath`` element.

    Parameters
    ----------
    latex : str
        LaTeX math string (without surrounding ``$`` or ``\\[``).
    display : bool
        If True, wrap in ``oMathPara`` (display/block equation).
        If False, return bare ``oMath`` (inline equation).

    Returns
    -------
    lxml.etree._Element
        The ``m:oMathPara`` or ``m:oMath`` element ready to be appended
        to a ``CT_P`` (paragraph) element.

    Raises
    ------
    ValueError
        If latex2mathml fails to convert the input.
    """
    from latex2mathml.converter import convert

    mml_str = convert(latex)
    root = ET.fromstring(mml_str)
    omml_children = _mml_to_omml(root)

    if display:
        omath_para = etree.Element(_tag("oMathPara"))
        omath = etree.SubElement(omath_para, _tag("oMath"))
    else:
        omath_para = etree.Element(_tag("oMath"))
        omath = omath_para

    for elem in omml_children:
        omath.append(elem)

    return omath_para


def insert_latex_equation(paragraph, latex: str, *, display: bool = True) -> None:
    """Insert a LaTeX equation into a python-docx Paragraph.

    Parameters
    ----------
    paragraph : docx.text.paragraph.Paragraph
        The target paragraph.
    latex : str
        LaTeX math string.
    display : bool
        If True, insert as display (block) equation.
    """
    omml_elem = latex_to_omml(latex, display=display)
    paragraph._element.append(omml_elem)
