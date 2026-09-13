
## 步骤1 基线核对 (非缺陷记录,计划内核对清单)
- [OK] R-010 端点现状=chat.py:161 frames 零改动可行 (_sniff_video/VIDEO_MAX_MB 复用面确认)
- [OK] save_assistant_message 现签名 (session_id,content,tokens_used=0) [CODE :438] → 默认参扩展向后兼容成立
- [OK] ensure_schema() 已有 messages.images 幂等补列先例 [CODE sql_models.py:372] → extra 列同款落点(修正:设计文档写"_ensure_extra_column()"实际并入 ensure_schema,归档时基线以实际为准)
- [OK] model_manager.supports_vision [CODE :150]、llm.chat messages 内嵌 images [CODE chat_service.py:418] 消费面与设计一致
