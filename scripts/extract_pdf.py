"""
PDF文本提取工具 - mineru-open-api包装器

用于从PDF文件中提取文本内容，保留章节结构、公式、表格。
支持：PDF文件、arXiv URL、直接下载

依赖：mineru-open-api（https://mineru.net/）
"""

import os
import re
import sys
import subprocess
import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any


def check_mineru_available() -> bool:
    """
    检查mineru-open-api是否可用

    Returns:
        bool: mineru-open-api是否可用
    """
    try:
        result = subprocess.run(
            ['mineru-open-api', '--version'],
            capture_output=True,
            text=True,
            timeout=5
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def get_pdf_info(file_path: str) -> Tuple[float, int]:
    """
    获取PDF文件信息（大小和页数）

    Args:
        file_path: PDF文件路径

    Returns:
        (文件大小MB, 页数)
    """
    # 获取文件大小
    size_bytes = os.path.getsize(file_path)
    size_mb = size_bytes / (1024 * 1024)

    # 尝试获取页数（简单方法：通过文件大小估算）
    # 更准确的方法需要使用PyPDF2，但这里我们简化处理
    # 平均每页约100KB
    estimated_pages = int(size_bytes / (100 * 1024))

    return size_mb, estimated_pages


def should_use_extract_mode(file_path: str, user_pref: Optional[str] = None) -> bool:
    """
    判断是否应该使用extract模式（而非flash-extract）

    Args:
        file_path: PDF文件路径
        user_pref: 用户偏好模式（'flash'或'extract'）

    Returns:
        bool: True表示使用extract模式，False表示使用flash-extract模式
    """
    # 用户明确指定模式
    if user_pref:
        return user_pref == 'extract'

    size_mb, estimated_pages = get_pdf_info(file_path)

    # 根据文件大小和页数判断
    # flash-extract限制：10MB, 20页
    if size_mb > 10 or estimated_pages > 20:
        return True

    return False


def extract_from_pdf(file_path: str, mode: Optional[str] = None, output_dir: Optional[str] = None) -> Dict[str, Any]:
    """
    从PDF文件提取文本内容（使用mineru-open-api）

    Args:
        file_path: PDF文件路径
        mode: 提取模式（'flash'或'extract'，None表示自动选择）
        output_dir: 输出目录（None表示PDF同目录）

    Returns:
        包含文本内容和元数据的字典
    """
    if not check_mineru_available():
        raise RuntimeError(
            "mineru-open-api未安装或不在PATH中。\n"
            "请访问 https://mineru.net/ 安装，或使用: pip install mineru-open-api"
        )

    # 检查文件是否存在
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"PDF文件不存在: {file_path}")

    # 确定输出目录
    if output_dir is None:
        output_dir = os.path.dirname(file_path)
    output_dir = os.path.abspath(output_dir)

    # 确保输出目录存在
    os.makedirs(output_dir, exist_ok=True)

    # 选择提取模式
    use_extract = should_use_extract_mode(file_path, mode)
    mode_name = 'extract' if use_extract else 'flash-extract'

    print(f"使用 {mode_name} 模式提取PDF...")

    # 构建命令
    if use_extract:
        # extract模式：支持表格、公式、OCR
        cmd = [
            'mineru-open-api',
            'extract',
            file_path,
            '-o', output_dir,
            '-f', 'md'
        ]
    else:
        # flash-extract模式：快速、免token
        cmd = [
            'mineru-open-api',
            'flash-extract',
            file_path,
            '-o', output_dir
        ]

    # 执行命令
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True,
            timeout=300  # 5分钟超时
        )

        # 查找输出的markdown文件
        pdf_name = Path(file_path).stem
        md_file = os.path.join(output_dir, f'{pdf_name}.md')

        if not os.path.exists(md_file):
            # 尝试查找可能的输出文件
            md_files = list(Path(output_dir).glob('*.md'))
            if md_files:
                md_file = str(md_files[0])
            else:
                raise FileNotFoundError(
                    f"未找到输出的markdown文件。"
                    f"预期位置: {md_file}\n"
                    f"mineru输出: {result.stdout}"
                )

        # 读取markdown内容
        with open(md_file, 'r', encoding='utf-8') as f:
            md_content = f.read()

        return {
            'text': md_content,
            'markdown_file': md_file,
            'mode': mode_name,
            'metadata': {
                'source': file_path,
                'extractor': 'mineru-open-api',
                'mode': mode_name
            }
        }

    except subprocess.CalledProcessError as e:
        raise RuntimeError(
            f"mineru-open-api执行失败:\n"
            f"命令: {' '.join(cmd)}\n"
            f"错误: {e.stderr}"
        )
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"PDF提取超时（5分钟），文件可能过大或复杂")


