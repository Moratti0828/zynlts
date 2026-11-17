"""Rebuild source-grounded, AI-authored development drafts; never run a model.

Presentation scopes below are declared independently of question answers. Source
snapshots and old pilot questions are immutable inputs. Human review stays zero.
"""
from __future__ import annotations

import copy
from collections import Counter
import hashlib
import json
from pathlib import Path
import re

from backend.benchmark_v2 import grade, validate_bank
from backend.corpus_workspace import _records
from backend.experiment_v2 import messages
from backend.token_budget import prepare_budget

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data/annotation/dev-expanded-20261020.json"
VALIDATION = ROOT / "output/dev-expanded-validation-20261020.json"
DATE = "2026-10-20"


def sha(value: str | bytes) -> str:
    return hashlib.sha256(value.encode("utf-8") if isinstance(value, str) else value).hexdigest()


def choice(dim: str, prompt: str, support: list[int], correct: str,
           options: list[str], **extra: object) -> dict:
    return dict(dimension=dim, kind="choice", prompt=prompt,
                support=support, correct_option=correct,
                options=dict(zip("ABCD", options)), **extra)


def short(dim: str, prompt: str, support: list[int], answers: list[str], **extra: object) -> dict:
    return dict(dimension=dim, kind="short", prompt=prompt, support=support, answers=answers, **extra)


def numeric(dim: str, prompt: str, support: list[int], value: str, unit: str,
            **extra: object) -> dict:
    return dict(dimension=dim, kind="numeric", prompt=prompt, support=support,
                value=value, unit=unit, absolute_tolerance="0", **extra)


def unknown(prompt: str, missing: str) -> dict:
    return dict(dimension="D6", kind="unanswerable", prompt=prompt,
                support=[], missing_information=missing)


# Full consecutive source paragraphs, except explicit publication boilerplate
# or navigation removal. Rice's entire table is merged as one evidence block,
# keeping every row/header/footnote in order and recording original indexes.
SCOPES: dict[int, dict] = {
    1: {"kind": "full", "merge": (6, 40), "note": "完整正文；源段6—40整张表（含表头、空白行、注释）合并为一段，原序号保留。"},
    2: {"kind": "full", "note": "完整正文及图注，未按题目挑选段落。"},
    8: {"kind": "full", "note": "完整四段会议报道，未删减。"},
    11: {"kind": "excerpt", "start": 1, "end": 6, "note": "固定保留连续主文1—6段；源7—16为Related Terms和Explore More导航，不作为文章正文。"},
    14: {"kind": "excerpt", "start": 1, "end": 8, "note": "固定连续新闻主文1—8段；源9—11为机构介绍及宣传标语，不纳入呈现。"},
    18: {"kind": "full", "note": "完整十段拨款报道，含项目与更多信息链接；未按答案删段。"},
}


