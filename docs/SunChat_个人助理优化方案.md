# SunChat 个人助理优化方案

> **定位**：基于 SunChat 架构的个人助理系统，核心能力为**记忆用户喜好与信息**、**读取本地资料**、**联网查询资料**，并在对话中智能协同三者。
> 
> **当前阶段目标**：功能完善，优先补齐三个核心模块（记忆、知识库、搜索）的"空心"实现。

---

## 一、核心能力重新定义

| 能力 | 当前问题 | 完善后标准 |
|------|----------|------------|
| **记忆** | 存了但用关键字检索，找不到语义关联；无法自动提取有价值信息 | 自动提取喜好/习惯，语义搜索，主动回忆，对话中自然引用 |
| **知识库** | 上传文件只存文件名，无法解析内容，QA 返回模拟答案 | 真正解析 PDF/Word/TXT/Markdown，分块向量化，精准引用原文 |
| **联网搜索** | 返回原始网页列表，无整理，无记忆上下文 | 结合用户记忆背景查询，LLM 整理答案，标注来源，保存搜索历史 |
| **协同** | 三个模块各自为政，对话层无路由逻辑 | 用户一句话自动判断：该回忆？该查文档？该上网？还是闲聊？ |

---

## 二、记忆系统：从"存储"到"懂你"

### 2.1 记忆自动提取（新增核心能力）

在每次对话后，由 LLM 自动分析是否包含值得长期记住的信息，无需用户手动记录。

**值得记住的信息类型**：
- **偏好**（preference）：喜欢的食物、颜色、品牌、风格、音乐
- **事件**（event）：生日、纪念日、会议、约定、待办
- **个人属性**（person）：职业、家庭情况、健康信息、所在地
- **习惯**（habit）：作息、常用工具、工作方式、口头禅
- **工作**（work）：项目背景、技术栈、常用流程

**实现逻辑**：

```python
MEMORY_EXTRACTION_PROMPT = """你是个人助理的记忆提取器。分析以下对话，提取值得长期记住的信息。

值得记住的信息包括：
- 用户偏好（喜欢的食物、颜色、品牌、风格）
- 重要事件（生日、纪念日、会议、约定）
- 个人属性（职业、家庭情况、健康信息）
- 习惯（作息、常用工具、工作方式）

如果没有任何值得记住的信息，返回空列表 []。

对话：
User: {user_message}
Assistant: {assistant_message}

请严格按 JSON 格式返回，不要添加任何其他文字：
[
  {"type": "semantic", "content": "用户喜欢喝美式咖啡，不加糖", "category": "preference", "importance": 0.9},
  {"type": "episodic", "content": "用户提到下周三要去医院复查", "category": "event", "importance": 0.8, "timestamp": "2026-06-06"}
]
"""
```

**触发时机**：每次对话完成后，异步执行（不阻塞回复），提取结果写入记忆库。

---

### 2.2 记忆语义检索（替换现有关键字匹配）

当前 `MemoryService.search_memories` 使用关键字匹配，个人助理必须支持**语义搜索**（例如用户问"我喜欢喝什么"要能匹配到"用户喜欢喝美式咖啡"）。

**技术方案**：
- 使用 **Chroma** 作为向量存储（本地文件持久化，重启不丢失）
- 使用 **Ollama Embedding**（`nomic-embed-text`）生成向量
- SQLite 保留完整元数据（内容、类型、分类、时间、来源会话）
- 搜索时：向量检索 -> 按相似度排序 -> 回 SQLite 补全信息

**核心实现**：

