# Wayfinder Launch Draft

## English

Most codebase onboarding tools have the same failure mode:they sound useful
before they are grounded. They can summarize a README, list plausible modules,
or explain a function name that looks familiar, but they usually do not tell
you which statements came from code evidence, which statements are assumptions,
and which statements are contradicted by tests.

Wayfinder is my answer to that problem. It is a multi-agent codebase onboarding
copilot built around evidence, not narration. Given a repository and a question,
it routes the task through a LangGraph Supervisor, calls deterministic MCP
servers for code facts, labels high-risk claims with evidence, and writes final
answers that preserve uncertainty instead of hiding it.

The system is intentionally split into three agents.

`architect_mapper` maps repository structure. It calls `mcp-repo-mapper`, a
self-authored MCP server that scans files, language breakdown, framework
signals, entry points, and Python import dependencies. This agent is responsible
for orientation-level evidence:what the repo contains, where likely entry
points live, and what the architecture graph can prove.

`entry_explainer` explains symbols and call paths. It calls
`mcp-ast-explorer`, another self-authored MCP server. This tool looks up Python
definitions, signatures, references, direct call chains, and class hierarchy
facts. If a symbol does not exist, the result is a structured not-found
response. Wayfinder is not allowed to invent a nearby symbol just because the
query sounds plausible.

`verifier` checks high-risk claims. Source locations, signatures, and direct
references already come from deterministic tools, so those facts can be labeled
from AST evidence. Runtime behavior, numeric claims, state mutations, and
testable error paths need executable evidence. In trusted local mode that can
come from `mcp-test-runner`;in the public Railway deployment, executable test
verification stays disabled until the separate sandbox worker exists.

This produces three labels:verified, unverified, and contradicted. That middle
label is important. If there is no test coverage, an unsupported language, a
timeout, malformed output, or a user-skipped test, Wayfinder marks the claim as
unverified. It does not silently count uncertainty as success. If a selected
test directly conflicts with a claim, the claim becomes contradicted and the
final output is rewritten through a bounded reflection layer.

The runtime is a FastAPI service. `POST /explain` creates a queued job and
starts a background graph run. `GET /status/{job_id}` returns status, current
node, partial summaries, structured errors, verification counts, trace metadata,
and final output. `POST /refine/{job_id}` accepts user corrections, reuses the
same LangGraph `thread_id`, and re-enters the graph through the same
checkpointer thread.

The dashboard is built in Next.js. It reads the API's recent run endpoint and
shows the operational surface:recent runs, trace links, per-agent P50/P95
latency, token usage, cost, routing flow, verification counts, and failure-mode
frequency. The dashboard can also render seeded demo data so the build remains
inspectable even before a live API run exists.

The most important engineering decision was to make observability a schema
contract. Even local runs emit stable metadata keys:agent name, tool name, MCP
server, token count, latency, cost, and claim id. LangSmith can consume those
fields when tracing is enabled, but the dashboard and eval harness can rely on
the same shape without requiring live credentials.

Wayfinder is not trying to be a general code chatbot. It is a codebase
onboarding workflow with a narrow promise:map the repo, explain entry paths,
verify risky claims, and show where the answer is uncertain. That makes it a
better artifact for engineering interviews because the interesting work is not
hidden in a prompt. It is visible in the state schema, MCP boundaries,
verification labels, failure-mode handling, API runtime, and dashboard evidence.

## 中文

很多 codebase onboarding 工具的问题不是完全没用，而是太早显得很自信。它们可以总结 README，可以列出一些看起来合理的 module，也可以解释一个听起来像函数名的东西。但它们通常不会告诉你：哪些内容真的来自代码证据，哪些只是推断，哪些已经被测试结果反驳。

Wayfinder 是我对这个问题的回答。它不是一个单纯的代码聊天机器人，而是一个以证据为中心的 multi-agent codebase onboarding workflow。用户给一个 repo 和一个问题后，系统会通过 LangGraph Supervisor 路由任务，用 deterministic MCP server 收集代码事实，用测试验证高风险 claim，最后输出时保留 verified / unverified / contradicted 的区别。

系统里有三个主要 agent。

`architect_mapper` 负责 repo-level orientation。它调用我自己写的 `mcp-repo-mapper`，扫描文件结构、语言占比、framework signal、entry point 和 Python import dependency。它回答的是“这个 repo 大概怎么组织，入口在哪里，架构证据能证明什么”。

`entry_explainer` 负责 symbol 和 call path。它调用 `mcp-ast-explorer`，用 AST 查 definition、signature、reference、direct call chain 和 class hierarchy。如果 symbol 不存在，工具返回结构化 not-found，而不是让 LLM 编一个相近的函数名。

`verifier` 负责高风险 claim。它不会验证每一句话，因为 source location、signature、reference 这些已经来自 deterministic tool，可以直接用 AST evidence 标注。真正需要 executable evidence 的，是 runtime behavior、数字、状态变化、错误路径、测试结果这类 claim。本地可信模式可以接 `mcp-test-runner`，但 public Railway 部署里执行测试仍然关闭，直到单独的 sandbox worker 做完。

Wayfinder 最关键的输出不是一段漂亮总结，而是三个标签：`verified`、`unverified`、`contradicted`。`unverified` 是产品功能，不是失败。如果没有测试覆盖、语言不支持、测试 timeout、输出 malformed、或者用户跳过执行，系统会明确标成 unverified，而不是假装已经证明。如果测试直接反驳某个 claim，这个 claim 会变成 contradicted，并触发 bounded reflection rewrite，把不安全的最终表述修掉。

Commit 8 把这个 workflow 变成可检查的 product surface。FastAPI 提供 `/explain`、`/status/{job_id}`、`/refine/{job_id}` 和 `/runs`。Dashboard 用 Next.js 读取最近 runs，展示 trace link、agent latency、token/cost、routing flow、verification stats 和 failure mode frequency。Docker、Compose、CI、README、Design v1、demo script 和双语发布稿一起构成本地 ship evidence。

我最看重的设计点是：observability 先作为 schema contract 出现。即使本地没有 LangSmith credential，每次 run 仍然有稳定字段：agent_name、tool_name、mcp_server、tokens、latency、cost_usd、claim_id。以后 Project 7 eval harness 可以直接复用这些字段，不需要重新猜测每次 run 到底发生了什么。

Wayfinder 的价值不是“又做了一个 agent UI”。它的价值是把 codebase understanding 变成一个可验证、可恢复、可追踪的 workflow。对求职项目来说，这比单纯聊天体验更有说服力，因为面试官能看到真实工程边界：state schema、MCP integration、verification policy、failure-mode handling、API runtime、dashboard evidence，以及哪些地方我选择诚实地说“不确定”。
