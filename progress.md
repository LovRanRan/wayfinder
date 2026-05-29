---
project: wayfinder
phase: P3
status: building
created: 2026-05-26
soft_deadline: 2026-09-01
hard_deadline: 2026-09-15
---

# Project 6 · `wayfinder` — Progress Tracker

> 单文件进度板 — Description + Dashboard + Roadmap + Logs + Pickup Protocol
> 维护方式:每完成一个动作,先在 Logs 追加一条,再同步 Dashboard 和 Roadmap
> Owner:Haichuan · Start:2026-05-26 · Reference window:Wave 3 前完成 P6 + P7

---

## 📌 Project Description

**`wayfinder`** 是 Phase 3 的 **multi-agent codebase onboarding copilot**。目标是给一个 GitHub repo + 用户问题,由 LangGraph Supervisor 路由到 `architect_mapper` / `entry_explainer` / `verifier`,输出带验证标签的 codebase explanation,从"自信讲解"升级到"讲解 + 自我验证"。

**项目定位**

从 Project 5 `mcp-codebase-tools` 的 deterministic tool layer,推进到可被用户直接使用的 product / agent layer。Project 5 证明"我能写 MCP server";Project 6 证明"我能把 grounded tools 编排成可恢复、可观测、可部署、带 HITL 和 verification 的 agent workflow"。

**技术契约**(对应 `final_checklist.md` Project 6 acceptance,Commit 0 后可细化)

- **Agent graph**:LangGraph Supervisor pattern 协调 3 个 sub-agent:`architect_mapper`(架构概览)、`entry_explainer`(入口/调用链/关键函数)、`verifier`(cross-cutting 声明验证层)。
- **State / schema**:`WayfinderState` TypedDict 覆盖 query、repo_url、intent、repo_metadata、module_dep_graph、entry_points、ast_index、pending / verified / unverified / contradicted claims、test_results、partial_summaries、next_agent、user_corrections、final_output、messages;`Claim` schema 包含 text、source_agent、risk_level、test_strategy、test_id。
- **Routing**:deterministic rule + LLM fallback;intent 覆盖 architectural / runtime / behavioral / debug / mixed。
- **MCP integration**:通过 `langchain-mcp-adapters` 集成 5 个 MCP server:Project 5 自写 `mcp-repo-mapper`、`mcp-ast-explorer`、`mcp-test-runner`,以及 community `arxiv-mcp` 和 `tavily-mcp` 或 GitHub search MCP。
- **Verification**:仅高风险声明触发 verifier;具体函数名、数字、行为断言进入 pending claims;输出 `verified` / `unverified` / `contradicted`;`contradicted_claims` 触发 reflection self-check loop,最多 2 次。
- **HITL**:意图分类后确认;跑测试前展示测试列表 + 估计耗时,支持 approve / skip / modify_filter;final 综述前展示 verification 状态摘要。
- **Resilience**:覆盖 8 个 failure modes:repo 过大、语言不支持、AST parse error、测试套件不存在或全失败、Supervisor 误分类、LLM 幻觉 symbol、reflection 无限、测试超时 / sandbox kill。
- **Reliability / persistence**:MCP tool calls 使用 tenacity retry + exponential backoff;SQLite checkpointer 支持 resumable runs;fault injection tests 覆盖 timeout / parse error / routing hallucination。
- **API / runtime**:FastAPI gateway 提供 `/explain`、`/status/{job_id}`、`/refine/{job_id}`;async background tasks;Git clone 浅 clone + LRU cache。
- **Observability**:LangSmith tracing 覆盖 nodes + tool calls,metadata 包含 agent_name、tool_name、mcp_server、tokens、latency、cost_usd、claim_id。
- **Dashboard / deploy**:Next.js + shadcn/ui dashboard 替代 Streamlit;Docker Compose multi-service(api + 3 mcp servers + dashboard + sqlite volume);Railway 或 Cloud Run deploy;live URL 写进 README。
- **Ship artifacts**:README terminal pass、DESIGN.md v1.0、3-min recursive demo on a pinned LangChain commit、bilingual blog post。
- **Post-mainline case study(planned)**:核心 Wayfinder 主线完成后,追加 lightweight **Permission-Gated Recruiting CRM Agent** enterprise workflow case study,证明同一 agent workflow 能迁移到 permission policy、approval queue、audit log、unsafe-action blocking、workflow-level eval 的企业流程场景。它是 P6 的 examples / docs extension,不是新 Project,也不替代 codebase onboarding 主线。

**项目领域**

**OSS codebase onboarding for AI/devtools engineers**。目标用户是进入陌生 GitHub repo 的工程师:先理解架构、入口、关键调用链,再用真实测试验证高风险代码理解声明。Primary demo 默认使用 `langchain-ai/langchain` 的 pinned commit,录制 recursive demo 时展示"用 wayfinder 解释 wayfinder 依赖的 LangChain"。

**简历差异化**

- 不是 generic multi-agent chat demo,而是 repo onboarding workflow:repo ingestion -> MCP grounding -> Supervisor routing -> explanation -> verification -> rewrite。
- 复用 Project 5 三个 self-authored MCP server,证明 agent 的 facts 来自 deterministic tools,不是 prompt guessing。
- `verifier` 只验证高风险声明,用 pytest / jest execution 输出 `verified` / `unverified` / `contradicted`,直接对位 anti-hallucination。
- HITL 不只是聊天确认,而是在 intent routing、pre-test approval、final verification summary 三个工程风险点插入控制。
- Dashboard + LangSmith traces + deploy + recursive demo 让项目从 local graph 变成可检查的 product artifact。
- 后置 enterprise workflow case study 只加一条简历 bullet:permission-gated tool execution、approval queue、audit log、unsafe-action blocking、synthetic CRM evals;不新增独立项目 title。

**跨项目衔接**

- ⬅ **Project 5 `mcp-codebase-tools`**:直接复用 3 个已发布 MCP server。`architect_mapper` 读 `mcp-repo-mapper`;`entry_explainer` 读 `mcp-ast-explorer`;`verifier` 读 `mcp-test-runner`。
- ⬅ **Project 4 `single-file-explainer`**:与 Project 6 形成 file-level single-agent vs repo-level multi-agent 对照;Project 6 不抢 P4 的 file explanation narrative,而是负责 repo onboarding workflow。
- ➡ **Project 7 `agent-eval-harness`**:Project 6 的 verification labels 和 traces 将成为 P7 的 eval 数据来源;P7 用 40 OSS repo tasks 量化 Wayfinder Supervisor vs ReAct。

**成功判定**

- [ ] `final_checklist.md` Project 6 acceptance criteria 全部 `[x]`
- [ ] `WayfinderState` / `Claim` schema、Supervisor routing、3 sub-agent、verifier loop 全部可测
- [ ] 5 MCP integrations working,其中 3 个 Project 5 self-authored MCP 作为主力工具
- [ ] 8 个 failure modes 都有 pytest / fault injection coverage
- [ ] FastAPI gateway + Next.js dashboard + Docker Compose + deployed URL 可用
- [ ] LangSmith traces 可打开,README 有 trace / demo evidence
- [ ] 3-min recursive demo video 完成
- [ ] `DESIGN.md` / README / bilingual blog post 完成
- [ ] Post-mainline enterprise workflow case study 完成:Haichuan-owned design note + skeleton,permission policy / approval queue / audit log / failure handling / eval report,README + resume 一条 bullet
- [ ] `TASKS.md` Project 6 ship 行 `[x]`

---

## 🔒 Core Principles(Commit 0.a 由 Haichuan 手填后锁定)

1. **Verification beats confident narration.**
   Wayfinder 的核心不是"讲得像懂了",而是把具体、高风险的代码理解声明拉回 AST evidence 和 test execution。无法验证时必须显式标 `unverified`,不能包装成确定结论。