```python
import chromadb
from chromadb.config import Settings

class MemoryService:
    def __init__(self, db, embedding_service):
        self.db = db
        self.embed = embedding_service
        # 本地持久化向量库
        self.chroma = chromadb.Client(
            Settings(persist_directory="./data/chroma_memories")
        )
        self.collection = self.chroma.get_or_create_collection(
            name="memories",
            metadata={"hnsw:space": "cosine"}  # 余弦相似度
        )

    def create_memory(self, content, type, category, 
                      importance, source_session_id, timestamp):
        """创建记忆：SQLite + 向量库双写"""
        # 1. 写入 SQLite（完整数据）
        memory = MemoryModel(
            content=content,
            type=type,
            category=category,
            importance=importance,
            source_session_id=source_session_id,
            created_at=timestamp
        )
        self.db.add(memory)
        self.db.commit()
        self.db.refresh(memory)  # 获取自增 ID

        # 2. 生成向量并写入 Chroma
        vector = self.embed.embed(content)
        self.collection.add(
            ids=[str(memory.id)],
            embeddings=[vector],
            metadatas=[{
                "type": type,
                "category": category,
                "importance": importance,
                "created_at": timestamp
            }]
        )
        return memory

    def search_memories(self, query, top_k=5, 
                       memory_type=None, category=None):
        """语义搜索 + 元数据过滤"""
        query_vec = self.embed.embed(query)

        # 构建过滤条件
        where = {"importance": {"$gte": 0.6}}  # 只搜重要记忆，避免噪音
        if memory_type:
            where["type"] = memory_type
        if category:
            where["category"] = category

        results = self.collection.query(
            query_embeddings=[query_vec],
            n_results=top_k,
            where=where
        )

        if not results["ids"][0]:
            return []

        # 回 SQLite 取完整数据
        memory_ids = [int(i) for i in results["ids"][0]]
        memories = self.db.query(MemoryModel).filter(
            MemoryModel.id.in_(memory_ids)
        ).all()

        # 按 Chroma 返回的相似度排序
        id_to_memory = {m.id: m for m in memories}
        sorted_memories = []
        for idx, mem_id in enumerate(results["ids"][0]):
            if int(mem_id) in id_to_memory:
                m = id_to_memory[int(mem_id)]
                m.similarity = results["distances"][0][idx]  # 附加相似度分数
                sorted_memories.append(m)

        return sorted_memories

    def get_preferences(self):
        """快速获取用户偏好（常用接口）"""
        return self.search_memories(
            query="用户偏好 喜欢 习惯", 
            category="preference",
            top_k=10
        )
```

**关键改进点**：
- 新增 `category` 字段（preference / event / person / habit / work），支持分类筛选
- 新增 `source_session_id`，可追溯"在哪次对话中提到的"
- 语义记忆与情景记忆自动分类存储
- 按 `importance >= 0.6` 过滤，避免低质量记忆干扰

---

### 2.3 记忆主动注入对话

在 `ChatService` 处理用户消息时，**自动检索相关记忆并注入 Prompt 上下文**，让回复更个性化。

**实现逻辑**：

```python
class ChatService:
    async def send_message(self, session_id, content):
        # 1. 检索相关记忆（语义搜索）
        relevant_memories = self.memory_service.search_memories(
            query=content, 
            top_k=3
        )

        # 2. 检索最近工作记忆（最近 5 轮对话）
        recent_messages = self.get_recent_messages(session_id, limit=5)

        # 3. 构建增强 Prompt
        memory_context = ""
        if relevant_memories:
            memory_context = "以下是我记住的关于你的信息：\n"
            for m in relevant_memories:
                memory_context += f"- {m.content}\n"

        work_context = ""
        if recent_messages:
            work_context = "最近对话：\n"
            for msg in recent_messages:
                work_context += f"{msg.role}: {msg.content}\n"

        enhanced_prompt = f"""{memory_context}

{work_context}

用户当前问题：{content}

请作为个人助理回答。回答时：
1. 如果记忆中有相关信息，主动结合（如"我记得你喜欢..."）
2. 保持简洁、个人化、有温度
3. 如果不确定，不要编造"""

        # 4. 调用 LLM 生成回复
        response = await self.llm.generate(enhanced_prompt)

        # 5. 异步提取新记忆（不阻塞返回）
        asyncio.create_task(
            self.generate_memory_from_message(content, response, session_id)
        )

        return response
```

---

## 三、知识库：从"文件列表"到"第二大脑"

当前知识库仅记录文件元信息（文件名、大小），无法解析内容。个人助理必须能**真正读取本地文档**并回答。

### 3.1 文档解析与分块

**支持格式**：`.txt`、`.md`、`.pdf`、`.docx`

**分块策略**：
1. 按段落优先分割（保持语义完整）
2. 段落过长时按句子分割
3. 块间保留 `overlap`（默认 50 字符），防止上下文断裂

**实现代码**：

