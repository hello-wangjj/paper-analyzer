"""
PDF文本提取工具 - 双引擎（PaddleOCR AI Studio API + mineru-open-api 备选）

用于从PDF文件中提取文本内容，保留章节结构、公式、表格和图片。
支持：本地PDF文件、arXiv URL、HTTP文件链接

引擎选择（--engine 参数）：
  paddleocr（默认）: PaddleOCR-VL-1.5 HTTP API，依赖 requests
  mineru: mineru-open-api CLI，依赖 mineru-open-api 已安装

依赖：
  paddleocr 引擎: pip install requests
  mineru 引擎: pip install mineru-open-api (https://mineru.net/)
"""

import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

# ─── PaddleOCR AI Studio API 配置 ───

POCR_JOB_URL = "https://paddleocr.aistudio-app.com/api/v2/ocr/jobs"
POCR_TOKEN = os.environ.get("PADDLEOCR_TOKEN", "")
POCR_MODEL = "PaddleOCR-VL-1.5"

DEFAULT_POLL_INTERVAL = 5  # 秒
DEFAULT_TIMEOUT = 600  # 10分钟总超时


# ═══════════════════════════════════════════════════════════════
# PaddleOCR AI Studio 引擎
# ═══════════════════════════════════════════════════════════════


def _pocr_submit_job(file_path: str) -> str:
    """提交OCR任务到PaddleOCR AI Studio API，返回 jobId。"""
    if not POCR_TOKEN:
        raise RuntimeError(
            "PADDLEOCR_TOKEN 未设置。请在环境变量中配置 API Token：\n"
            "  Windows: set PADDLEOCR_TOKEN=<your_token>\n"
            "  Linux/Mac: export PADDLEOCR_TOKEN=<your_token>"
        )
    headers = {"Authorization": f"bearer {POCR_TOKEN}"}
    optional_payload = {
        "useDocOrientationClassify": False,
        "useDocUnwarping": False,
        "useChartRecognition": False,
    }

    if file_path.startswith("http"):
        headers["Content-Type"] = "application/json"
        payload = {
            "fileUrl": file_path,
            "model": POCR_MODEL,
            "optionalPayload": optional_payload,
        }
        resp = requests.post(POCR_JOB_URL, json=payload, headers=headers)
    else:
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"文件不存在: {file_path}")
        data = {"model": POCR_MODEL, "optionalPayload": json.dumps(optional_payload)}
        with open(file_path, "rb") as f:
            resp = requests.post(POCR_JOB_URL, headers=headers, data=data, files={"file": f})

    if resp.status_code != 200:
        raise RuntimeError(f"PaddleOCR API 提交失败 (HTTP {resp.status_code}): {resp.text}")

    return resp.json()["data"]["jobId"]


def _pocr_poll_until_done(job_id: str, timeout: int = DEFAULT_TIMEOUT) -> Dict[str, Any]:
    """轮询等待OCR任务完成，返回 data 对象。"""
    headers = {"Authorization": f"bearer {POCR_TOKEN}"}
    start = time.time()

    while True:
        if time.time() - start > timeout:
            raise RuntimeError(f"PaddleOCR 任务超时 ({timeout}s)")

        resp = requests.get(f"{POCR_JOB_URL}/{job_id}", headers=headers)
        if resp.status_code != 200:
            raise RuntimeError(f"轮询失败 (HTTP {resp.status_code}): {resp.text}")

        data = resp.json()["data"]
        state = data["state"]

        if state == "done":
            return data
        elif state == "failed":
            raise RuntimeError(f"PaddleOCR 任务失败: {data.get('errorMsg', '未知错误')}")
        elif state == "running":
            try:
                p = data["extractProgress"]
                print(f"  [PaddleOCR] 处理中... {p['extractedPages']}/{p['totalPages']} 页")
            except KeyError:
                print("  [PaddleOCR] 处理中...")

        time.sleep(DEFAULT_POLL_INTERVAL)