QUESTIONS: dict[int, list[dict]] = {
    1: [
        numeric("D1", "根据2026年早稻公告，全国早稻单位面积产量是多少？answer只写数值，unit写“公斤/公顷”。", [3], "5963.4", "公斤/公顷"),
        numeric("D4", "按2026年分省表，湖南早稻总产量比江西多多少？answer只写差额，unit写“万吨”。", [6], "51.8", "万吨", operation={"type": "subtract", "operands": ["740.4", "688.6"], "formula": "740.4-688.6=51.8"}),
        choice("D2", "阅读2026年分地区表及表下注释，对表中未列出数值的省份应怎样理解？只答选项ID。", [6], "C", ["表示产量必定高于全国均值", "表示该省数据因四舍五入而保密", "按注释，这些未列出的省份没有早稻生产", "表示该省早稻产量恰等于全国总计"]),
        choice("D3", "结合公告的面积变化、单产变化和产量计算方法，哪种解释与2026年全国早稻数据一致？只答选项ID。", [2, 3, 14], "B", ["总产量只由面积决定，与单产无关", "面积略增，但单产下降，二者相乘后的总产量可以下降", "单产上涨抵消了面积下降", "表中产量不是根据面积与单产计算"], reasoning_steps=["源段2给出面积略增，源段3给出单产下降0.8%。", "源段48明确产量由面积与单产相乘，因此两者需合并判断。"]),
        choice("D5", "有人把公告中的2026年早稻总产量称为“对每一块早稻田逐块普查后直接相加的结果”。文中是否支持？只答选项ID。", [8], "D", ["支持，文中说对所有地块普查", "支持，因为省级数据必定来自逐块普查", "无法判断，文中没说明调查方式", "不支持，文中说明由以省为总体的抽样调查得出"]),
        short("D3", "只比较2026年表中的江西和湖南，哪个省播种面积更大、但总产量更小？只写省名。", [6], ["江西", "江西省"], reasoning_steps=["表中江西播种面积1213.4千公顷，大于湖南1205.5千公顷。", "江西总产量688.6万吨，小于湖南740.4万吨，两个条件共同定位江西。"]),
        unknown("2026年湖南早稻的平均售粮价格是多少元/公斤？若正文不能确定，请拒答。", "公告有面积、单产和产量，没有任何早稻售价；产量不能推出售价。"),
        unknown("2026年江西早稻因洪涝损失的具体产量是多少万吨？若正文不能确定，请拒答。", "分省表只有当年总量，没有灾害损失量或反事实无灾产量，不能把与其他省的差额当损失。"),
    ],
    2: [
        short("D1", "这项月壤水冰热导率研究采用的玄武质月壤模拟物型号是什么？只写型号。", [2], ["IRSM-L1"]),
        choice("D2", "文中两类含冰样品具有近似水冰含量，为什么仍可有不同热导率？只答选项ID。", [3], "A", ["孔隙冰形态、颗粒接触关系和导热通路不同", "两类样品完全没有固态水冰", "样品型号分别来自不同真实月球极区", "因为试验完全没有控制温度和压力"]),
        choice("D3", "结合制样方法和热导率增长路径，哪项配对正确？只答选项ID。", [3, 4], "C", ["液态水原位冻结对应离散冰颗粒混合型，增长更慢", "两类都先制离散冰颗粒，因此都只有缓慢增长", "液态水在孔隙中原位冻结形成冰胶结型，其连续骨架使热导率增长更快", "预制离散冰颗粒混合对应冰胶结型，其热导率不随饱和度变化"], reasoning_steps=["源段3区分液态水原位冻结的冰胶结型与预制冰粒混合型。", "源段4把胶结型的更快S型增长连接到冰桥、冰颈与连续导热骨架。"]),
        choice("D5", "“只测热导率，就能唯一确定月壤水冰含量，不必考虑冰形态。”文中研究是否支持这一结论？只答选项ID。", [6], "B", ["支持，文中把热导率当作单一丰度代理", "不支持，热导率同时响应含量和形态，相同热导率可对应不同含量", "支持，因为真空下没有任何热传输", "无法判断，正文完全未讨论储量反演"]),
        short("D1", "研究用哪一种显微观察方法证实冰胶结型样品存在颗粒间冰桥和胶结接触？只写方法名称。", [5], ["冷冻扫描电镜", "冷冻扫描电镜观察", "冷冻扫描电子显微镜"]),
        choice("D2", "为什么冰胶结型样品在高饱和度阶段，继续增加冰含量带来的导热增益趋弱？只答选项ID。", [5], "D", ["因为全部冰桥立即融化为液态水", "因为孔隙气压必定降为零", "因为所有颗粒接触被切断", "因为大部分有效孔隙已被连通冰占据"]),
        unknown("这项试验在水冰饱和度恰为50%时测得的热导率数值是多少W/(m·K)？若正文不足，请拒答。", "文字只描述增长路径，没有50%饱和度时的热导率数值；图注也没有该数值，不能凭机制猜数。"),
        unknown("根据该报道，月球南极可开采水冰总储量精确为多少吨？若正文不足，请拒答。", "报道阐释模拟物实验和储量评估机制，没有给月球南极可开采储量数值。"),
    ],
    8: [
        short("D1", "2026年这次秦岭协同座谈会在哪个城市召开？只写城市名。", [1], ["十堰", "十堰市", "湖北十堰", "湖北省十堰市"]),
        short("D1", "会议宣布正式上线的平台名称是什么？只写正文中的名称。", [1], ["秦岭信息平台"]),
        choice("D2", "关于把地方主动发现问题和整改成效纳入考核加分项，文章表达的是哪种状态？只答选项ID。", [3], "B", ["已经全国统一实施，并公布了全部得分", "要研究纳入，以激励机制支持监管水平提高", "明确禁止地方主动发现问题", "只奖励问题数量，不考虑整改成效"]),
        choice("D3", "哪项同时正确概括信息平台的当前状态和会议要求的后续用途？只答选项ID。", [1, 3], "C", ["尚未上线；下一步停止宣传教育", "尚未上线；只用于核算工业利润", "已经正式上线；用好平台等资源加强宣传教育及舆论引导", "已经正式上线；下一步取消公众参与"], reasoning_steps=["源段1给出秦岭信息平台正式上线。", "源段3第六项要求用好跨区域协同信息平台等资源，加强宣传教育及舆论引导。"]),
        choice("D5", "有人说：“这次会议认为相邻行政区保护区域管理已经完全一致，无需继续协调。”文中是否支持？只答选项ID。", [3], "A", ["不支持，下一步仍要梳理区域不连续和管理不一致问题", "支持，第一项工作就是取消所有跨区域监管", "支持，会议明确说无需提高一致性", "无法判断，文中完全没有提保护区域管理"]),
        numeric("D1", "本次会议明确提出下一步重点做好几个方面工作？answer只写数量，unit写“项”。", [3], "6", "项"),
        unknown("本次正式上线的秦岭信息平台建设总预算具体是多少万元？若正文不能确定，请拒答。", "正文只说正式上线，没有平台预算或建设成本。"),
        unknown("会议提及的三年行动计划，确切起始日期和终止日期分别是哪一天？若正文不能确定，请拒答。", "正文要求出台三年行动计划，但未给起止年月日；不能用会议日期自行推定。"),
    ],
    11: [
        short("D1", "What is the name of the standard wind-tunnel model used in the reported test? Give only its name.", [2], ["Benchmark Supercritical Wing", "the Benchmark Supercritical Wing"]),
        short("D1", "At which NASA research center did the reported tests take place? Give only the center name.", [1], ["Langley Research Center", "NASA Langley Research Center", "NASA’s Langley Research Center"]),
        choice("D2", "How should the benchmark wing's relationship to an actual aircraft type be understood? Return only the option ID.", [3], "D", ["It is an exact prototype of one named passenger aircraft", "It represents every aircraft's final production design", "It was built solely to identify the model of an unknown aircraft", "It is a universal model, rather than a representation of a particular aircraft type"]),
        choice("D3", "How do the benchmark wing and the paint measurements contribute together to computer modeling? Return only the option ID.", [3, 4], "B", ["A particular aircraft is identified by paint color, so no pressure data are needed", "The universal wing supplies a modeling benchmark, while pressure-dependent brightness recorded by cameras supplies data", "The paint directly replaces every computer simulation with a finished aircraft", "The benchmark wing measures passengers and the cameras count seats"], reasoning_steps=["Paragraph3 defines benchmark wings as universal models for improving computer models with tunnel data.", "Paragraph4 explains pressure-dependent brightness and camera capture as the source of that data."]),
        choice("D5", "Does the article report that these tests have already demonstrated a measured efficiency gain in flexible aircraft during flight? Return only the option ID.", [6], "C", ["Yes; the article reports the exact in-flight percentage gain", "Yes; it states the flexible aircraft are already in commercial service", "No; the milestone opens the door to upcoming tests on such models", "No; it proves flexible aircraft can never improve efficiency"]),
        short("D1", "In what oxygen condition was the large-scale, freely moving model tested for the technique's first such use? Use the phrase in the passage.", [5], ["a low-oxygen environment", "low-oxygen environment", "low‑oxygen environment", "a low‑oxygen environment"]),
        unknown("What exact air pressure, in pascals, was applied to the wing when the paint glowed pink-purple? Abstain if the passage does not determine the number.", "The text describes pressure-sensitive brightness and UV illumination but reports no pressure value in pascals."),
        unknown("By what exact percentage did these tests improve the fuel efficiency of an aircraft in actual flight? Abstain if the passage does not determine the number.", "The efficiency benefit concerns future flexible-model work; no measured in-flight percentage is supplied."),
    ],
    14: [
        short("D1", "What is the name of the experimental PubMed tool launched in this article? Give only the tool name.", [2], ["Linked Discoveries"]),
        short("D1", "Which NIH library developed the tool? Give only its full name or abbreviation.", [3], ["National Library of Medicine", "NIH’s National Library of Medicine", "NLM", "the National Library of Medicine"]),
        choice("D2", "Which activity is explicitly outside the tool's stated role? Return only the option ID.", [6], "A", ["Judging study quality or deciding whether a finding has been successfully replicated", "Organizing connections among publications", "Providing context for researchers to evaluate evidence", "Leaving scientific assessment to researchers"]),
        choice("D3", "Which pairing correctly describes an available filtering feature and responsibility for assessing evidence? Return only the option ID.", [5, 6], "D", ["Filter by genes; the tool certifies successful replication", "Filter by hospital billing codes; researchers assess quality", "Filter by genes; the tool replaces researchers' quality assessment", "Filter by genes; researchers still assess quality and replication themselves"], reasoning_steps=["Paragraph5 describes gene filters and retraction/citation context.", "Paragraph6 explicitly withholds study-quality and replication judgements from the tool."]),
        choice("D5", "Does finding a paper connected to other publications in Linked Discoveries establish that its finding was successfully replicated? Return only the option ID.", [6], "B", ["Yes; every connection is a replication certificate", "No; the tool organizes connections and does not determine successful replication", "Yes; only replicated papers are included", "No; the tool states that all connected findings are false"]),
        choice("D2", "What does the article say about the September 24 release and subsequent development? Return only the option ID.", [8], "C", ["It is the final version and feedback is disabled", "It predates the first public version by five years", "It is the first public version, and NLM will refine it using user feedback", "It is a private release accessible only to its developers"]),
        unknown("What fraction of all studies represented at launch had already been successfully replicated? Abstain if the passage does not determine the fraction.", "The article reports coverage but supplies no replicated-study count or fraction; the tool does not itself determine replication success."),
        unknown("What was the exact total dollar cost of developing the launched tool? Abstain if the passage does not determine the cost.", "No development cost or budget is supplied anywhere in the presented main article."),
    ],
    18: [
        short("D1", "For which Pennsylvania county will the funded project develop a high-resolution landslide inventory and susceptibility map? Give only the county name.", [6], ["Washington County", "Washington"]),
        numeric("D1", "Over how many years will the Pennsylvania project described in the article develop its inventory and map? Write only the number in answer and use unit=\"years\".", [6], "2", "years"),
        choice("D2", "Does the article's count of 16 recipients mean that 16 separate state governments received the grants? Return only the option ID.", [1, 2], "B", ["Yes; all recipients are explicitly state governments", "No; the 16 recipients include state, local and Tribal governments", "Yes; local and Tribal governments are explicitly excluded", "No; there were only two recipients in total"]),
        choice("D3", "Which pairing correctly distinguishes the Pennsylvania and Nevada projects? Return only the option ID.", [6, 7], "A", ["Pennsylvania: Washington County map; Nevada: first statewide inventory plus post-wildfire watershed assessments", "Pennsylvania: first Nevada statewide map; Nevada: Washington County map", "Both: only a nationwide school curriculum, with no mapping", "Pennsylvania: spacecraft testing; Nevada: hospital treatment trials"], reasoning_steps=["Paragraph6 places the county map and I-79 planning work in Pennsylvania.", "Paragraph7 places the statewide inventory and post-wildfire watershed assessments in Nevada."]),
        numeric("D4", "Using the total grant amount and number of recipients reported in the article, calculate the arithmetic mean per recipient. This does not determine any individual award. Write the average in answer and unit=\"USD per recipient\".", [2], "62500", "USD per recipient", operation={"type": "divide", "operands": ["1000000", "16"], "formula": "1000000/16=62500", "interpretation": "Arithmetic average only, not an observed award to any recipient."}),
        choice("D5", "Does the article establish that all funded projects have already finished and eliminated landslide risk? Return only the option ID.", [4], "D", ["Yes; completed projects are said to have eliminated every landslide", "Yes; the annual grants guarantee zero future hazards", "No; it says none of the grants supports public safety", "No; the recipients will undertake research and mapping projects, rather than reporting completed elimination of risk"]),
        unknown("What exact dollar amount was awarded to the Nevada Bureau of Mines and Geology? Abstain if the passage does not determine the individual award.", "Only the overall $1 million total for16 recipients is given; an arithmetic average does not identify Nevada's award."),
        unknown("Exactly how many landslide deaths will these grants prevent in fiscal year 2027? Abstain if the passage does not determine the number.", "The article describes intended risk reduction but provides no quantified causal estimate of future deaths prevented."),
    ],
}


