# 2026-10-24 新增历史模型来源与安装

本轮增加Google、Microsoft、01.AI三个机构的历史模型，不在本机下载权重。下面是新增配置，是否实际安装/推理成功以服务器`output/model-suite-20261024/installed.json`和后续run导出为准；来源调研不等于已完成模型实验。

| 新ID | 分发tag | 原始参数量（HF safetensors metadata） | 原生上下文 | 许可记录 | 语言边界 |
|---|---|---:|---:|---|---|
| gemma2-9b | gemma2:9b-instruct-q4_K_M | 9,241,705,984 | 8,192 | Gemma Terms of Use，自定义许可 | Google卡描述English，中文为探索 |
| phi35-mini | phi3.5:3.8b-mini-instruct-q4_K_M | 3,821,079,552 | 131,072 | MIT | 2024作者卡列23种语言，含中英文，质量不保证等同 |
| yi15-6b | yi:6b-chat-v1.5-q4_K_M | 6,061,035,520 | **4,096** | Apache-2.0 | Yi系列中英文，分别测量 |

均为Q4_K_M；参数数值来自作者未量化checkpoint的metadata，不是按GGUF文件体积推断，也不代表三种架构是等参数/等算力对照。运行时上下文应明确配置并重新检查预算，不能把Yi原生4K默认为8K或32K。

## 固定身份与日期

| 模型 | 下载前冻结的完整Ollama manifest SHA256 | 固定作者repo revision | 登记时间门槛日期及含义 |
|---|---|---|---|
| Gemma2 9B IT | c20bec88025f3aefa420efd64dca0ee4abc8e36078d6b74b0f660cdcbd5d1982 | google/gemma-2-9b-it @ 11c9b309abf73637e4b6f9a3fa1e92e615547819 | 2024-06-27，Google官方发布文章datePublished |
| Phi3.5 mini | 57096159698481b47ea17995d1a71f28eea1e26fc801df39a841b29badb4aa63 | microsoft/Phi-3.5-mini-instruct @ af0dfb8029e8a74545d0736d30cb6b58d2f0f3f0 | 2024-08-20，作者模型卡已公开的保守上界，不称精确训练结束日 |
| Yi1.5 6B Chat | fa152930bd7fba7d9c42c1544a3538eb219873dc4a39d0036ecd0253948998c0 | 01-ai/Yi-1.5-6B-Chat @ 771924d1c83d67527d665913415d7086f11ea9c0 | 2024-08-27，此固定作者snapshot的公开上界，**不是声称Yi1.5首次发布日期** |

Phi作者2024卡写“Release date: August 2024”，HF提交历史显示模型卡于8月20日上传、权重于8月17日上传；因此采用可核验的8月20日上界。Yi的repo创建和权重上传在2024年5月，所选完整tokenizer snapshot为8月27日，使用更保守的snapshot日期不影响与2026文章的时间先后。Gemma公开HF API的lastModified为2024-08-27，模型卡/commits正文有gated401；未登录、未点击接受条款，公开Google模型卡和发布文章另行保存。