def _pocr_download_results(data: Dict[str, Any], output_dir: str) -> List[str]:
    """下载OCR结果（每页一个 Markdown + 图片），返回文件路径列表。"""
    jsonl_url = data["resultUrl"]["jsonUrl"]
    resp = requests.get(jsonl_url)
    resp.raise_for_status()

    os.makedirs(output_dir, exist_ok=True)
    md_files = []
    page_num = 0

    for line in resp.text.strip().split("\n"):
        line = line.strip()
        if not line:
            continue
        result = json.loads(line)["result"]
        for res in result["layoutParsingResults"]:
            md_filename = os.path.join(output_dir, f"doc_{page_num}.md")
            with open(md_filename, "w", encoding="utf-8") as f:
                f.write(res["markdown"]["text"])
            md_files.append(md_filename)

            for img_path, img_url in res["markdown"].get("images", {}).items():
                full_img_path = os.path.join(output_dir, img_path)
                os.makedirs(os.path.dirname(full_img_path), exist_ok=True)
                try:
                    img_bytes = requests.get(img_url).content
                    with open(full_img_path, "wb") as img_file:
                        img_file.write(img_bytes)
                except Exception as e:
                    print(f"  警告: 图片下载失败 {img_path}: {e}")

            for img_name, img_url in res.get("outputImages", {}).items():
                try:
                    img_resp = requests.get(img_url)
                    if img_resp.status_code == 200:
                        filename = os.path.join(output_dir, f"{img_name}_{page_num}.jpg")
                        with open(filename, "wb") as f:
                            f.write(img_resp.content)
                except Exception:
                    pass

            page_num += 1

    return md_files


def _extract_paddleocr(
    file_path: str, output_dir: str, timeout: int = DEFAULT_TIMEOUT
) -> Dict[str, Any]:
    """PaddleOCR 引擎的完整提取流程。"""
    print(f"[PaddleOCR] 提交任务: {file_path}")
    job_id = _pocr_submit_job(file_path)
    print(f"[PaddleOCR] jobId: {job_id}")

    print("[PaddleOCR] 等待处理...")
    data = _pocr_poll_until_done(job_id, timeout)
    pages = data["extractProgress"]["extractedPages"]
    print(f"[PaddleOCR] 完成, 共 {pages} 页")

    print("[PaddleOCR] 下载结果...")
    page_files = _pocr_download_results(data, output_dir)

    combined = []
    for pf in page_files:
        with open(pf, "r", encoding="utf-8") as f:
            combined.append(f.read())
    combined_text = "\n\n---\n\n".join(combined)

    # 合并文件放到 PDF 同目录下（或当前目录），不是 ocr_output 子目录
    if file_path.startswith("http"):
        combined_dir = os.getcwd()
        base_name = "remote_document"
    else:
        combined_dir = os.path.dirname(os.path.abspath(file_path))
        base_name = Path(file_path).stem
    combined_file = os.path.join(combined_dir, f"{base_name}.md")
    with open(combined_file, "w", encoding="utf-8") as f:
        f.write(combined_text)

    print(f"[PaddleOCR] 合并输出: {combined_file}")
    return {
        "text": combined_text,
        "markdown_file": combined_file,
        "page_files": page_files,
        "metadata": {
            "source": file_path,
            "extractor": "PaddleOCR-VL-1.5",
            "model": POCR_MODEL,
            "pages": pages,
            "output_dir": output_dir,
        },
    }


# ═══════════════════════════════════════════════════════════════
# mineru-open-api 备选引擎
# ═══════════════════════════════════════════════════════════════


