"""File text extraction — pure utility, not an Agent tool."""
from __future__ import annotations
from pathlib import Path

TEXT_EXTENSIONS = {
    ".txt", ".md", ".py", ".js", ".ts", ".json",
    ".csv", ".yaml", ".yml", ".xml", ".html", ".log", ".rst",
}


def extract_text(file_path: Path) -> tuple[str, str]:
    """Extract text content from *file_path*.

    Returns ``(text_content, error_message)``.  On success *error_message*
    is an empty string.
    """
    suffix = file_path.suffix.lower()

    # ---- plain text ----
    if suffix in TEXT_EXTENSIONS:
        try:
            text = file_path.read_text(encoding="utf-8", errors="replace")
            if len(text) > 50000:
                text = text[:50000] + f"\n\n[文件过长，已截断，原始长度 {len(text)} 字符]"
            return text, ""
        except Exception as exc:
            return "", f"读取失败：{exc}"

    # ---- PDF ----
    if suffix == ".pdf":
        try:
            import PyPDF2
            reader = PyPDF2.PdfReader(str(file_path))
            pages = [p.extract_text() or "" for p in reader.pages]
            text = "\n\n".join(pages)
            if len(text) > 50000:
                text = text[:50000] + "\n\n[PDF 过长，已截断]"
            return text, ""
        except ImportError:
            return "", "PDF 支持需要安装 PyPDF2：pip install PyPDF2"
        except Exception as exc:
            return "", f"PDF 解析失败：{exc}"

    # ---- unsupported ----
    return "", f"暂不支持 {suffix} 格式的文本提取，文件已保存，可用其他方式处理"


# ═══════════════════════════════════════════════════════════════════════
# Image description via vision model
# ═══════════════════════════════════════════════════════════════════════

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp"}


def extract_image_description(file_path: Path, llm_client) -> tuple[str, str]:
    """Use a vision-capable LLM to describe an image file.

    Returns ``(description, error_message)``.
    """
    import base64

    with open(file_path, "rb") as f:
        image_data = base64.b64encode(f.read()).decode()

    suffix = file_path.suffix.lower().lstrip(".")
    # Normalise jpeg → jpg for MIME
    mime_suffix = "jpeg" if suffix == "jpg" else suffix

    messages = [{
        "role": "user",
        "content": [
            {"type": "image_url",
             "image_url": {"url": f"data:image/{mime_suffix};base64,{image_data}"}},
            {"type": "text",
             "text": "请详细描述这张图片的内容，包括文字、图表、场景等所有可见信息。"},
        ],
    }]

    try:
        raw = llm_client.chat(messages, temperature=0.3, max_tokens=1000)
        return raw, ""
    except Exception as exc:
        return "", f"图片理解失败：{exc}"
