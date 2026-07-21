# 部署配置

请填写下方 `## 基本参数`（7 项均为必填）。`## 服务化配置` 可选，用于覆盖模型路径 / host / port。
填写完成后保存，重新向 Agent 发起请求。参考示例：`configuration-tuning-skills/ascend-baseline-generator/config.example.md`

## 基本参数

- 输入长度:
- 输出长度:
- 设备类型:
- 模型名称:
- 量化格式:
- NPU卡数:
- 部署策略:

## 服务化配置

（本节可选，不需要可整节删除）

```bash
vllm serve /path/to/model \
    --host 0.0.0.0 \
    --port 8000
```