def _check_mineru_available() -> bool:
    """检查 mineru-open-api CLI 是否可用。"""
    try:
        result = subprocess.run(
            ["mineru-open-api", "--version"],
            capture_output=True, text=True, timeout=5,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def _extract_mineru(
    file_path: str, output_dir: str, mode: Optional[str] = None
) -> Dict[str, Any]:
    """mineru-open-api 引擎的提取流程。"""
    if not _check_mineru_available():
        raise RuntimeError(
            "mineru-open-api 未安装或不在 PATH 中。\n"
            "安装：https://mineru.net/ 或 pip install mineru-open-api"
        )

    # 选择模式
    if mode is None:
        size_mb = os.path.getsize(file_path) / (1024 * 1024) if not file_path.startswith("http") else 0
        use_extract = size_mb > 10
    else:
        use_extract = mode == "extract"

    mode_name = "extract" if use_extract else "flash-extract"
    print(f"[mineru] 使用 {mode_name} 模式")

    if file_path.startswith("http"):
        cmd = ["mineru-open-api", "extract", file_path, "-o", output_dir, "-f", "md"]
    elif use_extract:
        cmd = ["mineru-open-api", "extract", file_path, "-o", output_dir, "-f", "md"]
    else:
        cmd = ["mineru-open-api", "flash-extract", file_path, "-o", output_dir]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=300)
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"mineru-open-api 执行失败:\n命令: {' '.join(cmd)}\n错误: {e.stderr}")
    except subprocess.TimeoutExpired:
        raise RuntimeError("mineru 提取超时（5分钟）")

    # 查找输出文件
    if file_path.startswith("http"):
        base_name = "remote_document"
    else:
        base_name = Path(file_path).stem
    md_file = os.path.join(output_dir, f"{base_name}.md")

    if not os.path.exists(md_file):
        md_files = list(Path(output_dir).glob("*.md"))
        if md_files:
            md_file = str(md_files[0])
        else:
            raise FileNotFoundError(
                f"未找到输出文件，预期: {md_file}\nmineru 输出: {result.stdout}"
            )

    with open(md_file, "r", encoding="utf-8") as f:
        text = f.read()

    print(f"[mineru] 输出: {md_file}")
    return {
        "text": text,
        "markdown_file": md_file,
        "page_files": [md_file],
        "metadata": {
            "source": file_path,
            "extractor": "mineru-open-api",
            "mode": mode_name,
            "output_dir": output_dir,
        },
    }


# ═══════════════════════════════════════════════════════════════
# 统一接口
# ═══════════════════════════════════════════════════════════════


def extract_from_pdf(
    file_path: str,
    output_dir: Optional[str] = None,
    engine: str = "paddleocr",
    timeout: int = DEFAULT_TIMEOUT,
    mineru_mode: Optional[str] = None,
) -> Dict[str, Any]:
    """
    从PDF文件提取文本内容。

    Args:
        file_path: PDF文件路径或HTTP URL
        output_dir: 输出目录（None = PDF同目录下 ocr_output/）
        engine: 提取引擎，"paddleocr"（默认）或 "mineru"
        timeout: PaddleOCR 超时时间（秒）
        mineru_mode: mineru 模式，"flash" 或 "extract"（None=自动）

    Returns:
        {
            'text': 完整 Markdown 文本,
            'markdown_file': 合并后文件路径,
            'page_files': 各页文件路径,
            'metadata': {...}
        }
    """
    if not file_path.startswith("http") and not os.path.exists(file_path):
        raise FileNotFoundError(f"文件不存在: {file_path}")

    if output_dir is None:
        if file_path.startswith("http"):
            output_dir = os.path.join(os.getcwd(), "ocr_output")
        else:
            output_dir = os.path.join(
                os.path.dirname(os.path.abspath(file_path)), "ocr_output"
            )
    output_dir = os.path.abspath(output_dir)

    if engine == "paddleocr":
        return _extract_paddleocr(file_path, output_dir, timeout)
    elif engine == "mineru":
        return _extract_mineru(file_path, output_dir, mineru_mode)
    else:
        raise ValueError(f"未知引擎: {engine}，可选: paddleocr, mineru")