def source_paragraphs(record: dict) -> list[str]:
    text = (ROOT / record["text_path"]).read_text(encoding="utf-8")
    if text.endswith("\n"):
        text = text[:-1]
    if sha(text) != record["sha256"]:
        raise ValueError(f"Source body hash mismatch: {record['id']}")
    if sha((ROOT / record["raw_path"]).read_bytes()) != record["raw_sha256"]:
        raise ValueError(f"Source raw hash mismatch: {record['id']}")
    return [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]


def build_article(record: dict, source: dict, index: int) -> dict:
    scope = SCOPES[index]
    original = source_paragraphs(record)
    aid = record["id"] + "-dev20261020"
    start, end = scope.get("start", 1), scope.get("end", len(original))
    merge = scope.get("merge")
    paragraphs = []
    cursor = start
    while cursor <= end:
        indexes = list(range(cursor, merge[1] + 1)) if merge and cursor == merge[0] else [cursor]
        text = "\n".join(original[n - 1] for n in indexes)
        paragraphs.append({"id": f"{aid}:p{len(paragraphs)+1:03d}", "text": text,
                           "source_paragraph_indexes_1_based": indexes})
        cursor = indexes[-1] + 1
    questions = []
    for number, authored in enumerate(QUESTIONS[index], 1):
        q = copy.deepcopy(authored)
        support = q.pop("support")
        q.update(id=f"q{number:02d}", evidence_sets=[[paragraphs[n - 1]["id"] for n in support]] if support else [],
                 annotation_state="ai_checked", generator="Codex source-grounded authoring, 2026-10-20",
                 human_reviews=[], adjudication_complete=False, human_review_count=0,
                 answer_novelty_review_state="pending_human_review",
                 training_seen_status="unknown")
        questions.append(q)
    return dict(id=aid, title=record["title"], language=record["language"],
                source_cluster_id=record["id"], proposed_source_cluster=record["proposed_source_cluster"],
                source_cluster_reviewed=False, source_url=record["source_url"], source_name=record["source_name"],
                agency_group=record["agency_group"], published_at=record["published_at"],
                first_published_at=record.get("first_published_at"), date_evidence=record["date_evidence"],
                rights=source["rights"], source_text_sha256=record["sha256"],
                source_raw_sha256=record["raw_sha256"], source_raw_path=record["raw_path"],
                source_text_path=record["text_path"], scope=scope["kind"], scope_note=scope["note"],
                scope_declared_before_question_authoring=True, split="development", domain=record["domain_proposed"],
                length_bin=record["presentation_proposal"]["length_bin"], annotation_state="ai_checked",
                formal=False, human_review_count=0, globally_earliest_publication_proven=False,
                publication_date_is_answer_novelty_proof=False, training_seen_status="unknown",
                risk_flags=record["known_risk_flags"], time_review_note=record["scope_and_time_note"],
                related_candidates_blocked_from_hidden_split=record["provisional_hidden_split_block_candidate_ids"],
                paragraphs=paragraphs, presented_text_sha256=sha("\n\n".join(p["text"] for p in paragraphs)),
                questions=questions)


