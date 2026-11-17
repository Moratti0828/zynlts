# InternLM GGUF 量化内容来源核验（2026-10-20）

结论：**当前 Ollama 分发与官方 2024 年固定 GGUF 的量化 tensor 不一致，不能认证为内容等价。** 两个完整文件均存在，整文件 SHA-256 均匹配各自预期；32 字节的体积差并不能解释全部内容变化。

|核验项|结果|
|---|---|
|当前 Ollama 权重文件|`sha256-6226fc28c1bb045822d40341ef9062e5f4ea89adc851f9757e1fb6c832e52980`，4,712,768,352 字节|
|官方 GGUF 文件|`sha256-450ef0b157ee10586bb8fce4c5173ae1799345c43c537a6a7353518df1079f55`，4,712,768,320 字节|
|GGUF 版本|两者均为 v3|
|Tensor 数量与目录|两者均为 291；名称、尺寸、类型、相对 offset 逐项一致|
|F32 tensor|65 / 65 的实际 payload SHA-256 相同|
|量化 tensor|193 个 Q4_K 与 33 个 Q6_K，共 226 个；226 / 226 的实际 payload SHA-256 不同|
|实际 tensor payload 总字节|两者均为 4,710,625,280；SHA-256 不同|
|Metadata|两者均为 24 项，其中 3 项不同|
|数据区起始位置|Ollama 2,143,072；官方 2,143,040 字节|
|新增模型下载 / 模型调用|0 字节 / 0 次|

三个不同的 metadata 项均属于 tokenizer：`tokenizer.ggml.scores`、`tokenizer.ggml.token_type`、`tokenizer.ggml.tokens`。三者数组长度均为 92,544。完整证据保存各数组的内容规范化 SHA-256、元素类型、长度和前三项。`tokenizer.chat_template` 的内容相同；本结论不等于 Ollama 的外层 Modelfile 模板相同，后者未在此次核验范围内。

官方来源为 `internlm/internlm2_5-7b-chat-gguf`，固定 revision `8fa9dff166b63e3d356b3a3ca95c5ab2a4b1b378`（仓库 metadata 的 lastModified 为 2024-07-16），文件 `internlm2_5-7b-chat-q4_k_m.gguf`。本地已保存的官方 API metadata 中，LFS 大小和 SHA-256 与本次服务器完整文件读取结果一致。

这些差异可能涉及转换、量化版本或 tokenizer 处理；本次只读核验不能判定其成因，也不能据此推断模型在 2024 年后重新训练或已经见过近期文章。当前分发的严格历史来源仍不确定，结果应单独标注，不应借官方 2024 revision 给当前不同的量化文件背书。若后续需要严格固定来源，可从**服务器已有的、此次已核验的官方完整 blob**创建独立模型并记录新的模板与摘要；此次没有创建或修改任何模型。

方法：Python 标准库按 GGUF v3 逐项解析；每个完整文件做 SHA-256，每个 tensor 按 ggml block 大小计算实际 payload 长度后单独 SHA-256，排除对齐填充。未加载 tensor 到 GPU，没有执行推理。脚本用三组微型 GGUF 验证：相同 payload / 不同 metadata 可以识别；payload 改变被拒绝；整文件预期 hash 不匹配被拒绝。

完整证据：`output/internlm-gguf-provenance-20261020.json`。可复现脚本：`scripts/compare_gguf_payloads_20261020.py`。此次未改后端、题库、模型配置或既有实验结果；不构成人工题目复核。