2. **Tools produce facts; agents compose explanations.**
   Project 5 MCP server 负责 repo structure、symbol truth、test results;Project 6 的 agent 只负责编排、路由、解释、取舍和改写,不在 prompt 里伪造工具事实。
3. **HITL protects expensive or risky actions.**
   用户只在关键边界介入:intent correction、test execution approval、final verification review。不要把 HITL 做成频繁打断的聊天确认。
4. **Ship a product surface, not only a graph.**
   每个主要能力都要能通过 API、dashboard、trace、README demo evidence 被检查。LangGraph 本身不是成果,可复现的 onboarding run 才是成果。

---

## 🚪 New Chat Pickup Protocol

按以下顺序读 `progress.md`:

1. **Dashboard** — 当前阶段 / blocker / next action。这里是"现在状态"的事实源。
2. **Roadmap** — 找下一个 `[ ]` 或 `[/]`。
3. **Daily Logs 最近 3-5 条** — 看上次做了什么、卡在哪里、下一步是什么。
4. **Project Description** — 只在需要重新确认 P5/P6/P7 narrative 或 acceptance contract 时读。

继续工作前先把 Dashboard 的 `Last Activity`、`Today's North Star`、`Next Action` 更新到今天。

---

## 🔄 Update Protocol(每次有进度变化必走)

1. **Logs 追加一条**(先做,倒序最新在最上):做了什么 / 验证方式 / 决策 / 下一步。
2. **Dashboard 同步**:Current Commit、Overall Progress、Blocker、Last Activity、Working Mode、Today's North Star、Next Action。
3. **Roadmap 勾选**:完成项 `[ ]` -> `[x]` + 日期;进行中项使用 `[/]`。
4. **全局指针**:大事件才同步 `TASKS.md` / `AGENTS.md` / `CLAUDE.md`。

## ✍️ Four-Step Ownership Protocol(Commit 1 起强制)

Canonical method:`planning/codebase_onboarding_theme/project6_four_step_method.md`。

每个 production-code 模块 / 小步都按这个顺序:

1. Cowork 先用 1 句话/项回放本 commit 已完成的小步,再把它们串成"现在为什么做这一步"。
2. **Haichuan 先写短设计文档**:module problem,input,output,rules,failure cases,tests,interview explanation。
3. **Haichuan 自己写最小 skeleton**:函数签名、state 字段、数据流、TODO 位置先由 Haichuan 打出来。
4. **Codex 只补局部实现 / debug / review / tests**:不改全局架构,不决定 schema/routing/agent 分工,不一次性生成多文件 production code。
5. **Haichuan 反向解释代码**:能说清输入、输出、异常、测试和 tradeoff 后,再进入下一小步。
6. Cowork review + 跑验证 + 更新 `progress.md` / 必要时更新 `LEARNINGS.md`。

Ownership 边界:

| 内容 | 主导者 |
|---|---|
| 系统架构、模块边界、State schema、agent routing、Claim / verification 逻辑、test case 设计、README / 面试解释 | Haichuan |
| FastAPI boilerplate、Pydantic 初稿、LangGraph node 局部 TODO、Docker / CI、debug 建议、review gates | Codex 可辅助,但 Haichuan 审 |

当前小步暂停:`MCP retry / timeout / structured error normalization`。恢复前 Haichuan 先写该模块的 design note + minimal skeleton,Codex 再 review / 补局部 TODO。

Guided design mode:

1. 如果 Haichuan 不知道怎么写 design note,Cowork 一次只问一个问题。
2. Haichuan 用大白话回答;不用管 Markdown 格式。
3. Cowork 把回答整理进 `docs/design_notes/*.md`,并在整组问题结束后指出缺口和改进建议。
4. design note 未完整前,Cowork 不改 production code。

## 🧭 Code Walkthrough Protocol(用户要求讲代码时强制)

当 Haichuan 要求讲代码时,按以下形式推进:

1. 先把本次要讲的代码切成小块,列出顺序。
2. 每次只讲一块:先讲基础语法,再讲这块代码在系统里的作用。
3. 用大白话解释,必要时给 1 个小例子。
4. 每讲完一块必须问"看懂了吗?"。
5. Haichuan 确认看懂后,再讲下一块;不要一次性讲完整个文件。

---

## 📊 Dashboard

| Field | Value |
|---|---|
| **Current Commit** | ⏭ **Commit 2** — Supervisor graph + state machine kickoff pending |
| **Overall Progress** | Pre-build **3 / 3 done** · build commits **2 / 11 done** · ship **0 / 8 done** |
| **Blocker** | none |
| **Last Activity** | 2026-05-29 · Commit 1 closed with LEARNINGS updated and all quality gates green. |
| **Working Mode** | **Four-step ownership mode**. Haichuan owns design/skeleton/tests/explanation; Codex only assists local implementation, debug, review, verification, and tracker maintenance. |
| **Today's North Star** | Start Commit 2 only after the kickoff gate:materials first, then Haichuan-owned design/skeleton. |
| **Next Action** | Commit 2 kickoff gate:ask "材料看完了吗?" before any Supervisor/state implementation. |

---

## 🗺️ Roadmap(对照 `final_checklist.md` Project 6 acceptance · Commit 0 后可微调)

### Pre-build(从 `fast_path.md` Project 6 节抽取)

- [x] LangChain Academy modules 4-6(HITL / Memory / Subgraphs / Streaming) — https://academy.langchain.com/courses/intro-to-langgraph ✅ 2026-05-26
- [x] LangGraph Supervisor tutorial — https://langchain-ai.github.io/langgraph/tutorials/multi_agent/agent_supervisor/ ✅ 2026-05-26
- [x] 确认并同步 B2 TypeScript / Next.js 状态;Project 6 dashboard 默认用 Next.js + shadcn/ui ✅ 2026-05-26

### Build

- [x] **Commit 0 — Product contract + repo scaffold** ✅ 2026-05-26
  - [x] 锁定 Project 6 domain / target user / primary demo repo;默认候选:`langchain-ai/langchain` pinned commit ✅ 2026-05-26
  - [x] 填完 `项目领域` / `简历差异化` / `Core Principles` / `Today's North Star` ✅ 2026-05-26
  - [x] 写 README one-page pitch:problem, product promise, verification differentiator, P5/P6/P7 story ✅ 2026-05-26
  - [x] 写 `DESIGN.md` v0:3-agent architecture, state schema sketch, routing sketch, verifier strategy, 8 failure modes outline ✅ 2026-05-26
  - [x] 初始化 main repo scaffold:Python package, FastAPI shell, LangGraph package, Next.js + shadcn dashboard shell ✅ 2026-05-26
  - [x] 配好 local quality gates:ruff, mypy strict, pytest, frontend lint/typecheck placeholder, GitHub Actions main CI ✅ 2026-05-26