def verify(bank: dict, records: list[dict]) -> dict:
    articles = validate_bank(bank, allow_draft=True)
    try:
        validate_bank(bank, allow_draft=False)
    except ValueError as exc:
        formal_rejection = str(exc)
    else:
        raise AssertionError("AI draft unexpectedly accepted as formal")
    bundle = ROOT / "runtime/tokenizers/qwen25-7b-a09a354"
    manifest = json.loads((bundle / "manifest.json").read_text(encoding="utf-8"))
    qwen = {"tokenizer_spec": {"repo_id": manifest["repo_id"], "revision": manifest["revision"],
             "artifact_dir": str(bundle), "manifest_sha256": sha((bundle / "manifest.json").read_bytes())},
            "runtime_template_kind": "raw_rendered_prompt", "token_budget_margin": 512}
    checks = []
    for a in articles:
        assert len(a["questions"]) == 8
        assert sum(q["kind"] == "unanswerable" for q in a["questions"]) == 2
        assert a["human_review_count"] == 0 and a["annotation_state"] == "ai_checked"
        row = {"article_id": a["id"], "language": a["language"], "question_count": 8,
               "newly_authored": not a.get("reused_from_bank"), "budgets": [], "reference_self_checks": []}
        for q in a["questions"]:
            unknown_q = q["kind"] == "unanswerable"
            answer = "" if unknown_q else q.get("correct_option", q.get("value", q.get("answers", [""])[0]))
            response = {"answer": answer, "unit": q.get("unit", ""),
                        "evidence_ids": [] if unknown_q else q["evidence_sets"][0],
                        "abstain": unknown_q, "confidence": 1.0}
            graded = grade(q, response, [p["id"] for p in a["paragraphs"]], language=a["language"])
            assert graded["answer_correct"] == 1, (a["id"], q["id"], graded)
            prompt = messages(a, q, "with_context")
            exact = prepare_budget(qwen, prompt, 512, 8192, strict=True)
            fallback = prepare_budget({}, prompt, 512, 8192, strict=False)
            assert exact["allowed"], (a["id"], q["id"], exact["reason"])
            row["budgets"].append({"question_id": q["id"], "qwen_native_total_tokens": exact["total_tokens"],
                                   "qwen_native_input_tokens": exact["input_tokens"],
                                   "draft_utf8_total_bound": fallback["total_tokens"],
                                   "draft_utf8_admitted": fallback["allowed"]})
            row["reference_self_checks"].append({"question_id": q["id"], "answer_correct": 1,
                                                 "evidence_exact": graded["evidence_exact"],
                                                 "scope": "Scorer plumbing only; not an independent gold correctness review."})
        checks.append(row)
    langs = Counter(a["language"] for a in articles)
    return {"checked_on_client_date": DATE, "schema_validation_passed": True,
            "bank_sha256": sha(OUTPUT.read_bytes()), "formal_rejected_as_expected": formal_rejection,
            "counts": {"articles": len(articles), "questions": sum(len(a["questions"]) for a in articles),
                       "languages": dict(langs), "human_reviewed_articles": 0, "human_reviewed_questions": 0,
                       "newly_authored_articles": sum(not a.get("reused_from_bank") for a in articles),
                       "reused_pilot_articles": sum(bool(a.get("reused_from_bank")) for a in articles)},
            "source_bodies_and_raw_sha256_verified": len(records), "articles": checks,
            "all_qwen_native_budgets_pass": True,
            "all_draft_utf8_budgets_pass": all(b["draft_utf8_admitted"] for a in checks for b in a["budgets"]),
            "limitations": ["All questions are AI authored, human0, development only.",
                            "Reference round-trip is not independent validation of gold answers.",
                            "Page publication date does not prove question-answer novelty or training non-membership.",
                            "Exact native budget identity is Qwen2.5-7B only; other families use draft estimate unless separately certified."]}


