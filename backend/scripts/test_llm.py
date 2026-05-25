#!/usr/bin/env python3
"""
SunChat Backend - Test LLM Connection
"""
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.llm import ollama_service
from core.embedding import embedding_service
from core.search import search_service


def main():
    """测试 LLM 连接"""
    print("=" * 50)
    print("SunChat LLM 连接测试")
    print("=" * 50)

    # 测试 LLM
    print("\n[1] 测试 LLM 服务...")
    llm_available = ollama_service.check_availability()
    if llm_available:
        print(f"✓ LLM 服务可用")
        print(f"  模型: {ollama_service.model}")
    else:
        print("✗ LLM 服务不可用")
        print(f"  请检查 Ollama 是否运行在: {ollama_service.api_url}")
        print(f"  运行: ollama serve")

    # 测试嵌入模型
    print("\n[2] 测试嵌入模型...")
    try:
        test_text = "测试文本"
        embedding = embedding_service.embed(test_text)
        print(f"✓ 嵌入模型可用")
        print(f"  模型: {embedding_service.model}")
        print(f"  向量维度: {len(embedding)}")
    except Exception as e:
        print(f"✗ 嵌入模型测试失败: {e}")

    # 测试搜索
    print("\n[3] 测试搜索服务...")
    search_available = search_service.check_availability()
    if search_available:
        print("✓ 搜索服务可用")
        print("  使用: DuckDuckGo API (无 Key)")
    else:
        print("⚠ 搜索服务可能受限")

    # 测试聊天
    if llm_available:
        print("\n[4] 测试聊天功能...")
        try:
            messages = [
                {"role": "system", "content": "你是一个助手。"},
                {"role": "user", "content": "你好，请回复'测试成功'"}
            ]
            response = ollama_service.chat(messages)
            print("✓ 聊天测试成功")
            print(f"  响应: {response.get('message', {}).get('content', 'N/A')}")
        except Exception as e:
            print(f"✗ 聊天测试失败: {e}")

    print("\n" + "=" * 50)
    print("测试完成")
    print("=" * 50)


if __name__ == "__main__":
    main()