- [x] **Commit 1 — Repo ingestion + 5-MCP adapter foundation** ✅ 2026-05-29
  - [x] GitHub URL / local path ingestion layer:shallow clone, pinned ref support, local LRU cache, cleanup policy ✅ 2026-05-27
    - [x] Local path `RepoSource` / `RepoHandle` models and resolver ✅ 2026-05-27
    - [x] `count_files()` ignores generated/cache/dependency dirs (`.git`, `.venv`, `node_modules`, `.next`, etc.) ✅ 2026-05-27
    - [x] GitHub URL parsing / clone cache contract ✅ 2026-05-27
    - [x] Pinned ref support ✅ 2026-05-27
    - [x] Cache cleanup policy ✅ 2026-05-27
    - [x] Shallow clone + checkout execution ✅ 2026-05-27
  - [x] Repo size guard:>10k files 触发 sampling proposal + HITL confirmation ✅ 2026-05-27
  - [x] `langchain-mcp-adapters` integration harness with typed tool-call wrappers ✅ 2026-05-28
  - [x] Project 5 MCP config factory + adapter contract tests for `mcp-repo-mapper`, `mcp-ast-explorer`, `mcp-test-runner` ✅ 2026-05-28
  - [x] 接入 3 个 Project 5 self-authored MCP:`mcp-repo-mapper`, `mcp-ast-explorer`, `mcp-test-runner` ✅ 2026-05-29
    - [x] Design note for fake-vs-real integration boundary ✅ 2026-05-29
    - [x] Skip-safe integration test skeleton with one representative tool per server ✅ 2026-05-29
    - [x] Real integration run with Project 5 MCP commands available in PATH ✅ 2026-05-29
  - [x] 接入 2 个 community MCP:`tavily-mcp` + GitHub search MCP (`arxiv-mcp` parked) ✅ 2026-05-29
    - [x] Design note for Project 5-primary / community-supporting boundary ✅ 2026-05-29
    - [x] Community MCP package and command choices resolved from official sources ✅ 2026-05-29
    - [x] Config factory + contract tests for Tavily and GitHub search MCP ✅ 2026-05-29
    - [x] Env-gated real integration tests for Tavily and GitHub search MCP ✅ 2026-05-29
      - [x] Skip-safe integration test skeleton ✅ 2026-05-29
      - [x] Real run with `TAVILY_API_KEY` / `GITHUB_PERSONAL_ACCESS_TOKEN` available ✅ 2026-05-29
  - [x] 所有 MCP tool calls 加 tenacity exponential backoff, timeout, structured error normalization ✅ 2026-05-29
  - [x] Contract tests prove each MCP can list tools and return one happy-path response through adapter layer ✅ 2026-05-29

- [ ] **Commit 2 — Supervisor graph + state machine**
  - [ ] 实现 `WayfinderState` TypedDict:query, repo_url, intent, repo_metadata, module_dep_graph, entry_points, ast_index, claims, test_results, summaries, next_agent, user_corrections, final_output, messages
  - [ ] 实现 `Claim` schema:text, source_agent, risk_level(low/medium/high), test_strategy, test_id
  - [ ] LangGraph Supervisor coordinates `architect_mapper`, `entry_explainer`, `verifier` placeholder nodes
  - [ ] Intent routing:deterministic rule first, LLM fallback second;覆盖 architectural / runtime / behavioral / debug / mixed
  - [ ] SQLite checkpointer supports resumable runs and status recovery after process restart
  - [ ] Routing tests cover rule hits, LLM fallback JSON validation, invalid intent recovery, mixed-intent routing

- [ ] **Commit 3 — Architecture path end-to-end (`architect_mapper`)**
  - [ ] `architect_mapper` uses `mcp-repo-mapper` to produce module layers, dependency graph, language breakdown, frameworks, entry points
  - [ ] Architecture output includes source evidence, confidence labels, and "what I cannot prove" limitations
  - [ ] `repo_metadata`, `module_dep_graph`, and `entry_points` are persisted into `WayfinderState`
  - [ ] Architectural query works through `/explain` with mocked verifier disabled or no-op
  - [ ] Tests cover supported repo, oversized repo sampling branch, unsupported language fallback, AST parse flag propagation

- [ ] **Commit 4 — Entry explanation + AST anti-hallucination (`entry_explainer`)**
  - [ ] `entry_explainer` uses `mcp-ast-explorer` for definitions, references, signatures, call chains, class hierarchy
  - [ ] Produces entry-path explanation:call chain, key functions, data flow, assumptions, source citations
  - [ ] AST validation gate rejects hallucinated functions/classes before final output
  - [ ] `ast_index` and key symbol evidence are persisted into `WayfinderState`
  - [ ] Behavioral query works through `/explain` on a real fixture repo
  - [ ] Tests cover existing symbol, missing symbol, parse error skip + flag, and unsupported language degraded answer

- [ ] **Commit 5 — Verifier + HITL test approval**
  - [ ] Claim extractor turns high-risk output statements into `pending_claims`
  - [ ] Risk policy triggers verifier only for concrete function names, numbers, behavior assertions, or testable runtime claims
  - [ ] `verifier` uses `mcp-test-runner` to select/run minimal pytest or jest targets
  - [ ] Low-risk claims skip verification; no-test-coverage claims become `unverified`, not silently accepted
  - [ ] Pre-test HITL interrupt shows test list + estimated time;Command API supports approve / skip / modify_filter
  - [ ] Final pre-output HITL summary shows X verified / Y unverified / Z contradicted
  - [ ] Tests cover verified, unverified(no tests), contradicted, skipped-by-user, and modified test filter paths

- [ ] **Commit 6 — Reflection loop + resilience layer**
  - [ ] Reflection self-check rewrites final output when `contradicted_claims` exist:generate -> verify -> rewrite, max 2 iterations
  - [ ] Failure mode 1:repo >10k files -> sampling + user confirmation
  - [ ] Failure mode 2:unsupported language -> filename/comment heuristic + verifier skipped
  - [ ] Failure mode 3:AST parse error -> skip file + flag in final output
  - [ ] Failure mode 4:no tests or all tests fail -> claim unverified(no test coverage)
  - [ ] Failure mode 5:Supervisor intent misclassification -> HITL correction
  - [ ] Failure mode 6:LLM hallucinated symbol -> AST validation hard gate
  - [ ] Failure mode 7:reflection loop infinite -> hard cap 2 + abort with explanation
  - [ ] Failure mode 8:test timeout / sandbox kill -> retry once + upgraded timeout;still failing becomes validation timed out
  - [ ] Fault injection tests cover mock timeout, mock parse error, mock supervisor hallucination, reflection cap

- [ ] **Commit 7 — FastAPI runtime + observability**
  - [ ] FastAPI gateway exposes `/explain`, `/status/{job_id}`, `/refine/{job_id}`
  - [ ] Async background jobs persist run status, current node, partial summaries, errors, and final output
  - [ ] `/refine/{job_id}` accepts user corrections and resumes from checkpointer
  - [ ] LangSmith tracing wraps all nodes and tool calls
  - [ ] Trace metadata includes agent_name, tool_name, mcp_server, tokens, latency, cost_usd, claim_id
  - [ ] API tests cover job lifecycle, status polling, refine/resume, error serialization, trace metadata hooks

- [ ] **Commit 8 — Dashboard, deploy, and core Wayfinder ship evidence**
  - [ ] Next.js + shadcn dashboard replaces Streamlit plan and reads API status/results
  - [ ] Dashboard panels:recent runs table(10 entries, click -> trace URL), per-agent latency P50/P95, token usage, cost overview, routing decision Sankey, verification stats, failure mode frequency
  - [ ] Docker Compose multi-service:api + 3 MCP servers + dashboard + sqlite-volume
  - [ ] GitHub Actions CI for main app plus integration checks against the 3 MCP server packages/repos
  - [ ] Railway or Cloud Run deploy works;live URL added to README
  - [ ] README terminal pass:tagline, demo GIF, architecture, tech stack, quickstart, API spec, 3 curl examples, eval evidence, failure modes, lessons learned, hidden interview talking points
  - [ ] `DESIGN.md` v1.0 finalized with 8 failure modes and each mitigation
  - [ ] 3-min recursive demo video on pinned LangChain commit linked from README
  - [ ] Bilingual blog post(~2500 words) published or ready for external posting
  - [ ] `final_checklist.md` Project 6 section updated to `[x]` where acceptance is satisfied