def main() -> None:
    from .dev_expanded_additional_20261020 import SCOPES as more_scopes, QUESTIONS as more_questions
    SCOPES.update(more_scopes)
    QUESTIONS.update(more_questions)
    selection_path = ROOT / "data/annotation/development-selection-20261013.json"
    selection = json.loads(selection_path.read_text(encoding="utf-8"))["records"]
    sources = {r["id"]: r for r, _ in _records(ROOT)[0]}
    pilot_path = ROOT / "data/annotation/dev-pilot-v2.json"
    pilot = json.loads(pilot_path.read_text(encoding="utf-8"))
    existing = {a["source_cluster_id"]: a for a in pilot["articles"]}
    articles = []
    used = []
    for index, record in enumerate(selection):
        if record["id"] in existing:
            source_paragraphs(record)
            article = copy.deepcopy(existing[record["id"]])
            article.update(reused_from_bank="dev-pilot-v2", reused_bank_sha256=sha(pilot_path.read_bytes()),
                           proposed_source_cluster=record["proposed_source_cluster"],
                           time_review_note=record["scope_and_time_note"], risk_flags=record["known_risk_flags"],
                           globally_earliest_publication_proven=False, training_seen_status="unknown",
                           publication_date_is_answer_novelty_proof=False,
                           related_candidates_blocked_from_hidden_split=record["provisional_hidden_split_block_candidate_ids"])
        elif index in QUESTIONS:
            article = build_article(record, sources[record["id"]], index)
        else:
            continue
        articles.append(article)
        used.append(record)
    # Independent AI source audit, completed before testing this expanded bank.
    # Alternatives are equivalent complete support, never model-output repair.
    audit_fixes = {
        "zh-nbs-d8dd3b95e0c6": {"q01": {"extra_support": [[6]]}},
        "zh-cas-5dc9ec97bf04": {"q01": {"extra_support": [[8]]}, "q03": {"extra_support": [[3, 5]]},
            "q05": {"extra_answers": ["冷冻扫描电子显微镜观察"]}},
        "zh-mee-161477ffc17c": {"q02": {"extra_support": [[3]], "extra_answers": ["秦岭生态保护跨区域协同信息平台"]}},
        "en-nasa-2b3fb9c367c3": {"q02": {"extra_support": [[2]], "extra_answers": ["Langley", "NASA Langley"]}},
        "en-nih-88aa9c4bbbb9": {"q01": {"extra_support": [[8]]}},
        "en-usgs_release-8091ff19244f": {"q03": {"replace_support": [[2]]}},
        "en-census-8b06d9bbd7de": {"q01": {"extra_support": [[19]]}, "q03": {"extra_support": [[18]]}, "q06": {"extra_support": [[8]]}},
        "en-census-be20ba82c0cc": {"q01": {"extra_support": [[6]]}},
        "en-govuk-d5865b812982": {"q01": {"extra_support": [[4]]}, "q02": {"extra_support": [[17]]}},
        "zh-cas_health-d9258d90ea32": {"q03": {"replace_support": [[2], [3]]}},
        "zh-cas_health-31517790bbba": {"q01": {"extra_support": [[8]]}},
        "zh-mct_local-f4d9389d2865": {"q06": {"replace_support": [[6]]}},
        "zh-mct-2310a232a3eb": {"q04": {"extra_support": [[6]]}},
        "en-nih-63b73a8c608a": {"q05": {"replace_support": [[3]]}},
        "en-loc-359fbdc1a252": {"q01": {"extra_support": [[4]]}},
        "en-loc-829b92bd1e91": {"q04": {"replace_support": [[7]]}},
    }
    for article in articles:
        fixes = audit_fixes.get(article["source_cluster_id"], {})
        for question in article["questions"]:
            fix = fixes.get(question["id"], {})
            mapped = [[article["paragraphs"][n-1]["id"] for n in support]
                      for support in fix.get("replace_support", fix.get("extra_support", []))]
            if "replace_support" in fix:
                question["evidence_sets"] = mapped
            else:
                question["evidence_sets"].extend(s for s in mapped if s not in question["evidence_sets"])
            if fix.get("extra_answers"):
                question["answers"].extend(a for a in fix["extra_answers"] if a not in question["answers"])
        article["ai_source_audit"] = {"date": DATE, "human_review": False,
            "model_outputs_consulted": False, "status": "source_read_and_targeted_contract_fixes;human_review_pending"}
    bank = {"schema_version": "reading-bank-v2", "bank_version": "dev-expanded-20261020",
            "formal": False, "human_review_count": 0,
            "note": "真实2026正文的AI编制开发草稿；0人工审题，仅供平台和评分器诊断，不是正式金标或模型排名。复用原2篇不重复计为新文章来源。",
            "as_of_client_date": DATE, "target_articles": 20, "target_questions": 160,
            "source_selection_sha256": sha(selection_path.read_bytes()),
            "pending_source_ids": [r["id"] for r in selection if r not in used],
            "articles": articles}
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(bank, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    validation = verify(bank, used)
    VALIDATION.parent.mkdir(parents=True, exist_ok=True)
    VALIDATION.write_text(json.dumps(validation, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"bank": str(OUTPUT), "validation": str(VALIDATION),
                      "counts": validation["counts"], "all_draft_utf8_budgets_pass": validation["all_draft_utf8_budgets_pass"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