def extract_from_arxiv(
    arxiv_url: str,
    output_dir: Optional[str] = None,
    engine: str = "paddleocr",
    timeout: int = DEFAULT_TIMEOUT,
) -> Dict[str, Any]:
    """
    从arXiv URL提取论文内容。

    Args:
        arxiv_url: arXiv论文URL（abs/pdf 均可）
        output_dir: 输出目录
        engine: 提取引擎
        timeout: 超时时间

    Returns:
        与 extract_from_pdf 相同格式，额外含 arxiv_id
    """
    arxiv_id = extract_arxiv_id(arxiv_url)
    pdf_url = f"https://arxiv.org/pdf/{arxiv_id}.pdf"

    if output_dir is None:
        output_dir = os.path.join(os.getcwd(), f"arxiv_{arxiv_id}")

    print(f"处理arXiv论文: {arxiv_id}")
    result = extract_from_pdf(pdf_url, output_dir, engine=engine, timeout=timeout)
    result["arxiv_id"] = arxiv_id
    result["arxiv_url"] = arxiv_url
    result["metadata"]["arxiv_id"] = arxiv_id
    return result


def extract_arxiv_id(arxiv_url: str) -> str:
    """从arXiv URL提取ID（如 2304.02643）。"""
    patterns = [
        r"arxiv\.org/abs/(\d+\.\d+)",
        r"arxiv\.org/pdf/(\d+\.\d+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, arxiv_url)
        if match:
            return match.group(1)
    raise ValueError(f"无法从URL提取arXiv ID: {arxiv_url}")


# ═══════════════════════════════════════════════════════════════
# 命令行入口
# ═══════════════════════════════════════════════════════════════


def main():
    """命令行接口"""
    if len(sys.argv) < 2:
        print("PDF文本提取工具 - 双引擎（PaddleOCR + mineru 备选）")
        print("")
        print("用法：")
        print("  PDF文件：      python extract_pdf.py <文件路径.pdf>")
        print("  指定引擎：     python extract_pdf.py <文件路径.pdf> --engine <paddleocr|mineru>")
        print("  指定输出目录：  python extract_pdf.py <文件路径.pdf> --output <目录>")
        print("  arXiv URL：    python extract_pdf.py --arxiv <arXiv URL>")
        print("  HTTP文件：     python extract_pdf.py <http(s)://...>")
        print("")
        print("引擎：")
        print("  paddleocr（默认）: PaddleOCR AI Studio API，依赖 requests")
        print("  mineru:           mineru-open-api CLI，需预先安装")
        print("")
        print("环境变量：")
        print("  PADDLEOCR_TOKEN: PaddleOCR API Token（默认内置）")
        sys.exit(1)

    args = sys.argv[1:]
    engine = "paddleocr"

    if "--engine" in args:
        ei = args.index("--engine")
        if ei + 1 >= len(args):
            print("错误：--engine 需要指定 paddleocr 或 mineru")
            sys.exit(1)
        engine = args[ei + 1]
        if engine not in ("paddleocr", "mineru"):
            print(f"错误：未知引擎 '{engine}'，可选: paddleocr, mineru")
            sys.exit(1)

    if "--arxiv" in args:
        ai = args.index("--arxiv")
        if ai + 1 >= len(args):
            print("错误：--arxiv 需要指定URL")
            sys.exit(1)
        arxiv_url = args[ai + 1]

        output_dir = None
        if "--output" in args:
            oi = args.index("--output")
            output_dir = args[oi + 1]

        try:
            result = extract_from_arxiv(arxiv_url, output_dir, engine=engine)
            print(f"\narXiv论文提取成功!")
            print(f"  arXiv ID: {result['arxiv_id']}")
            print(f"  引擎: {result['metadata']['extractor']}")
            print(f"  输出文件: {result['markdown_file']}")
            if "pages" in result["metadata"]:
                print(f"  总页数: {result['metadata']['pages']}")
        except Exception as e:
            print(f"\n错误: {e}")
            sys.exit(1)
    else:
        file_path = args[0]
        output_dir = None
        if "--output" in args:
            oi = args.index("--output")
            output_dir = args[oi + 1]

        try:
            result = extract_from_pdf(file_path, output_dir, engine=engine)
            print(f"\nPDF提取成功!")
            print(f"  引擎: {result['metadata']['extractor']}")
            print(f"  输出文件: {result['markdown_file']}")
            if "pages" in result["metadata"]:
                print(f"  总页数: {result['metadata']['pages']}")
        except Exception as e:
            print(f"\n错误: {e}")
            sys.exit(1)


if __name__ == "__main__":
    main()