- [ ] **Commit 9 — Enterprise workflow case study design + skeleton contract(post-mainline)**
  - [ ] Read `project6_enterprise_workflow_case_study_plan.md` and extract the minimum case-study scope;do not add a new Project 11
  - [ ] Haichuan writes `docs/design_notes/00X_enterprise_workflow_case_study.md`:problem,input,output,rules,failure cases,tests,interview explanation
  - [ ] Decide exact module boundary in prose only:graph,schemas,tools,examples,docs;do not create production files until skeleton is approved
  - [ ] Define `EnterpriseWorkflowState` fields in the design note:candidate,jobs,contacts,job_matches,outreach_draft,risk_flags,approval_tasks,audit_events,final_status,final_report
  - [ ] Define policy table in the design note:allow,allow_if_low_risk,requires_approval,deny
  - [ ] Define approval / audit schemas in prose:ApprovalTask and AuditEvent required fields
  - [ ] Define eval contract:50 candidates,20 jobs,20 contacts,10 risky cases;metrics include approval_routing_accuracy,unsafe_action_blocking_rate,cost_per_candidate_usd,human_intervention_rate
  - [ ] Haichuan writes minimal skeleton only after design is accepted;Codex may review or fill local TODOs after that

- [ ] **Commit 10 — Enterprise workflow case study MVP + docs(post-mainline)**
  - [ ] Implement from Haichuan-owned skeleton:permission-gated recruiting CRM demo,not a standalone recruiting product
  - [ ] Add mock CRM / mock email draft / mock policy store / approval queue / audit log;no real Gmail,Salesforce,login,or frontend dashboard
  - [ ] Add example runner under `examples/enterprise_workflow/` that loads synthetic JSON,prints final report,and writes sample audit / approval outputs
  - [ ] Add focused tests for policy decisions,approval routing,unsafe email blocking,audit event creation,missing contact handling,high-risk CRM update requiring approval
  - [ ] Add `docs/case_studies/enterprise_workflow_agent.md` and `enterprise_eval_report.md`;do not publish fake benchmark numbers
  - [ ] Add a small README section under Wayfinder explaining that the architecture generalizes beyond codebase onboarding
  - [ ] Add one resume bullet under the existing Wayfinder project;do not create a separate project title

### Ship

- [ ] 全部 acceptance criteria `[x]`
- [ ] README terminal pass:tagline + demo GIF + architecture + tech stack + quickstart + API spec + 3 curl examples + eval evidence + failure modes + lessons learned
- [ ] `DESIGN.md` v1.0:3-agent architecture, state schema, routing, verifier strategy, 8 failure modes
- [ ] Live deploy URL 写进 README
- [ ] 3-min recursive demo video 完成并链接
- [ ] Bilingual blog post 发布
- [ ] `final_checklist.md` Project 6 section 全部同步
- [ ] `TASKS.md` Project 6 ship line `[x]`

---

## 📝 Daily Logs

> 每个 commit / 每个工作日加一条,**倒序**(最新在最上)。

### 2026-05-29 — Commit 1 — `closed`

- **做了什么**:Closed Commit 1 after the LEARNINGS close gate:all roadmap subitems are complete, `LEARNINGS.md` now has the Commit 1 learning section, and the dashboard is ready for Commit 2 kickoff.
- **自己设计了什么**:Commit 1 now has a clean boundary:repo ingestion, repo guardrails, typed MCP adapter, Project 5 MCP configs/integration, community MCP configs/integration, and adapter reliability are foundation work;Supervisor/state design belongs to Commit 2.
- **Codex 帮了哪里**:Codex updated tracker/LEARNINGS only after Haichuan confirmed there were no extra questions to add.
- **验证方式**:Close-out reused the latest green gates:`uv run pytest tests/test_mcp_adapter.py`(10 passed);`uv run ruff check src tests`;`uv run mypy src tests`;`uv run pytest`(40 passed, 5 skipped);`git diff --check`.
- **问题记录**:Commit 2 must start from the kickoff gate and four-step ownership flow;do not jump from closed adapter foundation directly into production graph code.
- **明天计划**:Ask "材料看完了吗?", then capture Commit 2 sources/design before implementation.

### 2026-05-29 — Commit 1 — `mcp reliability cleanup passed`

- **做了什么**:Completed the MCP adapter reliability cleanup:tool calls now use tenacity retry/backoff for retryable `TimeoutError` / `ConnectionError`, enforce a per-attempt timeout with `asyncio.wait_for()`, validate retry/timeout config, and still raise structured `MCPToolCallError` / `MCPToolError` on failure.
- **自己设计了什么**:The behavior follows the existing reliability design note:unknown tools do not retry;timeout and connection failures retry;generic runtime failures do not retry;all failures normalize into the small v1 error model.
- **Codex 帮了哪里**:Codex filled the local adapter implementation and added a focused fake-tool test proving Wayfinder enforces timeout itself instead of relying only on MCP tools to raise `TimeoutError`.
- **决策**:Keep default timeout at 30 seconds per attempt;unit tests set retry wait to zero for speed while production defaults use exponential backoff.
- **验证方式**:`uv run pytest tests/test_mcp_adapter.py`(10 passed);`uv run ruff check src tests`;`uv run mypy src tests`;`uv run pytest`(40 passed, 5 skipped);`git diff --check`.
- **问题记录**:Commit 1 close-out 可沉淀 per-attempt timeout vs tool-raised timeout:adapter-owned timeout protects Wayfinder even when an MCP tool hangs silently.
- **明天计划**:Run the Commit 1 close-out gate:collect any remaining LEARNINGS questions, then close Commit 1 or do one reverse-explanation pass first.

### 2026-05-29 — Commit 1 — `community mcp integration passed`

- **做了什么**:Loaded local `.env`, forwarded `TAVILY_API_KEY` / `GITHUB_PERSONAL_ACCESS_TOKEN` into MCP subprocess configs, fixed Tavily npm cache isolation, corrected Tavily's actual tool name from `tavily-search` to `tavily_search`, and confirmed real Tavily + GitHub MCP integration passes through `MCPAdapter`.
- **自己设计了什么**:Community MCPs remain env-gated and skip-safe in normal tests, but can be run as real external-service integration tests when keys are loaded.
- **Codex 帮了哪里**:Codex debugged the real integration failures:subprocess env was not being forwarded, `npx` used a broken user npm cache, Docker did not receive the GitHub token, and Tavily's real `list_tools()` output differed from the earlier source read.
- **决策**:Forward only available required env vars into config;keep npm cache under `/private/tmp/wayfinder-npm-cache`;trust real `list_tools()` output over guessed or stale tool-name documentation.
- **验证方式**:`WAYFINDER_RUN_COMMUNITY_MCP_INTEGRATION=1 uv run pytest tests/test_community_mcp_integration.py`(2 passed);`uv run ruff check src tests`;`uv run mypy src tests`;`uv run pytest`(39 passed, 5 skipped);`git diff --check`.
- **问题记录**:Commit 1 close-out 可沉淀 external MCP realism:real integration exposed env propagation, npm cache, Docker token forwarding, and tool-name drift that unit tests could not catch.
- **明天计划**:Explain the env-forwarding fixes, then continue Commit 1 cleanup/normalization.

### 2026-05-29 — Commit 1 — `community mcp integration skeleton reviewed`

- **做了什么**:Haichuan added `tests/test_community_mcp_integration.py` with env-gated, skip-safe real integration tests for Tavily and GitHub search MCP.
- **自己设计了什么**:The real integration boundary requires explicit opt-in via `WAYFINDER_RUN_COMMUNITY_MCP_INTEGRATION=1`, local command availability, required API keys, and Docker availability for GitHub MCP.
- **Codex 帮了哪里**:Codex reviewed the skeleton and ran targeted plus full quality gates.
- **决策**:Keep community MCP real-service checks incomplete until `TAVILY_API_KEY` and `GITHUB_PERSONAL_ACCESS_TOKEN` are available;normal tests should skip them rather than fail.
- **验证方式**:`uv run pytest tests/test_community_mcp_integration.py`(2 skipped);`uv run ruff check src tests`;`uv run mypy src tests`;`uv run pytest`(38 passed, 5 skipped);`git diff --check`.
- **问题记录**:Commit 1 close-out 可沉淀 env-gated integration tests:external-service tests prove real boundaries, but should not make ordinary local development depend on secrets or Docker.
- **明天计划**:Decide whether to run community MCP real integration with keys now, or defer and continue Commit 1 cleanup/normalization.

