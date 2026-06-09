"""
Markdown格式论文提取工具

用于从markdown格式的论文中提取结构化内容。
支持：标题识别、章节提取、公式提取、表格解析等。

依赖：无（仅使用标准库）
"""

import re
from typing import Dict, List, Optional, Tuple


class MarkdownPaperParser:
    """Markdown论文解析器"""

    def __init__(self, markdown_text: str):
        """
        初始化解析器

        Args:
            markdown_text: markdown格式的论文文本
        """
        self.text = markdown_text
        self.lines = markdown_text.split('\n')

    def parse(self) -> Dict[str, any]:
        """
        解析markdown论文

        Returns:
            包含论文结构和内容的字典
        """
        result = {
            'metadata': self._extract_metadata(),
            'structure': self._extract_structure(),
            'formulas': self._extract_formulas(),
            'tables': self._extract_tables(),
            'full_text': self.text
        }
        return result

    def _extract_metadata(self) -> Dict[str, str]:
        """
        提取论文元数据

        Returns:
            包含标题、作者、摘要等元数据的字典
        """
        metadata = {
            'title': '',
            'authors': '',
            'abstract': '',
            'keywords': []
        }

        # 提取标题（第一个一级标题）
        for line in self.lines:
            if line.startswith('# '):
                metadata['title'] = line[2:].strip()
                break

        # 提取作者信息（常见模式）
        author_patterns = [
            r'\*\*作者\*\*:\s*(.+)',
            r'Authors?:\s*(.+)',
            r'\*\*Authors?\*\*:\s*(.+)'
        ]
        for line in self.lines:
            for pattern in author_patterns:
                match = re.match(pattern, line, re.IGNORECASE)
                if match:
                    metadata['authors'] = match.group(1).strip()
                    break
            if metadata['authors']:
                break

        # 提取摘要
        abstract = self._extract_section('摘要', 'Abstract')
        if abstract:
            metadata['abstract'] = abstract

        # 提取关键词
        keyword_patterns = [
            r'\*\*关键词\*\*:\s*(.+)',
            r'Keywords?:\s*(.+)',
            r'\*\*Keywords?\*\*:\s*(.+)'
        ]
        for line in self.lines:
            for pattern in keyword_patterns:
                match = re.match(pattern, line, re.IGNORECASE)
                if match:
                    keywords_str = match.group(1).strip()
                    # 分割关键词（常见分隔符：,、；;）
                    keywords = re.split(r'[,，、；;]', keywords_str)
                    metadata['keywords'] = [k.strip() for k in keywords if k.strip()]
                    break
            if metadata['keywords']:
                break

        return metadata

    def _extract_structure(self) -> Dict[str, str]:
        """
        提取论文结构（章节）

        Returns:
            章节名称到内容的映射
        """
        structure = {}

        # 定义常见章节名称（中英文）
        sections = {
            'introduction': ['引言', '简介', 'Introduction', '1.'],
            'related_work': ['相关工作', 'Related Work', '2.'],
            'method': ['方法', '方法论', 'Method', 'Methodology', '3.'],
            'experiments': ['实验', 'Experiments', 'Experimental Results', '4.'],
            'conclusion': ['结论', 'Conclusion', '5.'],
            'references': ['参考文献', 'References', 'Bibliography']
        }

        for key, names in sections.items():
            for name in names:
                content = self._extract_section(name)
                if content:
                    structure[key] = content
                    break

        return structure

    def _extract_section(self, *section_names: str) -> str:
        """
        提取指定章节的内容

        Args:
            *section_names: 章节名称（多个候选名称）

        Returns:
            章节内容
        """
        # 构建正则表达式模式
        patterns = []
        for name in section_names:
            # 支持多种markdown标题格式
            patterns.extend([
                rf'^#+\s*{re.escape(name)}\s*$',
                rf'^{re.escape(name)}\s*$',
            ])

        # 查找章节开始位置
        start_idx = None
        start_line_num = None
        for i, line in enumerate(self.lines):
            for pattern in patterns:
                if re.match(pattern, line, re.IGNORECASE):
                    start_idx = i
                    start_line_num = i
                    break
            if start_idx is not None:
                break

        if start_idx is None:
            return ''

        # 查找章节结束位置（下一个同级或更高级标题）
        end_idx = len(self.lines)
        for i in range(start_idx + 1, len(self.lines)):
            line = self.lines[i]
            # 检查是否是标题
            if re.match(r'^#+\s', line):
                # 获取当前章节的标题级别
                current_level = len(re.match(r'^(#+)', self.lines[start_idx]).group(1))
                next_level = len(re.match(r'^(#+)', line).group(1))
                # 如果是同级或更高级标题，则结束
                if next_level <= current_level:
                    end_idx = i
                    break

        # 提取内容
        content_lines = self.lines[start_idx:end_idx]
        # 移除标题行
        if content_lines and re.match(r'^#+\s', content_lines[0]):
            content_lines = content_lines[1:]

        content = '\n'.join(content_lines).strip()
        return content

    def _extract_formulas(self) -> List[Dict[str, str]]:
        """
        提取所有数学公式

        Returns:
            公式列表，每个公式包含类型、LaTeX代码、位置
        """
        formulas = []

        # 行内公式：$...$
        inline_pattern = r'\$([^$]+)\$'
        for i, line in enumerate(self.lines):
            matches = re.finditer(inline_pattern, line)
            for match in matches:
                formulas.append({
                    'type': 'inline',
                    'latex': match.group(1),
                    'line': i + 1,
                    'context': line.strip()
                })

        # 块级公式：$$...$$
        block_pattern = r'\$\$([^$]+)\$\$'
        block_started = False
        block_start = 0
        block_lines = []

        for i, line in enumerate(self.lines):
            if not block_started:
                if re.search(block_pattern, line):
                    # 单行块级公式
                    match = re.search(block_pattern, line)
                    formulas.append({
                        'type': 'block',
                        'latex': match.group(1).strip(),
                        'line': i + 1,
                        'context': line.strip()
                    })
                elif '$$' in line:
                    # 多行块级公式开始
                    block_started = True
                    block_start = i
                    block_lines = [line]
            else:
                block_lines.append(line)
                if '$$' in line:
                    # 块级公式结束
                    block_text = '\n'.join(block_lines)
                    match = re.search(r'\$\$(.+?)\$\$', block_text, re.DOTALL)
                    if match:
                        formulas.append({
                            'type': 'block',
                            'latex': match.group(1).strip(),
                            'line': block_start + 1,
                            'context': f'Lines {block_start + 1}-{i + 1}'
                        })
                    block_started = False
                    block_lines = []

        return formulas

    def _extract_tables(self) -> List[Dict[str, any]]:
        """
        提取所有表格

        Returns:
            表格列表，每个表格包含表头和数据
        """
        tables = []
        in_table = False
        table_lines = []
        table_start = 0

        for i, line in enumerate(self.lines):
            # 检测表格开始（包含|的行）
            if '|' in line and not in_table:
                in_table = True
                table_start = i
                table_lines = [line]
            elif in_table:
                if '|' in line:
                    table_lines.append(line)
                else:
                    # 表格结束
                    if table_lines:
                        table = self._parse_table(table_lines)
                        if table:
                            tables.append({
                                'lines': [table_start + 1, i],
                                'headers': table.get('headers', []),
                                'data': table.get('data', []),
                                'raw': '\n'.join(table_lines)
                            })
                    in_table = False
                    table_lines = []

        # 处理最后一个表格
        if in_table and table_lines:
            table = self._parse_table(table_lines)
            if table:
                tables.append({
                    'lines': [table_start + 1, len(self.lines)],
                    'headers': table.get('headers', []),
                    'data': table.get('data', []),
                    'raw': '\n'.join(table_lines)
                })

        return tables

    def _parse_table(self, table_lines: List[str]) -> Optional[Dict[str, any]]:
        """
        解析表格

        Args:
            table_lines: 表格行列表

        Returns:
            包含headers和data的字典
        """
        if not table_lines:
            return None

        # 移除首尾的|
        rows = []
        for line in table_lines:
            # 跳过分隔线（如 |---|---|）
            if re.match(r'^\|?\s*[\-|:\s]+\|?\s*$', line):
                continue
            # 分割列
            cells = [cell.strip() for cell in line.split('|')]
            # 移除空的首尾元素
            if cells and cells[0] == '':
                cells = cells[1:]
            if cells and cells[-1] == '':
                cells = cells[:-1]
            if cells:
                rows.append(cells)

        if not rows:
            return None

        # 第一行作为表头
        headers = rows[0]
        # 其余作为数据
        data = rows[1:] if len(rows) > 1 else []

        return {
            'headers': headers,
            'data': data
        }

    def get_section_content(self, section_name: str) -> str:
        """
        获取指定章节的内容（便捷方法）

        Args:
            section_name: 章节名称

        Returns:
            章节内容
        """
        return self._extract_section(section_name)

    def get_all_headings(self) -> List[Dict[str, any]]:
        """
        获取所有标题

        Returns:
            标题列表，包含级别、文本、行号
        """
        headings = []
        for i, line in enumerate(self.lines):
            match = re.match(r'^(#+)\s+(.+)$', line)
            if match:
                level = len(match.group(1))
                text = match.group(2).strip()
                headings.append({
                    'level': level,
                    'text': text,
                    'line': i + 1
                })
        return headings