```python
import os
import re
from pathlib import Path

# 依赖：pip install pdfplumber python-docx

class DocumentParser:
    SUPPORTED = {'.txt', '.md', '.pdf', '.docx'}

    def parse(self, file_path):
        """解析文档为纯文本"""
        ext = Path(file_path).suffix.lower()
        if ext in {'.txt', '.md'}:
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read()
        elif ext == '.pdf':
            import pdfplumber
            text = []
            with pdfplumber.open(file_path) as pdf:
                for page in pdf.pages:
                    text.append(page.extract_text() or "")
            return "\n".join(text)
        elif ext == '.docx':
            from docx import Document
            doc = Document(file_path)
            return "\n".join([p.text for p in doc.paragraphs])
        else:
            raise ValueError(f"不支持的格式: {ext}")

    def chunk(self, text, chunk_size=500, overlap=50):
        """语义分块：按段落优先，再按句子，最后按字符"""
        paragraphs = [p.strip() for p in text.split('\n') if p.strip()]

        chunks = []
        current_chunk = ""

        for para in paragraphs:
            if len(current_chunk) + len(para) < chunk_size:
                current_chunk += para + "\n"
            else:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                # 保留 overlap 上下文
                if overlap > 0 and current_chunk:
                    sentences = re.split(r'([。！？.!?])', current_chunk)
                    overlap_text = ""
                    for i in range(len(sentences)-1, -1, -1):
                        if len(overlap_text) + len(sentences[i]) < overlap:
                            overlap_text = sentences[i] + overlap_text
                        else:
                            break
                    current_chunk = overlap_text + para + "\n"
                else:
                    current_chunk = para + "\n"

        if current_chunk:
            chunks.append(current_chunk.strip())

        return chunks
```

---

### 3.2 知识库向量化与问答

**完整链路**：

```
文件上传 -> 文本提取 -> 语义分块 -> 向量化 -> Chroma 存储 -> 检索 -> 构造 Prompt -> LLM 生成答案
```

**核心实现**：

```python
class KnowledgeService:
    def __init__(self, db, embedding_service, llm_service):
        self.db = db
        self.embed = embedding_service
        self.llm = llm_service
        self.parser = DocumentParser()
        self.chroma = chromadb.Client(
            Settings(persist_directory="./data/chroma_knowledge")
        )

    def process_file(self, file_id, file_path):
        """真正的文件处理：解析 -> 分块 -> 向量化"""
        # 1. 解析文档
        text = self.parser.parse(file_path)

        # 2. 分块
        chunks = self.parser.chunk(text)

        # 3. 获取/创建集合（每个文件一个集合，也支持全局集合）
        collection = self.chroma.get_or_create_collection(f"kb_{file_id}")

        # 4. 批量向量化并写入
        chunk_ids = [f"{file_id}_{i}" for i in range(len(chunks))]
        embeddings = [self.embed.embed(chunk) for chunk in chunks]

        collection.add(
            ids=chunk_ids,
            embeddings=embeddings,
            metadatas=[{
                "file_id": file_id,
                "chunk_index": i,
                "text_preview": chunk[:200]  # 摘要预览
            } for i, chunk in enumerate(chunks)],
            documents=chunks
        )

        # 5. 更新数据库状态
        kb_file = self.db.query(KBFile).filter(KBFile.id == file_id).first()
        kb_file.status = "ready"
        kb_file.chunk_count = len(chunks)
        self.db.commit()

        return len(chunks)

    def search_knowledge(self, query, file_id=None, top_k=5):
        """向量检索：支持单文件或跨文件"""
        if file_id:
            collection = self.chroma.get_collection(f"kb_{file_id}")
        else:
            # 跨文件检索：遍历所有集合或维护一个全局集合
            collection = self.chroma.get_or_create_collection("kb_global")

        query_vec = self.embed.embed(query)
        results = collection.query(
            query_embeddings=[query_vec],
            n_results=top_k
        )

        return [
            {
                "content": doc,
                "file_id": meta["file_id"],
                "chunk_index": meta["chunk_index"]
            }
            for doc, meta in zip(results["documents"][0], results["metadatas"][0])
        ]

    def qa(self, query, file_id=None):
        """知识库问答：检索 + LLM 生成"""
        # 1. 检索相关 chunks
        chunks = self.search_knowledge(query, file_id, top_k=5)

        if not chunks:
            return "知识库中没有找到相关内容。"

        # 2. 构建上下文
        context = "\n\n".join([
            f"[文档片段 {i+1}] {c['content']}" 
            for i, c in enumerate(chunks)
        ])

        # 3. 生成答案
        prompt = f"""基于以下文档内容回答问题。如果文档中没有答案，请明确说明。

文档内容：
{context}

问题：{query}

要求：
1. 用中文回答
2. 引用相关文档片段（如"根据文档片段1..."）
3. 保持简洁准确，不要编造文档外的信息"""

        return self.llm.generate(prompt)
```