### 2026-05-29 — Commit 1 — `community mcp config skeleton reviewed`

- **做了什么**:Haichuan added `src/wayfinder/mcp/community.py` and `tests/test_community_mcp_configs.py` to declare Tavily and GitHub search MCP configs, primary tools, and real-integration env requirements.
- **自己设计了什么**:The community MCP config layer mirrors the Project 5 config pattern but keeps external tools in a separate module because they are supporting context, not primary repo-fact tools.
- **Codex 帮了哪里**:Codex reviewed the skeleton, corrected Tavily's official tool name from `tavily_search` to `tavily-search`, and ran quality gates.
- **决策**:Keep `arxiv-mcp` parked;use `npx -y tavily-mcp@latest` for Tavily and Dockerized `ghcr.io/github/github-mcp-server` in read-only mode for GitHub search.
- **验证方式**:`uv run pytest tests/test_community_mcp_configs.py`(3 passed);`uv run ruff check src tests`;`uv run mypy src tests`;`uv run pytest`(38 passed, 3 skipped).
- **问题记录**:Commit 1 close-out 可沉淀 external tool naming drift:official MCP tool names must be verified from source, not guessed from Python identifier style.
- **明天计划**:Explain the community config skeleton, then choose whether to add env-gated real community integration tests now or defer until API keys are available.

### 2026-05-29 — Commit 1 — `community mcp commands resolved`

- **做了什么**:Resolved the exact community MCP implementation choices from official sources:Tavily uses official `tavily-mcp` via `npx -y tavily-mcp@latest`;GitHub search uses GitHub's official `github-mcp-server`, preferably through Docker for local MCP execution.
- **自己设计了什么**:Keep product integration MCP-based for both community tools;do not replace GitHub MCP with Codex/GitHub connector tooling inside Wayfinder.
- **Codex 帮了哪里**:Codex checked official sources and updated the design note before code skeleton work.
- **决策**:`TAVILY_API_KEY` and `GITHUB_PERSONAL_ACCESS_TOKEN` are real integration requirements only;normal unit tests must not require them.
- **问题记录**:Commit 1 close-out 可沉淀 local-vs-remote MCP choice:Tavily supports remote HTTP, but the initial Wayfinder config can use local stdio through `npx` because the existing adapter/config path already supports stdio commands.
- **明天计划**:Write the minimal community MCP config skeleton and config contract tests.

### 2026-05-29 — Commit 1 — `community mcp integration design locked`

- **做了什么**:Completed `docs/design_notes/003_community_mcp_integration.md` for the two community MCP boundary.
- **自己设计了什么**:Haichuan selected Tavily MCP + GitHub search MCP for Commit 1 and parked `arxiv-mcp` for later;community MCPs provide supporting external context only, while Project 5 MCPs remain the primary repository fact layer.
- **Codex 帮了哪里**:Codex kept the scope to two community MCPs, formatted the design note, and flagged unresolved package/command/API-key questions before implementation.
- **决策**:Community MCP success still returns `MCPToolCallResult`;failure still raises `MCPToolCallError`;external snippets must be labeled as external context and cannot override Project 5 repo facts.
- **问题记录**:Commit 1 close-out 可沉淀 community MCP boundary:external docs/issues/PRs help onboarding, but they are context, not proof.
- **明天计划**:Resolve exact Tavily/GitHub MCP package and command names, then write the minimal config/test skeleton.

### 2026-05-29 — Commit 1 — `project5 mcp integration passed`

- **做了什么**:Installed the three local Project 5 MCP packages into the Project 6 venv, fixed the real integration test's `parse_test_output` payload, and confirmed all three Project 5 MCP servers pass the env-gated integration test through `MCPAdapter`.
- **自己设计了什么**:The happy-path checks remain one representative tool per server:`scan_repo`, `find_definition`, and `parse_test_output`.
- **Codex 帮了哪里**:Codex debugged two real-boundary failures:editable install `.pth` files were marked hidden on macOS so Python skipped source paths, and `parse_test_output` expects pytest-json-report JSON rather than human pytest text.
- **决策**:Keep real Project 5 MCP integration tests env-gated so normal `pytest` remains fast and skip-safe;use `/private/tmp/wayfinder-uv-cache` in sandboxed Codex runs to avoid the blocked `~/.cache/uv` path.
- **验证方式**:`uv run python -c 'import mcp_repo_mapper, mcp_ast_explorer, mcp_test_runner; print("imports ok")'`;`WAYFINDER_RUN_PROJECT5_MCP_INTEGRATION=1 uv run pytest tests/test_project5_mcp_integration.py`(3 passed);`uv run ruff check src tests`;`uv run mypy src tests`;`uv run pytest`(35 passed, 3 skipped);`git diff --check`.
- **问题记录**:Commit 1 close-out 可沉淀 integration test 的价值:fake tests caught adapter policy, but only real integration tests caught packaging/source-path and tool payload-contract issues.
- **明天计划**:Start the 2 community MCP integration boundary with the same four-step ownership flow.

### 2026-05-29 — Commit 1 — `project5 mcp integration skeleton reviewed`

- **做了什么**:Haichuan added `tests/test_project5_mcp_integration.py` with isolated real-MCP integration tests for one representative Project 5 tool per server and registered the `integration` pytest marker.
- **自己设计了什么**:The test boundary follows the design note:ordinary tests stay fake/config-only, while real MCP checks require `WAYFINDER_RUN_PROJECT5_MCP_INTEGRATION=1` and skip if local Project 5 commands are missing.
- **Codex 帮了哪里**:Codex reviewed the skeleton, confirmed the skip behavior, checked that the Project 5 commands are not currently in PATH, and ran quality gates.
- **决策**:Do not mark real Project 5 MCP integration complete yet;the skeleton is correct, but the actual server calls have not run because `mcp-repo-mapper`, `mcp-ast-explorer`, and `mcp-test-runner` are not installed/exposed as shell commands.
- **验证方式**:`uv run pytest tests/test_project5_mcp_integration.py`(3 skipped);`WAYFINDER_RUN_PROJECT5_MCP_INTEGRATION=1 uv run pytest tests/test_project5_mcp_integration.py`(3 skipped due missing commands);`uv run ruff check src tests`;`uv run mypy src tests`;`uv run pytest`(35 passed, 3 skipped).
- **问题记录**:Commit 1 close-out 可沉淀 `config`:config is a connection/runtime instruction sheet, not the server, not the tool, and not the execution logic.
- **明天计划**:Install or expose the three Project 5 MCP commands, then rerun the env-gated real integration test.

### 2026-05-29 — Commit 1 — `project5 mcp integration design locked`

- **做了什么**:Completed `docs/design_notes/002_project5_mcp_integration.md` for the real Project 5 MCP integration boundary.
- **自己设计了什么**:Haichuan defined the split between fake adapter tests and real integration tests:unit tests prove static config and adapter logic without starting MCP processes;real integration tests start each Project 5 server, call `list_tools()`, check expected tools, and call one happy-path tool per server.
- **Codex 帮了哪里**:Codex guided the design note one question at a time and formatted the rough answers into the project design document.
- **决策**:If Project 5 MCP commands are missing locally, real integration tests should skip instead of failing normal `pytest`;the first integration pass uses one representative tool per server, not every primary tool.
- **问题记录**:Commit 1 close-out 可沉淀 fake adapter tests vs real integration tests:fake tests prove Wayfinder retry/error logic in isolation;real tests prove Wayfinder can start Project 5 servers, discover tools, and call them against a repo.
- **明天计划**:Start the Haichuan-owned minimal skeleton for isolated, skip-safe Project 5 MCP integration tests.

### 2026-05-29 — Roadmap adjustment — `enterprise case study parked`