def extract_from_markdown(file_path: str) -> Dict[str, any]:
    """
    从markdown文件提取论文内容

    Args:
        file_path: markdown文件路径

    Returns:
        解析后的论文内容
    """
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    parser = MarkdownPaperParser(content)
    return parser.parse()


def main():
    """命令行接口"""
    import sys

    if len(sys.argv) < 2:
        print("用法：python extract_markdown.py <文件路径.md>")
        sys.exit(1)

    file_path = sys.argv[1]

    result = extract_from_markdown(file_path)

    print("=== 论文元数据 ===")
    for key, value in result['metadata'].items():
        print(f"{key}: {value}")

    print("\n=== 章节结构 ===")
    for section, content in result['structure'].items():
        print(f"\n{section}:")
        print(content[:200] + "..." if len(content) > 200 else content)

    print(f"\n=== 公式 ({len(result['formulas'])}个) ===")
    for i, formula in enumerate(result['formulas'][:5]):  # 只显示前5个
        print(f"\n公式{i+1} ({formula['type']}):")
        print(f"  LaTeX: {formula['latex']}")
        print(f"  位置: 第{formula['line']}行")

    if len(result['formulas']) > 5:
        print(f"\n... 还有{len(result['formulas']) - 5}个公式")

    print(f"\n=== 表格 ({len(result['tables'])}个) ===")
    for i, table in enumerate(result['tables']):
        print(f"\n表格{i+1}:")
        print(f"  表头: {table['headers']}")
        print(f"  数据行数: {len(table['data'])}")


if __name__ == '__main__':
    main()