---

### 3.3 文件上传接口改造

上传后异步处理，前端轮询状态：

```python
@router.post("/upload")
async def upload_file(file: UploadFile, db: Session = Depends(get_db)):
    # 1. 保存文件到本地
    file_id = str(uuid.uuid4())
    save_dir = Path("./data/uploads")
    save_dir.mkdir(exist_ok=True)
    file_path = save_dir / f"{file_id}_{file.filename}"

    with open(file_path, "wb") as f:
        f.write(await file.read())

    # 2. 记录元信息（状态改为 processing）
    kb_file = KBFile(
        id=file_id,
        filename=file.filename,
        file_type=file.filename.split('.')[-1],
        file_size=file.size,
        status="processing",
        local_path=str(file_path)
    )
    db.add(kb_file)
    db.commit()

    # 3. 异步处理（避免上传阻塞）
    asyncio.create_task(
        knowledge_service.process_file(file_id, str(file_path))
    )

    return {"file_id": file_id, "status": "processing"}
```

**前端轮询逻辑**：

```javascript
const checkStatus = async (fileId) => {
  const res = await axios.get(`/api/v1/knowledge/files/${fileId}`);
  if (res.data.status === 'ready') {
    message.success('文档解析完成，可以提问了');
  } else if (res.data.status === 'error') {
    message.error('文档解析失败：' + res.data.error_msg);
  } else {
    setTimeout(() => checkStatus(fileId), 1000);  // 每秒轮询
  }
};
```

---

## 四、联网搜索：从"返回链接"到"整理答案"

当前搜索返回原始 DuckDuckGo 条目，个人助理需要**理解问题 -> 搜索 -> 整理 -> 结合记忆回答**。

### 4.1 搜索流程升级

```python
class SearchService:
    def __init__(self, memory_service, llm_service):
        self.memory = memory_service
        self.llm = llm_service

    async def search(self, query, user_id=None):
        # 1. 检查记忆中是否有相关上下文（个性化搜索）
        memory_hints = []
        if user_id:
            memories = self.memory.search_memories(query, top_k=2)
            for m in memories:
                if m.category in ['preference', 'habit', 'work']:
                    memory_hints.append(m.content)

        # 2. 构建增强查询（结合用户背景）
        enhanced_query = query
        if memory_hints:
            enhanced_query = f"{query} (相关背景: {'; '.join(memory_hints)})"

        # 3. 意图路由（新闻/学术/通用）
        intent = self._route_query(query)

        # 4. 执行 DuckDuckGo 搜索
        with DDGS() as ddgs:
            if intent == "news":
                results = ddgs.news(enhanced_query, max_results=5)
            else:
                results = ddgs.text(enhanced_query, max_results=5)

        # 5. 用 LLM 整理搜索结果（关键！）
        sources = "\n".join([
            f"[{i+1}] {r['title']}: {r['body']}" 
            for i, r in enumerate(results)
        ])

        summary_prompt = f"""基于以下搜索结果，回答用户问题。请综合多个来源，给出简洁准确的答案。

用户问题：{query}

搜索结果：
{sources}

要求：
1. 直接给出答案，不要罗列链接
2. 如果有冲突信息，选择最权威的
3. 标注信息来源（如"据XX报道"）
4. 如果搜索结果不足以回答，请明确说明"""

        answer = await self.llm.generate(summary_prompt)

        return {
            "answer": answer,
            "sources": [{"title": r["title"], "url": r["href"]} for r in results],
            "intent": intent
        }
```

**关键改进**：
- 搜索前自动注入用户记忆作为上下文，实现"个性化搜索"
- 搜索结果由 LLM 整理为直接答案，而非返回原始链接列表
- 保留来源引用，便于用户验证

---

### 4.2 搜索历史记录（关联记忆）

保存搜索历史并关联相关记忆，支持后续追问"我上次让你查的..."

