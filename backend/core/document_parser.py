"""
SunChat Backend - Document Parser
支持 PDF, DOCX, TXT, MD 格式文档解析
"""
import os
import re
from typing import List, Dict, Optional
from datetime import datetime


class DocumentParser:
    """文档解析器"""

    def __init__(self):
        self.supported_types = {
            "pdf": "pdf",
            "docx": "docx",
            "txt": "txt",
            "md": "markdown"
        }

    def parse(self, file_path: str, file_type: str = None) -> List[Dict]:
        """
        解析文档并返回内容块列表

        Args:
            file_path: 文件路径
            file_type: 文件类型（自动检测如果未提供）

        Returns:
            内容块列表，每个块包含:
            - content: 文本内容
            - page_number: 页码（对于多页文档）
            - char_count: 字符数
            - word_count: 单词数
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"文件不存在: {file_path}")

        # 自动检测文件类型
        if file_type is None:
            file_type = self._detect_file_type(file_path)

        # 检查文件类型是否支持
        if file_type not in self.supported_types:
            raise ValueError(f"不支持的文件类型: {file_type}")

        # 根据文件类型调用相应的解析器
        if file_type == "pdf":
            return self._parse_pdf(file_path)
        elif file_type == "docx":
            return self._parse_docx(file_path)
        elif file_type == "txt":
            return self._parse_txt(file_path)
        elif file_type == "md":
            return self._parse_md(file_path)
        else:
            raise ValueError(f"不支持的文件类型: {file_type}")

    def _detect_file_type(self, file_path: str) -> str:
        """自动检测文件类型"""
        _, ext = os.path.splitext(file_path)
        ext = ext.lower().lstrip(".")
        if ext not in self.supported_types:
            raise ValueError(f"不支持的文件类型: {ext}")
        return ext

    def _parse_pdf(self, file_path: str) -> List[Dict]:
        """解析 PDF 文件"""
        try:
            import PyPDF2
        except ImportError:
            raise ImportError(
                "PyPDF2 未安装。请运行: pip install PyPDF2"
            )

        chunks = []
        try:
            with open(file_path, "rb") as file:
                reader = PyPDF2.PdfReader(file)

                for page_num, page in enumerate(reader.pages, 1):
                    text = page.extract_text() or ""
                    if text.strip():  # 只添加非空文本
                        chunks.append({
                            "content": text.strip(),
                            "page_number": page_num,
                            "char_count": len(text),
                            "word_count": len(text.split()),
                            "created_at": datetime.now().isoformat()
                        })
        except Exception as e:
            raise RuntimeError(f"PDF 解析失败: {e}")

        if not chunks:
            raise ValueError("PDF 文件为空或无法提取文本")

        return chunks

    def _parse_docx(self, file_path: str) -> List[Dict]:
        """解析 DOCX 文件"""
        try:
            import docx
        except ImportError:
            raise ImportError(
                "python-docx 未安装。请运行: pip install python-docx"
            )

        chunks = []
        try:
            from docx import Document
            doc = Document(file_path)

            # 按段落分块，每个块包含一个或多个段落
            current_chunk = []
            current_page = 1

            for para in doc.paragraphs:
                text = para.text.strip()
                if not text:
                    continue

                # 检测分页符（简单检测）
                if "\f" in text:
                    text = text.replace("\f", "").strip()
                    if current_chunk:
                        chunks.append({
                            "content": "\n".join(current_chunk),
                            "page_number": current_page,
                            "char_count": sum(len(t) for t in current_chunk),
                            "word_count": sum(len(t.split()) for t in current_chunk),
                            "created_at": datetime.now().isoformat()
                        })
                        current_chunk = []
                    current_page += 1

                current_chunk.append(text)

                # 如果 chunk 太大，分块
                if len(current_chunk) >= 10:  # 每10个段落作为一个 chunk
                    chunks.append({
                        "content": "\n".join(current_chunk),
                        "page_number": current_page,
                        "char_count": sum(len(t) for t in current_chunk),
                        "word_count": sum(len(t.split()) for t in current_chunk),
                        "created_at": datetime.now().isoformat()
                    })
                    current_chunk = []

            # 添加剩余内容
            if current_chunk:
                chunks.append({
                    "content": "\n".join(current_chunk),
                    "page_number": current_page,
                    "char_count": sum(len(t) for t in current_chunk),
                    "word_count": sum(len(t.split()) for t in current_chunk),
                    "created_at": datetime.now().isoformat()
                })

        except Exception as e:
            raise RuntimeError(f"DOCX 解析失败: {e}")

        if not chunks:
            raise ValueError("DOCX 文件为空或无法提取文本")

        return chunks

    def _parse_txt(self, file_path: str) -> List[Dict]:
        """解析 TXT 文件"""
        try:
            with open(file_path, "r", encoding="utf-8") as file:
                content = file.read()
        except UnicodeDecodeError:
            # 尝试其他编码
            with open(file_path, "r", encoding="gbk") as file:
                content = file.read()

        # 按空行分块
        paragraphs = re.split(r"\n\s*\n", content)

        chunks = []
        current_chunk = []
        char_count = 0

        for para in paragraphs:
            para = para.strip()
            if not para:
                continue

            # 如果当前 chunk 满了，保存
            if char_count + len(para) > 500 and current_chunk:  # 每个 chunk 最多 500 字符
                chunks.append({
                    "content": "\n".join(current_chunk),
                    "page_number": 1,  # TXT 文件没有页码
                    "char_count": char_count,
                    "word_count": sum(len(p.split()) for p in current_chunk),
                    "created_at": datetime.now().isoformat()
                })
                current_chunk = [para]
                char_count = len(para)
            else:
                current_chunk.append(para)
                char_count += len(para)

        # 添加剩余内容
        if current_chunk:
            chunks.append({
                "content": "\n".join(current_chunk),
                "page_number": 1,
                "char_count": char_count,
                "word_count": sum(len(p.split()) for p in current_chunk),
                "created_at": datetime.now().isoformat()
            })

        if not chunks:
            raise ValueError("TXT 文件为空")

        return chunks

    def _parse_md(self, file_path: str) -> List[Dict]:
        """解析 Markdown 文件"""
        try:
            with open(file_path, "r", encoding="utf-8") as file:
                content = file.read()
        except UnicodeDecodeError:
            with open(file_path, "r", encoding="gbk") as file:
                content = file.read()

        # 按标题分块（支持 # ## ###）
        sections = re.split(r"\n(?=\n*#{1,6}\s)", content)

        chunks = []
        for i, section in enumerate(sections):
            section = section.strip()
            if not section:
                continue

            # 提取标题
            title_match = re.match(r"^(#{1,6})\s+(.+)$", section.split("\n")[0])
            title = title_match.group(2) if title_match else f"Section {i + 1}"

            # 移除标题行
            section_content = re.sub(r"^#{1,6}\s+.+$", "", section, flags=re.MULTILINE).strip()

            if not section_content:
                continue

            chunks.append({
                "content": section_content,
                "title": title,
                "page_number": 1,  # MD 文件没有页码
                "char_count": len(section_content),
                "word_count": len(section_content.split()),
                "created_at": datetime.now().isoformat()
            })

        if not chunks:
            raise ValueError("MD 文件为空或无法提取文本")

        return chunks

    def get_file_info(self, file_path: str) -> Dict:
        """获取文件信息"""
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"文件不存在: {file_path}")

        _, ext = os.path.splitext(file_path)
        ext = ext.lower().lstrip(".")

        file_stat = os.stat(file_path)

        return {
            "filename": os.path.basename(file_path),
            "extension": ext,
            "file_type": ext if ext in self.supported_types else "unknown",
            "size": file_stat.st_size,
            "size_kb": round(file_stat.st_size / 1024, 2),
            "created_at": datetime.fromtimestamp(file_stat.st_ctime).isoformat(),
            "modified_at": datetime.fromtimestamp(file_stat.st_mtime).isoformat()
        }


# 全局实例
document_parser = DocumentParser()
