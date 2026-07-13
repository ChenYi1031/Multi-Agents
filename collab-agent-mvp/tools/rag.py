"""
RAG 知识库模块
支持文件上传（TXT/PDF）、文档分块、关键词检索
使用内存存储，适合 MVP 演示
"""

from __future__ import annotations

import json
import logging
import os
import re
import tempfile
from typing import Dict, List, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


class DocumentChunk:
    """文档块"""
    def __init__(self, doc_id: str, content: str, source: str, chunk_index: int):
        self.doc_id = doc_id
        self.content = content
        self.source = source
        self.chunk_index = chunk_index

    def to_dict(self) -> dict:
        return {
            "doc_id": self.doc_id,
            "content": self.content[:200] + "..." if len(self.content) > 200 else self.content,
            "source": self.source,
            "chunk_index": self.chunk_index,
        }


class KnowledgeBase:
    """
    简易内存知识库
    支持文档添加、关键词检索、清空
    """

    def __init__(self):
        self.chunks: List[DocumentChunk] = []
        self._doc_counter = 0

    def add_text(self, text: str, source: str = "text") -> str:
        """添加纯文本，自动分块"""
        doc_id = f"doc_{self._doc_counter}_{id(text)}"
        self._doc_counter += 1
        chunks = self._chunk_text(text, doc_id, source)
        self.chunks.extend(chunks)
        logger.info(f"添加文本: {source}, {len(text)} 字符, {len(chunks)} 块")
        return doc_id

    def add_file(self, file_path: str) -> str:
        """添加文件（TXT/PDF），自动检测格式"""
        ext = Path(file_path).suffix.lower()
        if ext == ".txt":
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                text = f.read()
            return self.add_text(text, source=os.path.basename(file_path))
        elif ext == ".pdf":
            text = self._extract_pdf_text(file_path)
            return self.add_text(text, source=os.path.basename(file_path))
        else:
            raise ValueError(f"不支持的文件格式: {ext}")

    def search(self, query: str, top_k: int = 5) -> List[dict]:
        """
        关键词检索：基于 TF 的词频匹配
        返回前 top_k 个匹配块
        """
        if not self.chunks:
            return []

        query_terms = set(re.findall(r'\w+', query.lower()))
        if not query_terms:
            return []

        scored = []
        for chunk in self.chunks:
            chunk_terms = set(re.findall(r'\w+', chunk.content.lower()))
            overlap = query_terms & chunk_terms
            score = len(overlap) / max(len(query_terms), 1)
            if score > 0:
                scored.append((score, chunk))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [
            {"content": chunk.content, "source": chunk.source, "score": round(score, 3)}
            for score, chunk in scored[:top_k]
        ]

    def get_all_chunks(self) -> List[dict]:
        """返回所有文档块摘要"""
        return [c.to_dict() for c in self.chunks]

    def clear(self):
        """清空知识库"""
        self.chunks.clear()
        self._doc_counter = 0
        logger.info("知识库已清空")

    @staticmethod
    def _chunk_text(text: str, doc_id: str, source: str, chunk_size: int = 500) -> List[DocumentChunk]:
        """将文本分割为固定大小的块"""
        chunks = []
        paragraphs = re.split(r'\n\s*\n', text)
        current_chunk = ""
        idx = 0
        for para in paragraphs:
            para = para.strip()
            if not para:
                continue
            if len(current_chunk) + len(para) > chunk_size and current_chunk:
                chunks.append(DocumentChunk(doc_id, current_chunk.strip(), source, idx))
                idx += 1
                current_chunk = para
            else:
                current_chunk += ("\n\n" if current_chunk else "") + para
        if current_chunk:
            chunks.append(DocumentChunk(doc_id, current_chunk.strip(), source, idx))
        return chunks

    @staticmethod
    def _extract_pdf_text(file_path: str) -> str:
        """使用 PyMuPDF 提取 PDF 文本"""
        try:
            import fitz
            doc = fitz.open(file_path)
            texts = []
            for page in doc:
                texts.append(page.get_text())
            doc.close()
            return "\n\n".join(texts)
        except ImportError:
            logger.warning("PyMuPDF 未安装，无法解析 PDF")
            return f"[PDF 文件: {os.path.basename(file_path)}，请安装 pymupdf 以提取文本]"
        except Exception as e:
            logger.error(f"PDF 解析失败: {e}")
            return f"[PDF 解析失败: {e}]"


# 全局单例
_kb: Optional[KnowledgeBase] = None


def get_knowledge_base() -> KnowledgeBase:
    """获取全局知识库单例"""
    global _kb
    if _kb is None:
        _kb = KnowledgeBase()
    return _kb


def search_knowledge(query: str, top_k: int = 5) -> List[dict]:
    """快捷检索知识库"""
    return get_knowledge_base().search(query, top_k)


def add_knowledge_file(file_path: str) -> str:
    """快捷添加文件"""
    return get_knowledge_base().add_file(file_path)