def extract_from_arxiv(arxiv_url: str, output_dir: Optional[str] = None) -> Dict[str, Any]:
    """
    从arXiv URL提取论文内容

    Args:
        arxiv_url: arXiv论文URL
        output_dir: 输出目录（None表示当前目录）

    Returns:
        包含文本内容和元数据的字典
    """
    if not check_mineru_available():
        raise RuntimeError(
            "mineru-open-api未安装或不在PATH中。\n"
            "请访问 https://mineru.net/ 安装，或使用: pip install mineru-open-api"
        )

    # 提取arXiv ID
    arxiv_id = extract_arxiv_id(arxiv_url)

    # 确定输出目录
    if output_dir is None:
        output_dir = os.getcwd()
    output_dir = os.path.abspath(output_dir)

    # 确保输出目录存在
    os.makedirs(output_dir, exist_ok=True)

    print(f"从arXiv下载并提取论文: {arxiv_id}")

    # 构建命令
    pdf_url = f'https://arxiv.org/pdf/{arxiv_id}.pdf'
    cmd = [
        'mineru-open-api',
        'extract',
        pdf_url,
        '-o', output_dir,
        '-f', 'md'
    ]

    # 执行命令
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True,
            timeout=300  # 5分钟超时
        )

        # 查找输出的markdown文件
        md_file = os.path.join(output_dir, f'{arxiv_id}.md')

        if not os.path.exists(md_file):
            # 尝试查找可能的输出文件
            md_files = list(Path(output_dir).glob('*.md'))
            if md_files:
                md_file = str(md_files[0])
            else:
                raise FileNotFoundError(
                    f"未找到输出的markdown文件。"
                    f"预期位置: {md_file}\n"
                    f"mineru输出: {result.stdout}"
                )

        # 读取markdown内容
        with open(md_file, 'r', encoding='utf-8') as f:
            md_content = f.read()

        return {
            'text': md_content,
            'markdown_file': md_file,
            'arxiv_id': arxiv_id,
            'arxiv_url': arxiv_url,
            'metadata': {
                'source': pdf_url,
                'extractor': 'mineru-open-api',
                'mode': 'extract',
                'arxiv_id': arxiv_id
            }
        }

    except subprocess.CalledProcessError as e:
        raise RuntimeError(
            f"mineru-open-api执行失败:\n"
            f"命令: {' '.join(cmd)}\n"
            f"错误: {e.stderr}"
        )
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"arXiv论文提取超时（5分钟）")


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


def main():
    """命令行接口"""
    if len(sys.argv) < 2:
        print("PDF文本提取工具 - mineru-open-api包装器")
        print("")
        print("用法：")
        print("  PDF文件：python extract_pdf.py <文件路径.pdf>")
        print("  PDF文件（指定模式）：python extract_pdf.py <文件路径.pdf> --mode <flash|extract>")
        print("  PDF文件（指定输出目录）：python extract_pdf.py <文件路径.pdf> --output <目录>")
        print("  arXiv URL：python extract_pdf.py --arxiv <arXiv URL>")
        print("")
        print("模式说明：")
        print("  flash-extract（默认）：快速、免token，适合<10MB且<20页的简单论文")
        print("  extract：精确、需token，支持表格/公式/OCR，适合复杂或大型论文")
        print("")
        print("示例：")
        print("  python extract_pdf.py paper.pdf")
        print("  python extract_pdf.py paper.pdf --mode extract")
        print("  python extract_pdf.py --arxiv https://arxiv.org/abs/2304.xxxxx")
        sys.exit(1)

    # 解析参数
    args = sys.argv[1:]

    if '--arxiv' in args:
        # arXiv URL模式
        arxiv_idx = args.index('--arxiv')
        if arxiv_idx + 1 >= len(args):
            print("错误：--arxiv 需要指定URL")
            sys.exit(1)

        arxiv_url = args[arxiv_idx + 1]
        output_dir = None

        # 检查是否有输出目录参数
        if '--output' in args:
            output_idx = args.index('--output')
            if output_idx + 1 >= len(args):
                print("错误：--output 需要指定目录")
                sys.exit(1)
            output_dir = args[output_idx + 1]

        try:
            result = extract_from_arxiv(arxiv_url, output_dir)
            print(f"\n✓ 成功提取arXiv论文!")
            print(f"  arXiv ID: {result['arxiv_id']}")
            print(f"  输出文件: {result['markdown_file']}")
            print(f"  使用模式: {result['metadata']['mode']}")

        except Exception as e:
            print(f"\n✗ 错误: {e}")
            sys.exit(1)

    else:
        # PDF文件模式
        pdf_file = args[0]

        # 解析可选参数
        mode = None
        output_dir = None

        if '--mode' in args:
            mode_idx = args.index('--mode')
            if mode_idx + 1 >= len(args):
                print("错误：--mode 需要指定模式（flash或extract）")
                sys.exit(1)
            mode = args[mode_idx + 1]
            if mode not in ['flash', 'extract']:
                print("错误：模式必须是 'flash' 或 'extract'")
                sys.exit(1)

        if '--output' in args:
            output_idx = args.index('--output')
            if output_idx + 1 >= len(args):
                print("错误：--output 需要指定目录")
                sys.exit(1)
            output_dir = args[output_idx + 1]

        try:
            result = extract_from_pdf(pdf_file, mode, output_dir)
            print(f"\n✓ 成功提取PDF文件!")
            print(f"  源文件: {result['metadata']['source']}")
            print(f"  输出文件: {result['markdown_file']}")
            print(f"  使用模式: {result['metadata']['mode']}")
            print(f"  文件大小: {os.path.getsize(pdf_file) / (1024*1024):.2f} MB")

        except Exception as e:
            print(f"\n✗ 错误: {e}")
            sys.exit(1)


if __name__ == '__main__':
    main()