- **做了什么**:Read `project6_enterprise_workflow_case_study_plan.md` and updated this tracker so the enterprise workflow case study becomes post-mainline Commit 9/10, not an immediate production-code change.
- **自己设计了什么**:Haichuan clarified the correct boundary:the case study should update plan / progress / commit structure first;production code must still follow the four-step ownership workflow.
- **Codex 帮了哪里**:Codex corrected an earlier overreach by removing generated implementation/docs/examples/tests from this working tree, then changed only `progress.md`.
- **决策**:Keep Commit 1-8 intact for core Wayfinder. Add Commit 9 for Haichuan-owned enterprise workflow design + skeleton contract, then Commit 10 for the later lightweight MVP/docs/eval after skeleton approval.
- **验证方式**:Tracker-only update;no tests required. Confirmed the mistaken generated source/example/docs files are no longer present.
- **明天计划**:Resume Commit 1 unless Haichuan explicitly switches to planning Commit 9 design-note questions.

### 2026-05-28 — Commit 1 — `mcp error helper reviewed`

- **做了什么**:Haichuan extracted `_tool_call_error()` to remove repeated `MCPToolCallError(MCPToolError(...))` construction while preserving behavior.
- **自己设计了什么**:The helper only constructs structured errors;it does not decide retry policy or call tools, so `call_tool()` still owns the policy branches.
- **Codex 帮了哪里**:Codex fixed formatting-only whitespace and ran all quality gates.
- **决策**:Keep the helper as a narrow static method instead of a larger abstraction;the retry/error decisions remain explicit and readable in `call_tool()`.
- **验证方式**:`uv run pytest tests/test_mcp_adapter.py`(9 passed);`uv run ruff check src tests`;`uv run mypy src tests`;`uv run pytest`(35 passed);`git diff --check`.
- **还没完全懂什么**:Need one reverse-explanation pass to confirm Haichuan can explain `call_tool()` vs `_invoke_tool()` vs `_tool_call_error()` without Codex.
- **明天计划**:Either walk through the final adapter code or start real Project 5 MCP integration.

### 2026-05-28 — Commit 1 — `mcp connection retry reviewed`

- **做了什么**:Haichuan added connection-error coverage and implementation:connection failures now retry up to 3 attempts and normalize to retryable `tool_error`.
- **自己设计了什么**:This follows the design note decision to keep v1 error types small:connection failures are not a separate `connection_error` type yet, but are marked retryable.
- **Codex 帮了哪里**:Codex reviewed the implementation and ran all quality gates.
- **决策**:Keep `ConnectionError` folded into `tool_error` for v1;defer a separate error type until real MCP integration proves the distinction is useful.
- **验证方式**:`uv run pytest tests/test_mcp_adapter.py`(9 passed);`uv run ruff check src tests`;`uv run mypy src tests`;`uv run pytest`(35 passed);`git diff --check`.
- **还没完全懂什么**:Whether to extract duplicated error construction into a helper now, or leave explicit branches for readability while learning.
- **明天计划**:Review MCP reliability slice completeness and choose between helper cleanup or real Project 5 MCP server integration.

### 2026-05-28 — Commit 1 — `mcp timeout retry reviewed`

- **做了什么**:Haichuan implemented the first MCP retry / normalization path:timeout retries up to 3 attempts, timeout raises retryable structured error, generic `RuntimeError` raises non-retryable `tool_error`.
- **自己设计了什么**:The behavior follows Haichuan's design note:transient timeout gets retries;deterministic runtime failure does not retry.
- **Codex 帮了哪里**:Codex reviewed the implementation, fixed formatting-only issues, explained why tests were red, and ran all quality gates.
- **决策**:Use a simple explicit retry loop for now instead of `tenacity`, because it keeps the policy visible while Haichuan is learning the control flow. Tenacity can replace the loop later once the behavior is fully understood.
- **验证方式**:`uv run pytest tests/test_mcp_adapter.py`(8 passed);`uv run ruff check src tests`;`uv run mypy src tests`;`uv run pytest`(34 passed);`git diff --check`.
- **还没完全懂什么**:Whether to split `connection_error` into its own error type now or keep it folded into retryable `tool_error` until real MCP integration.
- **明天计划**:Add or defer connection-error coverage, then decide if this MCP reliability slice is complete for Commit 1.

### 2026-05-28 — Commit 1 — `mcp not-found error path reviewed`

- **做了什么**:Haichuan updated `MCPAdapter.call_tool()` so unknown tool names now raise `MCPToolCallError` carrying a structured `MCPToolError`.
- **自己设计了什么**:The `not_found` path now follows the design note:invalid tool names are non-retryable and should not leak a raw `KeyError` / `ValueError`.
- **Codex 帮了哪里**:Codex reviewed scope and ran verification;no retry or timeout implementation was added.
- **决策**:Keep this step intentionally narrow:only replace the old `ValueError` path;defer timeout / connection / runtime error handling to the next test-first slice.
- **验证方式**:`uv run pytest tests/test_mcp_adapter.py`;`uv run ruff check src tests`;`uv run mypy src tests`;`uv run pytest`(32 passed);`git diff --check`.
- **还没完全懂什么**:Next point is how to test retry count without introducing real MCP servers.
- **明天计划**:Write failing tests for timeout retry and non-retryable runtime error, then implement the smallest adapter change to satisfy them.

### 2026-05-28 — Commit 1 — `mcp reliability skeleton reviewed`

- **做了什么**:Haichuan added the first MCP reliability skeleton:`MCPToolErrorType`, `MCPToolError`, and `MCPToolCallError`.
- **自己设计了什么**:Haichuan completed the design note for standardizing MCP tool-call failures into structured error categories and retry decisions.
- **Codex 帮了哪里**:Codex formatted the design note, fixed spacing-only code style issues, explained `Exception` / `super().__init__`, and ran verification.
- **决策**:Keep `MCPToolError` as Pydantic data in `models.py`;keep `MCPToolCallError(Exception)` in `adapter.py` as the failure control-flow wrapper.
- **验证方式**:`uv run ruff check src tests`;`uv run mypy src tests`;`uv run pytest tests/test_mcp_adapter.py tests/test_project5_mcp_configs.py`;`uv run pytest`(32 passed);`git diff --check`.
- **还没完全懂什么**:Next implementation question is how tests should express retry behavior before adding tenacity / timeout code.
- **明天计划**:Write adapter tests for structured `not_found`, retryable timeout, and non-retryable runtime errors.

### 2026-05-28 — Commit 1 — `four-step ownership workflow locked`

- **做了什么**:Paused the MCP retry coding step and promoted the Project 6 four-step method into root workflow docs plus this tracker.
- **自己设计了什么**:Haichuan redefined the ownership boundary:architecture, module boundaries, schema, routing, verification policy, tests, and interview explanation must be Haichuan-owned.
- **Codex 帮了哪里**:Codex updated workflow/tracker docs only;no production retry code was added in this step.
- **决策**:Future P6 modules must start with Haichuan's design note and skeleton before Codex can fill local TODOs.
- **验证方式**:Workflow docs updated;no code test needed because this is process documentation.
- **还没完全懂什么**:Next learning target is the MCP retry/error-normalization design itself, but implementation waits for Haichuan-owned design/skeleton.
- **明天计划**:Resume with a design note for MCP retry / timeout / structured error normalization.

### 2026-05-28 — Commit 1 — `project5 mcp configs reviewed`

- **做了什么**:Added `wayfinder.mcp.project5` as the centralized config factory for Project 5 MCP servers and added contract tests proving the declared tool names flow through the adapter boundary.
- **验证方式**:`uv run ruff check src tests`;`uv run mypy src tests`;`uv run pytest`(32 passed);`git diff --check`.
- **决策**:Keep this as a unit-level config contract for now;do not require the three Project 5 CLI packages to be installed before ordinary P6 tests can pass.
- **问题记录**:Commit 1 close-out 可沉淀 `config` 的定义:config is the runtime connection/behavior description, not the tool execution logic itself. Also record `list` invariant vs `Sequence` covariance for fake clients.
- **明天计划**:Add MCP retry / timeout / structured error normalization before real server integration.

