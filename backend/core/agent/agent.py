"""
SunChat Backend - Agent Core
Agent 核心逻辑，实现 ReAct 循环，指挥其他组件协同工作
"""
import json
import re
from typing import List, Dict, Optional, Any, Generator
from datetime import datetime

from core.agent.schema import (
    Message,
    ToolResult,
    ToolDefinition,
    AgentState,
    MemoryContext,
    AgentConfig,
    Action
)
from core.agent.llm import agent_llm
from core.agent.tools import (
    get_all_tools,
    get_tool_definition,
    register_builtin_tools,
    ToolResult as ToolExecutionResult
)
from core.memory_router import memory_router
from core.memory_extractor import memory_extractor
from services.memory_service import memory_service
from utils.logger import logger


class Agent:
    """
    Agent 核心类 - 实现 ReAct 模式

    ReAct 模式：Reasoning + Acting
    - 思考 (Thought)：分析当前状态，决定下一步
    - 行动 (Action)：调用工具
    - 观察 (Observation)：获取工具执行结果
    """

    def __init__(self, config: AgentConfig = None):
        self.config = config or AgentConfig.default()
        self.conversation_history: List[Dict] = []
        self.state = AgentState()
        self._register_tools()

    def _register_tools(self):
        """注册工具"""
        self.tools = {}
        for tool_def in get_all_tools():
            name = tool_def.get("name")
            if name:
                self.tools[name] = tool_def
        logger.info(f"[AGENT] 注册工具 - {list(self.tools.keys())}")

    def _build_system_prompt(self) -> str:
        """构建系统提示"""
        # 基础系统提示
        system_prompt = """你是一个智能 Agent，需要使用 ReAct 模式解决用户问题。

你的输出必须遵循以下格式（始终使用 JSON）：
{
    "thought": "你的思考过程，分析当前状态和下一步计划",
    "action": {
        "name": "工具名称",
        "parameters": {
            "参数名": "参数值"
        }
    },
    "observation": "工具执行结果（如果是观察步骤）"
}

可用工具：
"""

        # 添加工具描述
        for name, tool_def in self.tools.items():
            desc = tool_def.get("description", "")
            params = tool_def.get("parameters", {})
            system_prompt += f"""
{name}: {desc}
参数: {json.dumps(params, ensure_ascii=False, indent=2)}
"""

        system_prompt += """
规则：
1. 每次思考后必须有一个行动，除非任务已完成
2. 行动必须是预定义的工具之一
3. 观察步骤用于返回工具执行结果
4. 任务完成后输出: {"thought": "任务完成", "action": {"name": "finish", "result": "最终答案"}}
5. 如果不需要工具，直接回答用户问题
"""

        return system_prompt

    def _parse_agent_output(self, text: str) -> Dict:
        """解析 Agent 输出"""
        result = {
            "thought": text,
            "action": None,
            "observation": None,
            "raw": text
        }

        # 尝试解析 JSON
        try:
            # 移除可能的 Markdown 代码块
            clean_text = text.strip()
            if clean_text.startswith("```json"):
                clean_text = clean_text[7:]
            if clean_text.startswith("```"):
                clean_text = clean_text[3:]
            if clean_text.endswith("```"):
                clean_text = clean_text[:-3]
            clean_text = clean_text.strip()

            # 尝试解析 JSON
            parsed = json.loads(clean_text)

            if isinstance(parsed, dict):
                result["thought"] = parsed.get("thought", text)
                result["action"] = parsed.get("action")
                result["observation"] = parsed.get("observation")
        except json.JSONDecodeError:
            # 如果不是 JSON，提取可能的 JSON 部分
            json_match = re.search(r'\{[\s\S]*\}', text)
            if json_match:
                try:
                    parsed = json.loads(json_match.group())
                    if isinstance(parsed, dict):
                        result["thought"] = parsed.get("thought", text)
                        result["action"] = parsed.get("action")
                        result["observation"] = parsed.get("observation")
                except json.JSONDecodeError:
                    pass

        return result

    def _execute_action(self, action: Dict) -> ToolResult:
        """执行动作"""
        if not action:
            return ToolResult(success=False, error="没有行动")

        name = action.get("name")
        parameters = action.get("parameters", {})

        logger.info(f"[AGENT] 执行动作 - name:{name}, parameters:{parameters}")

        # 检查是否是 finish 动作
        if name == "finish":
            result = action.get("result", "任务完成")
            return ToolResult(success=True, data=result, metadata={"action": "finish"})

        # 执行工具
        tool_def = self.tools.get(name)
        if not tool_def:
            return ToolResult(
                success=False,
                error=f"未知工具: {name}。可用工具: {list(self.tools.keys())}"
            )

        try:
            # 执行工具函数
            if "function" in tool_def:
                # 装饰器注册的函数
                tool_func = tool_def["function"]
                result = tool_func(**parameters)
                if isinstance(result, ToolExecutionResult):
                    return ToolResult(
                        success=result.success,
                        data=result.data,
                        error=result.error
                    )
                return ToolResult(success=True, data=result)
            elif "tool" in tool_def:
                # 类注册的工具
                tool_instance = tool_def["tool"]
                tool_result = tool_instance.run(**parameters)
                return ToolResult(
                    success=tool_result.success,
                    data=tool_result.data,
                    error=tool_result.error
                )
            else:
                return ToolResult(
                    success=False,
                    error=f"工具 {name} 没有实现"
                )
        except Exception as e:
            logger.error(f"[AGENT] 执行工具 {name} 失败 - 错误:{e}")
            return ToolResult(success=False, error=str(e))

    def _update_state(self, thought: str, action: Dict, observation: str):
        """更新 Agent 状态"""
        self.state.thoughts.append(thought)
        if action:
            self.state.current_action = action
        if observation:
            self.state.observation = observation

    def _add_to_history(self, role: str, content: str):
        """添加到对话历史"""
        self.conversation_history.append({
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat()
        })

        # 修剪对话历史
        while len(self.conversation_history) > 10:
            self.conversation_history.pop(0)

    def process(
        self,
        user_input: str,
        max_iterations: int = None,
        user_id: int = 1
    ) -> Dict:
        """
        处理用户输入 - ReAct 循环

        Args:
            user_input: 用户输入
            max_iterations: 最大迭代次数
            user_id: 用户 ID

        Returns:
            最终结果
        """
        max_iterations = max_iterations or self.config.max_iterations
        self.state = AgentState()
        self.conversation_history = []

        logger.info(f"[AGENT] 开始处理 - 用户输入:{user_input[:100]}...")

        # 添加用户输入到历史
        self._add_to_history("user", user_input)

        # 构建系统提示
        system_prompt = self._build_system_prompt()

        for iteration in range(max_iterations):
            logger.info(f"[AGENT] 迭代 {iteration + 1}/{max_iterations}")

            # 构建消息
            messages = agent_llm.build_messages(
                system_prompt=system_prompt,
                conversation_history=self.conversation_history,
                user_input=user_input,
                tool_results=self.state.tool_results
            )

            # 获取工具定义
            tools = [
                {
                    "type": "function",
                    "function": {
                        "name": tool_def.get("name"),
                        "description": tool_def.get("description"),
                        "parameters": tool_def.get("parameters", {})
                    }
                }
                for tool_def in self.tools.values()
            ]

            # 调用 LLM
            try:
                response = agent_llm.generate(messages, tools if tools else None)
                logger.debug(f"[AGENT] LLM 原始响应: {response}")

                if response.get("error"):
                    return {
                        "success": False,
                        "error": response.get("error"),
                        "thoughts": self.state.thoughts
                    }

                content = response.get("message", {}).get("content", "")

            except Exception as e:
                logger.error(f"[AGENT] LLM 调用失败 - 错误:{e}")
                return {
                    "success": False,
                    "error": str(e),
                    "thoughts": self.state.thoughts
                }

            # 解析响应
            parsed = self._parse_agent_output(content)
            logger.debug(f"[AGENT] 解析结果: {parsed}")

            # 检查是否完成
            if parsed["action"] and parsed["action"].get("name") == "finish":
                self.state.final_result = parsed["action"].get("result", content)
                self.state.current_step = "complete"
                self._add_to_history("assistant", self.state.final_result)
                break

            # 执行动作
            if parsed["action"]:
                self.state.current_step = "act"
                tool_result = self._execute_action(parsed["action"])
                self.state.tool_results.append(tool_result)

                observation = ""
                if tool_result.success:
                    observation = f"工具执行成功: {tool_result.data}"
                else:
                    observation = f"工具执行失败: {tool_result.error}"

                self.state.observation = observation
                logger.info(f"[AGENT] 观察: {observation[:100]}...")

                # 添加到历史
                self._add_to_history("assistant", parsed["thought"])
                self._add_to_history("tool", observation)

                self.state.current_step = "observe"
            else:
                # 没有动作，直接返回内容
                self.state.final_result = content
                self._add_to_history("assistant", content)
                self.state.current_step = "complete"
                break

        logger.info(f"[AGENT] 处理完成 - 迭代次数:{iteration + 1}, 最终结果长度:{len(self.state.final_result or '')}")

        return {
            "success": True,
            "result": self.state.final_result,
            "thoughts": self.state.thoughts,
            "tool_results": [r.to_dict() for r in self.state.tool_results],
            "iterations": iteration + 1
        }

    def process_simple(self, user_input: str, user_id: int = 1) -> Dict:
        """
        简化处理流程 - 优化的对话流程

        流程：
        1. 用户输入信息
        2. 构建 prompt + 用户输入信息 给 llm, 看需要查询什么记忆
        3. 按照 llm 提示查询本地记忆
        4. 本地记忆查询内容 + 用户输入信息 + 记忆提取 prompt 给到 llm
        5. llm 返回记忆提取内容 以及 对用户输入信息的回复
        6. 本地服务更新记忆, 如果有冲突以最新记忆为准

        Args:
            user_input: 用户输入
            user_id: 用户 ID

        Returns:
            响应结果
        """
        logger.info(f"[AGENT] 简化处理开始 - 用户输入:{user_input[:100]}...")

        # Step 1: 用户输入信息
        self._add_to_history("user", user_input)

        # Step 2: 构建 prompt + 用户输入信息 给 llm, 看需要查询什么记忆
        logger.info("[AGENT] Step 2: 分析需要查询的记忆类型")
        analysis_result = memory_router.analyze_memory_need(user_input)
        logger.info(f"[AGENT]   记忆分析完成 - 类型:{analysis_result.get('recommended_memory_types', [])}")

        # Step 3: 按照 llm 提示查询本地记忆
        memory_context = []
        if analysis_result.get("needs_memory_query", False):
            logger.info("[AGENT] Step 3: 查询本地记忆")
            try:
                memory_context = memory_service.search_memories_by_analysis(
                    user_id=user_id,
                    analysis_result=analysis_result,
                    top_k=5
                )
                logger.info(f"[AGENT]   查询到 {len(memory_context)} 条相关记忆")
            except Exception as e:
                logger.error(f"[AGENT]   查询记忆失败 - 错误:{e}")

        # Step 4: 本地记忆查询内容 + 用户输入信息 + 记忆提取 prompt 给到 llm
        logger.info("[AGENT] Step 4: 构建 prompt 并调用 LLM")

        # 构建系统提示
        system_prompt = "你是一个智能助手。请回答用户问题。"

        # 添加记忆上下文
        if memory_context:
            memory_text = "\n".join([f"- {m['content']} (相似度: {m['similarity']:.2f})" for m in memory_context])
            system_prompt += f"\n\n用户背景信息（基于语义检索的记忆）：\n{memory_text}"

        # 构建完整 prompt
        full_prompt = f"{system_prompt}\n\n用户: {user_input}\n\nAI:"

        # Step 5: LLM 返回记忆提取内容以及对用户输入信息的回复
        try:
            logger.info("[AGENT] Step 5: LLM 生成响应")
            response_content = agent_llm.generate(
                [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": full_prompt}
                ]
            )

            content = response_content.get("message", {}).get("content", "")
            logger.debug(f"[AGENT]   LLM 响应长度:{len(content)}")

        except Exception as e:
            logger.error(f"[AGENT]   LLM 调用失败 - 错误:{e}")
            content = "抱歉，我遇到了一些问题。请稍后重试。"

        # Step 6: 本地服务更新记忆
        memory_updates = []
        if memory_context:
            try:
                logger.info("[AGENT] Step 6: 更新记忆")
                extraction_result = memory_extractor.extract_memories(
                    user_input=user_input,
                    ai_response=content,
                    context_memories=memory_context
                )

                logger.info(f"[AGENT]   提取到 {extraction_result.get('extracted_count', 0)} 条新记忆")

                for mem_data in extraction_result.get("memories", []):
                    try:
                        result = memory_service.update_or_create_memory(
                            user_id=user_id,
                            content=mem_data.get("content", ""),
                            memory_type=mem_data.get("type", "semantic"),
                            category=mem_data.get("category", "general"),
                            importance=mem_data.get("importance", 5)
                        )
                        mem_data["action"] = result.get("action", "created")
                        memory_updates.append(mem_data)
                    except Exception as e:
                        logger.error(f"[AGENT]   更新记忆失败 - 错误:{e}")

            except Exception as e:
                logger.error(f"[AGENT]   记忆更新失败 - 错误:{e}")

        # 添加到历史
        self._add_to_history("assistant", content)

        return {
            "success": True,
            "result": content,
            "memory_updates": memory_updates,
            "memory_context": memory_context,
            "analysis_result": analysis_result
        }

    def reset(self):
        """重置 Agent"""
        self.conversation_history = []
        self.state = AgentState()
        logger.info("[AGENT] Agent 已重置")


# 全局实例
agent = Agent()