```python
class SearchHistory(BaseModel):
    id: int
    query: str
    intent: str
    result_summary: str       # LLM 整理后的摘要
    source_urls: str          # JSON 序列化
    created_at: datetime
    related_memory_ids: str   # 关联的记忆 ID 列表

# 搜索后自动保存
async def search_and_remember(self, query, user_id):
    result = await self.search(query, user_id)

    history = SearchHistory(
        query=query,
        intent=result["intent"],
        result_summary=result["answer"][:500],
        source_urls=json.dumps(result["sources"]),
        related_memory_ids=json.dumps([])  # 可后续关联
    )
    self.db.add(history)
    self.db.commit()

    return result
```

---

## 五、对话协同：记忆 + 知识库 + 搜索的智能路由

个人助理的核心是**对话路由**：用户一句话，系统判断该用记忆、知识库还是搜索。

### 5.1 意图路由（对话级）

```python
class ChatRouter:
    def __init__(self, llm):
        self.llm = llm

    ROUTING_PROMPT = """分析用户问题，判断需要调用哪些工具来给出最佳回答。

可用工具：
- memory：需要回忆用户相关信息（偏好、历史、约定）
- knowledge：需要查询用户上传的文档/资料
- search：需要联网获取最新信息（新闻、实时数据）
- chat：一般闲聊/常识问答，不需要工具

判断规则：
- 涉及"我"、"我的"、个人事务 -> 优先 memory
- 涉及"文件"、"文档"、"资料"、"论文" -> 优先 knowledge
- 涉及"最新"、"今天"、"新闻"、"现在"、"价格" -> 优先 search
- 多个工具可以组合使用

用户问题：{query}

请严格返回 JSON 格式，不要添加其他文字：
{"tools": ["memory", "search"], "reason": "用户问喜欢的餐厅，需要回忆记忆；问最新评价，需要搜索"}"""

    async def route(self, query):
        response = await self.llm.generate(
            self.ROUTING_PROMPT.format(query=query)
        )
        return json.loads(response)
```

---

### 5.2 对话流程整合

```python
class ChatService:
    async def process_message(self, session_id, user_id, content):
        # 1. 路由决策：判断需要哪些工具
        route = await self.router.route(content)
        tools = route.get("tools", ["chat"])

        context_parts = []

        # 2. 收集记忆上下文
        if "memory" in tools:
            memories = self.memory_service.search_memories(content, top_k=3)
            if memories:
                context_parts.append("【关于你的记忆】\n" + 
                    "\n".join([f"- {m.content}" for m in memories]))

        # 3. 收集知识库上下文
        if "knowledge" in tools:
            knowledge = self.knowledge_service.search_knowledge(content, top_k=3)
            if knowledge:
                context_parts.append("【你的文档资料】\n" +
                    "\n".join([f"- {k['content'][:200]}..." for k in knowledge]))

        # 4. 收集搜索结果
        if "search" in tools:
            search_result = await self.search_service.search(content, user_id)
            context_parts.append("【联网搜索结果】\n" + search_result["answer"])

        # 5. 构建最终 Prompt
        system_prompt = """你是用户的个人助理。回答时请：
1. 优先使用记忆中的个人信息，让回答更贴心、有温度
2. 引用知识库时标注来源文档
3. 使用搜索信息时确保时效性
4. 保持简洁，避免冗长
5. 如果不确定，诚实说明，不要编造"""

        full_prompt = f"{system_prompt}\n\n" + "\n\n".join(context_parts) + f"\n\n用户：{content}\n\n助理："

        # 6. 生成回复（建议改造为 SSE 流式）
        response = await self.llm.generate(full_prompt)

        # 7. 异步提取新记忆（后台执行，不阻塞）
        asyncio.create_task(
            self.memory_service.extract_from_dialog(content, response, session_id)
        )

        return response
```

---

## 六、前端适配要点

### 6.1 记忆展示页面（MemoriesView.vue）

- **时间线视图**：按时间倒序展示情景记忆（带日期标签）
- **分类筛选**：顶部 Tab 切换 preference / event / habit / work / person
- **记忆溯源**：每条记忆显示"来源对话"按钮，点击可跳转回原始会话
- **重要性编辑**：允许用户手动调整记忆重要程度（0-1 滑块）
- **删除记忆**：支持单条删除 + 批量清理低重要性记忆

### 6.2 知识库状态显示

上传文件后，文件列表显示处理状态：
- `processing`：显示进度条/转圈，禁止提问
- `ready`：显示"可问答"标签，开放输入框
- `error`：显示红色错误提示，提供重新处理按钮