### 2026-05-28 — Commit 1 — `mcp adapter harness reviewed`

- **做了什么**:Cowork filled the MCP adapter harness directly at Haichuan's request:typed server config models, `MCPAdapter`, `build_mcp_client()`, and fake-client/fake-tool contract tests. Also recorded the required block-by-block code walkthrough protocol in this tracker.
- **验证方式**:`uv run ruff check src tests`, `uv run mypy src tests`, `uv run pytest tests/test_mcp_adapter.py`, `uv run pytest`, and `git diff --check` all passed;full suite now has 28 tests.
- **决策**:Use `streamable_http` instead of generic `http` to match local `langchain-mcp-adapters`;cast third-party connection dicts at the adapter boundary, not throughout the codebase.
- **问题记录**:Commit 1 close-out 可沉淀 typed wrapper / adapter seam:Wayfinder code depends on its own `MCPToolCall` / `MCPToolCallResult`, while third-party MCP client details stay isolated in `adapter.py`. Also record `Protocol` syntax:`class X(Protocol)` defines the methods/fields an object must have; the object does not need to inherit from `X` at runtime.
- **明天计划**:Walk through MCP adapter code in small chunks, then add Project 5 MCP server configs and contract tests.

### 2026-05-27 — Commit 1 — `github clone execution reviewed`

- **做了什么**:Haichuan wired GitHub resolver execution to `materialize_github_repo()`, supporting shallow clone, cache reuse, requested-ref fetch/checkout, non-git cache rejection, and post-clone file counting.
- **验证方式**:`uv run ruff check src tests`, `uv run mypy src tests`, `uv run pytest tests/test_ingestion_resolver.py`, `uv run pytest`, and `git diff --check` all passed;full suite now has 22 tests.
- **决策**:Unit tests must inject a fake git runner for GitHub resolver execution. Real network clone belongs to manual/integration verification, not normal unit tests.
- **问题记录**:Commit 1 close-out 可沉淀 fake runner / dependency injection:side-effectful git commands are injected so tests prove command intent without hitting GitHub.
- **明天计划**:Start `langchain-mcp-adapters` integration harness with typed tool-call wrappers.

### 2026-05-27 — Commit 1 — `repo size guard reviewed`

- **做了什么**:Haichuan implemented `RepoSizePolicy`, `RepoSamplingProposal`, `RepoSizeAssessment`, and `assess_repo_size()` so oversized repos return a sampling / confirmation proposal instead of silently proceeding.
- **验证方式**:`uv run ruff check src tests`, `uv run mypy src tests`, `uv run pytest tests/test_ingestion_resolver.py`, `uv run pytest`, and `git diff --check` all passed;full suite now has 18 tests.
- **决策**:Keep this as assessment semantics only. Real file sampling and HITL interrupt remain later work.
- **问题记录**:Commit 1 close-out 可沉淀 sampling proposal 的边界:it tells the user why full-repo analysis is risky and asks for confirmation before a degraded path.
- **明天计划**:Implement real GitHub shallow clone + checkout execution using the existing cache / pinned-ref contracts.

### 2026-05-27 — Commit 1 — `cache cleanup policy reviewed`

- **做了什么**:Haichuan implemented cache cleanup policy models and a dry-run cleanup planner that scans cache entries, measures size, and selects oldest entries when repo count or byte limits are exceeded.
- **验证方式**:`uv run ruff check src tests`, `uv run mypy src tests`, `uv run pytest tests/test_ingestion_resolver.py`, `uv run pytest`, and `git diff --check` all passed;full suite now has 15 tests.
- **决策**:Accepted as contract behavior only. Cleanup returns `entries_to_remove`;it does not delete directories yet.
- **问题记录**:Commit 1 close-out 可沉淀 cache cleanup policy 的边界:planning cleanup is safer than deleting immediately because HITL/logging/tests can inspect the removal set first.
- **明天计划**:Add repo size guard for `>10k` files with sampling / HITL proposal semantics.

### 2026-05-27 — Commit 1 — `pinned ref contract reviewed`

- **做了什么**:Haichuan added `clone_url` and `checkout_ref` to `RepoHandle`, preserving GitHub requested refs without performing checkout. Cowork reviewed model, resolver, and tests.
- **验证方式**:`uv run ruff check src tests`, `uv run mypy src tests`, `uv run pytest tests/test_ingestion_resolver.py`, `uv run pytest`, and `git diff --check` all passed;full suite now has 12 tests.
- **决策**:Keep cache identity repo-level and keep `checkout_ref` run-level. Do not put branch/tag/commit into the cache key.
- **问题记录**:Commit 1 close-out 要沉淀 cache vs checkout_ref:cache is where the repo clone is stored;checkout_ref is the branch/tag/commit selected for this run.
- **明天计划**:Define cache cleanup policy as a dry-run contract before adding real clone or delete behavior.

### 2026-05-27 — Commit 1 — `github cache contract reviewed`

- **做了什么**:Haichuan implemented GitHub URL parsing and cache-path contract without performing network clone. Cowork reviewed the parsing, model shape, and tests.
- **验证方式**:`uv run ruff check src tests`, `uv run mypy src tests`, `uv run pytest tests/test_ingestion_resolver.py`, `uv run pytest`, and `git diff --check` all passed;full suite now has 11 tests.
- **决策**:Accept this as a contract slice only:GitHub URL -> normalized owner/repo/clone_url/cache_key/local_path. Real clone, checkout, and cleanup remain separate steps.
- **问题记录**:Commit 1 close-out 要沉淀 `requested_ref` 的作用:it records the branch/tag/commit SHA the user wants Wayfinder to analyze so demos and verification can pin a stable repo version.
- **明天计划**:Move to pinned ref support contract before adding real clone execution.

### 2026-05-27 — Commit 1 — `count_files ignore policy reviewed`

- **做了什么**:Haichuan completed `count_files()` generated/cache/dependency directory pruning;Cowork reviewed implementation and test coverage.
- **验证方式**:`uv run ruff check src tests`, `uv run mypy src tests`, `uv run pytest tests/test_ingestion_resolver.py`, `uv run pytest`, and `git diff --check` all passed.
- **决策**:`os.walk()` with in-place `dirnames[:]` pruning is accepted for this slice. `.gitignore` parsing and repo size threshold remain out of scope for this step.
- **问题记录**:Commit 1 close-out 要沉淀两个命名问题:why `count_files()` uses `_root`;why some variables/functions start with `_`.
- **明天计划**:Move to GitHub URL parsing / clone cache contract before real clone execution.

### 2026-05-27 — Commit 1 — `hand-write protocol locked`

- **做了什么**:Recorded the production-code step protocol requested by Haichuan:explain thinking first, provide target code shape, wait for Haichuan to implement, then Cowork reviews and verifies.
- **验证方式**:Process/tracker update only;no production code changed.
- **决策**:Starting with `count_files()` ignore policy, Cowork will not directly edit production code unless Haichuan explicitly asks.
- **明天计划**:Haichuan implements ignore-dir counting behavior;Cowork reviews after completion.

### 2026-05-27 — Commit 1 — `local resolver reviewed`

- **做了什么**:Haichuan implemented `src/wayfinder/ingestion/models.py`, `src/wayfinder/ingestion/resolver.py`, and `tests/test_ingestion_resolver.py`. Cowork reviewed the code without editing production logic.
- **验证方式**:`uv run ruff check src tests`, `uv run mypy src tests`, `uv run pytest tests/test_ingestion_resolver.py`, and full `uv run pytest` all passed;full suite now has 8 tests.
- **决策**:Local path resolver is accepted as the first ingestion slice. The full Roadmap item remains partial because GitHub URL clone/cache, repo size guard, and MCP adapters are still pending.
- **明天计划**:Add repo size guard / ignore policy behavior next, then move to GitHub URL cache contract.

