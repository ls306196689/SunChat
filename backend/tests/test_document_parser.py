"""
Tests for Document Parser
"""
import pytest
import os
import tempfile
import shutil

from core.document_parser import DocumentParser, document_parser


@pytest.fixture
def temp_dir():
    """Create a temporary directory for test files"""
    temp = tempfile.mkdtemp()
    yield temp
    shutil.rmtree(temp)


class TestDocumentParser:
    """Test cases for DocumentParser"""

    def test_detect_file_type(self):
        """Test file type detection"""
        parser = DocumentParser()

        assert parser._detect_file_type("test.pdf") == "pdf"
        assert parser._detect_file_type("test.PDF") == "pdf"
        assert parser._detect_file_type("test.docx") == "docx"
        assert parser._detect_file_type("test.txt") == "txt"
        assert parser._detect_file_type("test.md") == "md"

    def test_detect_file_type_raises_for_unknown(self):
        """Test that unknown file type raises ValueError"""
        parser = DocumentParser()

        with pytest.raises(ValueError, match="不支持的文件类型"):
            parser._detect_file_type("test.unknown")

    def test_parse_txt(self, temp_dir):
        """Test TXT file parsing"""
        # Create a test TXT file
        txt_file = os.path.join(temp_dir, "test.txt")
        with open(txt_file, "w", encoding="utf-8") as f:
            f.write("这是第一段内容。\n")
            f.write("这是第二段内容。\n\n")
            f.write("这是第三段内容。\n")

        parser = DocumentParser()
        chunks = parser.parse(txt_file)

        assert len(chunks) > 0
        assert "content" in chunks[0]
        assert "char_count" in chunks[0]
        assert "word_count" in chunks[0]
        assert chunks[0]["page_number"] == 1

    def test_parse_md(self, temp_dir):
        """Test Markdown file parsing"""
        # Create a test MD file
        md_file = os.path.join(temp_dir, "test.md")
        with open(md_file, "w", encoding="utf-8") as f:
            f.write("# 标题1\n")
            f.write("这是第一段内容。\n")
            f.write("\n")
            f.write("## 标题2\n")
            f.write("这是第二段内容。\n")

        parser = DocumentParser()
        chunks = parser.parse(md_file)

        assert len(chunks) > 0
        assert "content" in chunks[0]
        assert "title" in chunks[0]
        assert chunks[0]["page_number"] == 1

    def test_parse_empty_txt(self, temp_dir):
        """Test parsing empty TXT file"""
        empty_file = os.path.join(temp_dir, "empty.txt")
        with open(empty_file, "w", encoding="utf-8") as f:
            f.write("")

        parser = DocumentParser()

        with pytest.raises(ValueError, match="TXT 文件为空"):
            parser.parse(empty_file)

    def test_parse_nonexistent_file(self):
        """Test parsing non-existent file"""
        parser = DocumentParser()

        with pytest.raises(FileNotFoundError, match="文件不存在"):
            parser.parse("/nonexistent/file.txt")

    def test_parse_unknown_type(self, temp_dir):
        """Test parsing unknown file type"""
        unknown_file = os.path.join(temp_dir, "test.xyz")
        with open(unknown_file, "w") as f:
            f.write("test content")

        parser = DocumentParser()

        # _detect_file_type raises ValueError for unknown types
        with pytest.raises(ValueError, match="不支持的文件类型"):
            parser._detect_file_type(unknown_file)

    def test_get_file_info(self, temp_dir):
        """Test getting file info"""
        txt_file = os.path.join(temp_dir, "test.txt")
        with open(txt_file, "w", encoding="utf-8") as f:
            f.write("test content")

        parser = DocumentParser()
        info = parser.get_file_info(txt_file)

        assert info["filename"] == "test.txt"
        assert info["extension"] == "txt"
        assert info["file_type"] == "txt"
        assert info["size"] > 0
        assert info["size_kb"] > 0

    @pytest.mark.skipif(not shutil.which("pdftk"), reason="pdftk not available")
    def test_parse_pdf(self, temp_dir):
        """Test PDF file parsing"""
        # Create a simple PDF using reportlab or pypdf
        try:
            from reportlab.pdfgen import canvas
            from reportlab.lib.pagesizes import A4

            pdf_file = os.path.join(temp_dir, "test.pdf")
            c = canvas.Canvas(pdf_file, pagesize=A4)
            c.drawString(100, 750, "这是 PDF 的第一页内容")
            c.drawString(100, 700, "包含更多文本内容")
            c.showPage()
            c.drawString(100, 750, "这是 PDF 的第二页内容")
            c.save()

            parser = DocumentParser()
            chunks = parser.parse(pdf_file)

            assert len(chunks) > 0
            assert "content" in chunks[0]
            assert "page_number" in chunks[0]

        except ImportError:
            pytest.skip("reportlab not available")

    def test_parse_docx(self, temp_dir):
        """Test DOCX file parsing"""
        try:
            from docx import Document
            from docx.shared import Inches

            docx_file = os.path.join(temp_dir, "test.docx")
            doc = Document()

            # Add content
            doc.add_heading("文档标题", level=1)
            doc.add_paragraph("这是第一段内容。")
            doc.add_paragraph("这是第二段内容。")
            doc.add_heading("第二部分", level=2)
            doc.add_paragraph("这是第三段内容。")

            doc.save(docx_file)

            parser = DocumentParser()
            chunks = parser.parse(docx_file)

            assert len(chunks) > 0
            assert "content" in chunks[0]
            assert "char_count" in chunks[0]

        except ImportError:
            pytest.skip("python-docx not available")

    def test_parse_large_txt(self, temp_dir):
        """Test parsing large TXT file with chunking"""
        # Create a large TXT file with actual paragraphs (empty line between paragraphs)
        large_file = os.path.join(temp_dir, "large.txt")
        with open(large_file, "w", encoding="utf-8") as f:
            for i in range(30):
                f.write(f"这是第 {i} 段内容，包含一些文本内容用于测试分块功能。\n")
                f.write(f"这是第 {i} 段的第二行内容。\n\n")  # Empty line creates paragraph break

        parser = DocumentParser()
        chunks = parser.parse(large_file)

        # 应该被分块处理
        assert len(chunks) > 0
        # 每个 chunk 应该在合理大小
        for chunk in chunks:
            assert chunk["char_count"] <= 500 + 100  # 允许一些余量
