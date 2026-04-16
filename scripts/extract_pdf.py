"""
PDF文本提取工具

用于从PDF文件中提取文本内容，保留章节结构。
支持：PDF文件、文本内容、arXiv ID

依赖：PyPDF2（或pypdf）
"""

import re
import sys
from typing import Dict, List, Optional


def extract_from_pdf(file_path: str) -> Dict[str, str]:
    """
    从PDF文件提取文本内容

    Args:
        file_path: PDF文件路径

    Returns:
        包含文本内容和元数据的字典
    """
    try:
        import PyPDF2
    except ImportError:
        print("错误：需要安装PyPDF2库")
        print("请运行：pip install PyPDF2")
        sys.exit(1)

    result = {
        'text': '',
        'pages': [],
        'metadata': {}
    }

    with open(file_path, 'rb') as file:
        reader = PyPDF2.PdfReader(file)

        # 提取元数据
        if reader.metadata:
            result['metadata'] = {
                'title': reader.metadata.get('/Title', ''),
                'author': reader.metadata.get('/Author', ''),
                'subject': reader.metadata.get('/Subject', ''),
            }

        # 提取每一页的文本
        for page_num, page in enumerate(reader.pages):
            page_text = page.extract_text()
            result['pages'].append({
                'page_number': page_num + 1,
                'text': page_text
            })
            result['text'] += page_text + '\n\n'

    return result


def extract_text_from_file(file_path: str) -> str:
    """
    从文本文件提取内容

    Args:
        file_path: 文本文件路径

    Returns:
        文本内容
    """
    with open(file_path, 'r', encoding='utf-8') as f:
        return f.read()


def detect_structure(text: str) -> Dict[str, str]:
    """
    检测论文结构

    Args:
        text: 论文全文

    Returns:
        各章节的文本内容
    """
    structure = {
        'abstract': '',
        'introduction': '',
        'related_work': '',
        'method': '',
        'experiments': '',
        'conclusion': '',
        'references': ''
    }

    # 定义章节标题的正则表达式模式
    patterns = {
        'abstract': r'(?:Abstract|ABSTRACT)\s*\n(.*?)(?=\n\s*(?:Introduction|1\.|I\.))',
        'introduction': r'(?:Introduction|INTRODUCTION|1\.\\s*Introduction)\s*\n(.*?)(?=\n\s*(?:Related Work|2\.|II\.|Method|Methodology))',
        'related_work': r'(?:Related Work|RELATED WORK|2\.\\s*Related Work)\s*\n(.*?)(?=\n\s*(?:Method|3\.|III\.|Methodology))',
        'method': r'(?:Method|METHOD|Methodology|METHODOLOGY|3\.\\s*Method(?:ology)?)\s*\n(.*?)(?=\n\s*(?:Experiments|4\.|IV\.|Experiments|Experimental Results))',
        'experiments': r'(?:Experiments|EXPERIMENTS|4\.\\s*Experiments)\s*\n(.*?)(?=\n\s*(?:Conclusion|5\.|V\.|Conclusions))',
        'conclusion': r'(?:Conclusion|CONCLUSION|5\.\\s*Conclusion)\s*\n(.*?)(?=\n\s*(?:References|References))',
        'references': r'(?:References|REFERENCES)\s*\n(.*)'
    }

    for section, pattern in patterns.items():
        match = re.search(pattern, text, re.DOTALL | re.MULTILINE)
        if match:
            structure[section] = match.group(1).strip()

    return structure


def extract_arxiv_id(arxiv_url: str) -> str:
    """
    从arXiv URL提取arXiv ID

    Args:
        arxiv_url: arXiv链接

    Returns:
        arXiv ID（如：2304.xxxxx）
    """
    # 支持多种arXiv URL格式
    patterns = [
        r'arxiv\.org/abs/(\d+\.\d+)',
        r'arxiv\.org/pdf/(\d+\.\d+)',
        r'arxiv\.org/abs/(\d+\.\d+)v\d+',
    ]

    for pattern in patterns:
        match = re.search(pattern, arxiv_url)
        if match:
            return match.group(1)

    raise ValueError(f"无法从URL提取arXiv ID: {arxiv_url}")


def format_paper_text(raw_text: str) -> str:
    """
    格式化论文文本，修复常见提取问题

    Args:
        raw_text: 原始提取的文本

    Returns:
        格式化后的文本
    """
    # 修复连字符换行
    text = re.sub(r'-\n\s*', '', raw_text)

    # 修复多余的空白行
    text = re.sub(r'\n\s*\n\s*\n', '\n\n', text)

    # 修复页眉页脚（简单启发式）
    lines = text.split('\n')
    filtered_lines = []
    for line in lines:
        # 跳过可能的页码行
        if re.match(r'^\d+\s*$', line.strip()):
            continue
        # 跳过过短的行（可能是页眉）
        if len(line.strip()) < 20 and line.strip():
            # 可能是页眉，保留
            filtered_lines.append(line)
        else:
            filtered_lines.append(line)

    return '\n'.join(filtered_lines)


def main():
    """命令行接口"""
    if len(sys.argv) < 2:
        print("用法：")
        print("  PDF文件：python extract_pdf.py <文件路径.pdf>")
        print("  文本文件：python extract_pdf.py --text <文件路径.txt>")
        print("  arXiv URL：python extract_pdf.py --arxiv <arXiv URL>")
        sys.exit(1)

    arg = sys.argv[1]

    if arg == '--text' and len(sys.argv) == 3:
        # 文本文件
        text = extract_text_from_file(sys.argv[2])
        print(text)

    elif arg == '--arxiv' and len(sys.argv) == 3:
        # arXiv URL
        arxiv_id = extract_arxiv_id(sys.argv[2])
        print(f"arXiv ID: {arxiv_id}")
        print("注意：需要手动下载PDF或使用arXiv API")

    else:
        # PDF文件（默认）
        result = extract_from_pdf(arg)

        print("=== 元数据 ===")
        for key, value in result['metadata'].items():
            print(f"{key}: {value}")

        print("\n=== 文本内容 ===")
        print(result['text'])


if __name__ == '__main__':
    main()