### 2026-05-26 — Commit 0 close — `scaffold accepted`

- **做了什么**:Closed Commit 0. Updated `LEARNINGS.md` with concepts, gotchas, and interview soundbites from Supervisor pre-build, product contract, scaffold, Pylance/package fix, and frontend build verification.
- **验证方式**:Commit 0 Roadmap is 6/6 done;latest verification set was green for backend import, ruff, mypy, pytest, dashboard lint/typecheck/build, and `git diff --check`.
- **决策**:Commit 1 starts from repo ingestion + MCP adapter foundation, not more scaffold polish. The placeholder graph stays intentionally minimal until real repo inputs exist.
- **明天计划**:Before coding Commit 1, confirm material/source readiness, then design local-path/GitHub-url ingestion and MCP adapter contracts.

### 2026-05-26 — Commit 0 kickoff — `product contract draft`

- **做了什么**:Review pass after VS Code interpreter fix. Found that tests passed via pytest `pythonpath`, but the package itself was not importable through `uv run python -c "import wayfinder"`. Added hatchling wheel package config and ignored dashboard TypeScript build info.
- **验证方式**:`uv sync --extra dev`;`uv run python -c "import fastapi, wayfinder; print(fastapi.__version__); print(wayfinder.__version__)"` returned `0.136.3` and `0.1.0`;reran backend and frontend gates green.
- **决策**:Do not trust pytest import success alone for src-layout scaffolds;package import must be part of Commit 0 verification.
- **明天计划**:Close Commit 0 after LEARNINGS update, then start Commit 1 repo ingestion + 5-MCP adapter foundation.

- **做了什么**:Initialized Commit 0 scaffold:Python package, FastAPI `/health` / `/explain` / `/status/{job_id}` / `/refine/{job_id}` shell, LangGraph bootstrap graph, typed `WayfinderState` / `Claim` contracts, Next.js + shadcn-style dashboard shell, backend CI, frontend config, lockfiles.
- **验证方式**:Backend: `uv sync --extra dev`, `uv run ruff check .`, `uv run mypy src tests`, `uv run pytest`(4 passed). Frontend:user ran `npm ci --cache /private/tmp/wayfinder-npm-cache`, `npm run lint`, `npm run typecheck`, `npm run build`;all passed. Next.js workspace-root warning fixed by setting `outputFileTracingRoot`.
- **决策**:Commit 0 scaffold intentionally returns deterministic placeholder output;real repo ingestion, MCP calls, Supervisor routing, and verifier behavior begin in later commits.
- **明天计划**:Close Commit 0 after final review and LEARNINGS update, then start Commit 1 repo ingestion + 5-MCP adapter foundation.

- **做了什么**:Created `DESIGN.md` v0 with architecture sketch, state schema, routing model, verifier strategy, HITL checkpoints, resilience modes, observability, and build/deploy surface.
- **验证方式**:Matched the v0 design sections to Commit 0 Roadmap and `final_checklist.md` P6 acceptance.
- **决策**:`DESIGN.md` starts as a contract doc, not a polished launch doc;v1.0 will be finalized near ship after implementation proves the details.
- **明天计划**:Initialize Python API / LangGraph / Next.js scaffold and local quality gates.

- **做了什么**:Locked the first product contract draft:domain = OSS codebase onboarding for AI/devtools engineers;target user = engineer entering an unfamiliar repo;primary demo = pinned `langchain-ai/langchain`;filled differentiation and Core Principles;created README one-page pitch.
- **验证方式**:Mapped draft back to Project 6 acceptance:Supervisor product layer, 5 MCP grounding, verifier-backed claims, HITL, dashboard/deploy/demo evidence.
- **决策**:Keep the story verifier-first. Wayfinder should not be framed as "3 agents explain code", but as a codebase onboarding product where agents compose tool-grounded facts and tests catch high-risk claims.
- **明天计划**:Write `DESIGN.md` v0, then initialize Python API / LangGraph / Next.js scaffold.

### 2026-05-26 — Pre-build close — `b2 dashboard scope confirmed`

- **做了什么**:Haichuan reviewed the compressed TypeScript / Next.js / shadcn knowledge needed for the P6 dashboard. Cowork marked the P6-specific B2 gate complete without marking the full Odin / Next.js Learn courses as completed.
- **验证方式**:User confirmation in chat.
- **决策**:For P6, dashboard work can start with typed API responses, App Router basics, client components for polling/interaction, and shadcn table/tabs/badge/card components;deeper frontend learning stays learn-while-building.
- **明天计划**:Start Commit 0:lock domain / demo repo / Core Principles / README one-page pitch.

### 2026-05-26 — Pre-build checkpoint — `supervisor tutorial complete`

- **做了什么**:Haichuan completed the LangGraph Supervisor tutorial. Cowork marked the source complete in `LEARNINGS.md`, `progress.md`, and `TASKS.md`.
- **验证方式**:User confirmation in chat.
- **决策**:Pre-build 只剩 B2 TypeScript / Next.js 状态确认;确认后即可进入 Commit 0.a。
- **明天计划**:确认 B2 状态,然后锁定 Project 6 domain / demo repo / Core Principles / README one-page pitch。

### 2026-05-26 — Roadmap rewrite — `acceptance-backed milestones`

- **做了什么**:对照 `final_checklist.md` Project 6 acceptance 完整重写 Roadmap,把原来的薄 commit 标题改成 9 个厚 milestone,每个 commit 都带可验收 subtask。
- **验证方式**:逐项覆盖 Supervisor / state schema / MCP integration / verifier / HITL / resilience / tracing / API / dashboard / deploy / README / DESIGN / demo / blog。
- **决策**:P6 不按"多写几个小 commit"推进,而按 repo ingestion -> MCP orchestration -> Supervisor -> architecture path -> AST explanation -> verifier -> resilience -> runtime/observability -> ship evidence 的产品链推进。
- **明天计划**:读完 Supervisor tutorial,确认 B2 TypeScript / Next.js 状态,再进入 Commit 0.a。

### 2026-05-26 — Pre-build checkpoint — `langgraph modules complete`

- **做了什么**:Haichuan completed LangChain Academy modules 4-6. Cowork marked the source complete in `LEARNINGS.md` and updated P6 pre-build progress.
- **验证方式**:User confirmation in chat.
- **决策**:继续按 fast_path 单源推进,下一项是 LangGraph Supervisor tutorial,暂不展开备选资料。
- **明天计划**:读完 Supervisor tutorial,确认 B2 TypeScript / Next.js 状态,再进入 Commit 0.a。

### 2026-05-26 — Project kickoff — `wayfinder tracker open`

- **做了什么**:创建 Project 6 `wayfinder` tracker,从 `final_checklist.md` / `fast_path.md` / `theme_design_v1.md` / Project 5 handoff 抽取技术契约、pre-build、roadmap 草案和 P5/P6/P7 衔接。
- **验证方式**:确认 `Final_checklist_phase_projects/project6/` 原先不存在,避免覆盖已有 progress。
- **决策**:Project 6 定位为 P5 工具层之上的 product / agent layer;核心差异化不是"多 agent",而是 verifier-backed codebase explanation。
- **明天计划**:完成 LangChain Academy modules 4-6,把 Sources 写进 `LEARNINGS.md`,再进入 Commit 0.a kickoff。

---

## 🔍 本项目实时任务视图

> 需要 Obsidian + Dataview 插件。这一节自动从本文件的所有 `[ ]` `[/]` `[x]` 行聚合。

### 📋 TODO

```dataview
TASK
FROM ""
WHERE file.path = this.file.path AND !completed AND status = " "
```

### 🔄 进行中

```dataview
TASK
FROM ""
WHERE file.path = this.file.path AND status = "/"
```

### ✅ 已完成

```dataview
TASK
FROM ""
WHERE file.path = this.file.path AND completed
```