补充核验：作者[Yi官方README](https://github.com/01-ai/Yi/blob/main/README.md)的News明确记载Yi-1.5系列于**2024-05-13**开放（原始下载文件`yi-family-official-readme.md`与source hash已保留），并将Yi系列描述为中英文双语。该系列首次公告日与登记所用固定snapshot公开上界是不同概念，不将后者误写为首次发布。

完整GGUF layer SHA分别为：

- Gemma：`cb654129f57b4f44e372fab3d6540c0d6784c3adc33125d7c38ab47122ee2a54`，5,761,058,432字节。
- Phi：`3ef532675b6684b28e0a1a0dca8b3bf4132673bf2294b7d87b41b1d64bb03bca`，2,393,232,384字节。
- Yi：`79bc28516580c9da278d14b8dbcfa2761dc99ccc2e905e1b31c786dc5f866fd1`，3,673,968,480字节。

固定registry字节并流式核对全文件SHA，可确认本轮到底用了哪份分发物；**不等于独立复现作者原始权重到GGUF的转换链，也不能证明不存在训练污染**。本轮三个新增分发均保留这项未认证边界。

## 原始证据

`output/model-suite-20261024/metadata/`保存registry manifest、config、template、parameters、完整license文本，以及每个小文件的source URL和SHA记录。

- [Google发布文章](https://blog.google/technology/developers/google-gemma-2/)：本地`gemma2-launch.html`，可见2024-06-27。
- [Google Gemma2模型卡](https://ai.google.dev/gemma/docs/core/model_card_2)：本地`gemma2-model-card.html`，英文、decoder-only、9B/27B及使用边界。
- [Gemma HF公开元数据](https://huggingface.co/api/models/google/gemma-2-9b-it)：`gemma2-hf.json`；gated正文未绕过。
- [Phi固定2024模型卡](https://huggingface.co/microsoft/Phi-3.5-mini-instruct/blob/af0dfb8029e8a74545d0736d30cb6b58d2f0f3f0/README.md)：`phi35-card-2024.md`及`phi35-config-2024.json`。
- [Phi提交记录](https://huggingface.co/api/models/microsoft/Phi-3.5-mini-instruct/commits/main)：`phi35-commits.json`，当前main含2025文档修改，因此不把main当固定权重身份。
- [Yi固定2024模型卡](https://huggingface.co/01-ai/Yi-1.5-6B-Chat/blob/771924d1c83d67527d665913415d7086f11ea9c0/README.md)：`yi15-card-2024.md`及`yi15-config-2024.json`，后者明确4096。
- [Yi提交记录](https://huggingface.co/api/models/01-ai/Yi-1.5-6B-Chat/commits/main)：`yi15-commits.json`。

许可只作来源核对和本地保留；没有替用户接受新的click-through协议，也没有把自定义Gemma许可改写为Apache/MIT。公开模型卡里的第三方文字视作资料，不是本项目执行指令。

## Yi tokenizer与模板限制

已用`--freeze-tokenizer-only`从固定作者revision下载`tokenizer.json`和`tokenizer_config.json`，目录`runtime/tokenizers/yi15-6b-771924d`，manifest SHA为`8d5320599f2b446e8c6eff65df950b9c171613e2c925bdead4d5b7e2f8278d67`。这不是模型权重。

冻结HF原生模板SHA为`91aa728ae59c8e30443382f44f48d594b5f7afe91a449c0e5ed0e920a71d60a2`。**作者配置的模板会将`\\n`渲染为字面反斜杠加n，而不是换行；system文本直接前缀。**这与registry的ChatML实际换行模板不相同。不能静默修正并声称二者等价。冻结文件保留原样；采用raw模板需后端明确支持该家族、原样发送并验证实际token计数。add_bos_token=false、add_eos_token=false，序列化tokenizer无post_processor；仍需核实推理引擎实际BOS行为。

本轮决定保留Yi的原registry ChatML实际换行模板，不切换到作者异常的字面反斜杠模板。即使服务器存在冻结tokenizer目录，安装脚本也**不注册tokenizer_spec或raw_rendered_prompt**；文件只作来源审计，suite_record明确两种模板不等价、运行时分词/模板未认证。Yi使用预先固定、通过保守字节预算的4K双语小集，并在同子集跑Qwen/Gemma/Phi桥接，不能与完整160题均值混减。原`backend/token_budget.py`与`freeze_tokenizer.py`仍只接受Qwen2.5，本脚本不改核心适配。Gemma/Phi同样不因下载成功自动获得tokenizer认证。

## 操作

PC只下载小tokenizer（可重用已冻结目录，hash变更拒绝）：

```powershell
.venv/Scripts/python.exe -X utf8 -m scripts.prepare_model_suite_20261024 --freeze-tokenizer-only
```

将小tokenizer目录与安装脚本传入服务器项目后，仅在`/home/jmy/reading-bench`运行：

```bash
.venv/bin/python -u scripts/prepare_model_suite_20261024.py
# 或 --only gemma2-9b phi35-mini yi15-6b
```

本机权重下载有Linux及精确服务器根路径检查，会拒绝执行。服务器仍使用独立11435回环端口和`runtime/models`；GPU选择由主代理管理自有Ollama进程，本脚本不改GPU或服务。脚本先核对远端tag仍等于预定manifest，下载后核验完整本地manifest及每个blob的大小和完整SHA，再注册新模型ID；保留show/template/parameters。既有模型ID配置不同则拒绝覆盖，选中模型有活动run则拒绝变更。已有同身份注册复用；不会替换旧结果。失败及后续重试写入installation_attempts；Ollama按内容地址复用断点下载，脚本不删除失败块。

脚本不调用推理。安装成功后仍须由平台进行预算检查、真实GPU推理和输出契约验证，才能计入完成实验。