### 6.3 搜索结果引用

`MessageItem.vue` 中，如果消息包含搜索来源，底部显示可折叠的引用卡片：

```vue
<template>
  <div class="message-content">{{ content }}</div>
  <div v-if="sources?.length" class="sources">
    <n-collapse>
      <n-collapse-item title="参考来源">
        <div v-for="s in sources" :key="s.url">
          <a :href="s.url" target="_blank">{{ s.title }}</a>
        </div>
      </n-collapse-item>
    </n-collapse>
  </div>
</template>
```

### 6.4 流式响应（建议后续实现）

将 `chat.py` 改为 SSE 流式输出，前端使用 `EventSource` 接收：

```javascript
const eventSource = new EventSource('/api/v1/chat/stream?session_id=xxx');
eventSource.onmessage = (event) => {
  const data = JSON.parse(event.data);
  if (data.content) {
    currentMessage.value += data.content;  // 逐字追加
  }
  if (data.done) {
    eventSource.close();
  }
};
```

---

## 七、执行清单（按优先级排序）

| 优先级 | 功能 | 改造文件 | 工作量 | 预期效果 |
|--------|------|----------|--------|----------|
| **P0** | 记忆语义检索 | `memory_service.py` | 2-3 天 | 问"我喜欢什么"能准确找到答案 |
| **P0** | 知识库文档解析 | `knowledge_service.py` + 新增 `DocumentParser` | 2-3 天 | 上传 PDF 后能真正问答 |
| **P0** | 对话记忆注入 | `chat_service.py` | 1-2 天 | 助理开始"懂你"，回复个性化 |
| **P1** | 记忆自动提取 | `chat_service.py` 中的 `generate_memory_from_message` | 1-2 天 | 自动记录喜好，无需手动 |
| **P1** | 搜索答案整理 | `search_service.py` | 1-2 天 | 搜索体验质变，不再是链接列表 |
| **P1** | 搜索记忆上下文 | `search_service.py` | 0.5 天 | 搜索更贴合用户背景 |
| **P2** | 对话路由 | 新增 `ChatRouter` | 1-2 天 | 自动判断该查记忆/文档/搜索 |
| **P2** | 搜索历史关联 | `search.py` + 模型 | 1 天 | "我上次让你查的..."能回答 |
| **P2** | 流式 SSE 响应 | `chat.py` + `MessageItem.vue` | 2-3 天 | 大模型回复不卡顿等待 |
| **P3** | 前端记忆时间线 | `MemoriesView.vue` | 2-3 天 | 用户可管理自己的记忆 |
| **P3** | 知识库状态轮询 | `knowledge.py` + 前端 | 1 天 | 上传后实时显示处理进度 |

---

## 八、数据模型补充

### Memory 表扩展字段

```sql
-- 在现有 Memory 表基础上增加
ALTER TABLE memories ADD COLUMN category VARCHAR(20);      -- preference/event/person/habit/work
ALTER TABLE memories ADD COLUMN source_session_id VARCHAR(50);  -- 来源会话 ID
ALTER TABLE memories ADD COLUMN updated_at TIMESTAMP;      -- 支持记忆更新
```

### SearchHistory 表（新增）

```sql
CREATE TABLE search_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    query TEXT NOT NULL,
    intent VARCHAR(20),
    result_summary TEXT,
    source_urls TEXT,           -- JSON 数组
    related_memory_ids TEXT,    -- JSON 数组
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

---

## 九、总结

当前 SunChat 架构的**骨架已经搭好**，作为个人助理，只需把三个"空心模块"填实：

1. **记忆**：从"关键字搜索"升级为**语义检索 + 自动提取 + 对话注入**
2. **知识库**：从"存文件名"升级为**解析 -> 分块 -> 向量化 -> 精准引用**
3. **搜索**：从"返回链接"升级为**意图判断 + 记忆上下文 + LLM 整理**

这三个能力跑通后，配合**对话路由**，就是一个**真正可用的个人助理**（而非玩具）。后续再考虑流式响应、PostgreSQL 迁移、Docker 化等工程化升级。

**建议先集中 1-2 周完成 P0 项（记忆语义检索 + 知识库解析 + 对话注入），系统体验会有质变。**

---

*文档生成时间：2026-06-06*
*基于 SunChat 架构文档与个人助理需求整理*
