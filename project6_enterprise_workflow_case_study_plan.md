# Project 6 `wayfinder` 修改计划：Enterprise Workflow Case Study

> 用途：保存本次 ChatGPT 讨论结果，并喂给 Codex，帮助修改 Project 6 的流程设计。
> 目标：不要新增一个完整大项目，而是在现有 Project 6 `wayfinder` 中加入一个轻量的 enterprise workflow case study，补足 AI Agent Developer 岗位所需的企业业务流程、权限边界、审计日志、human-in-the-loop、失败处理和业务指标能力。

---

## 1. 背景结论

### 1.1 我的目标岗位

目标岗位不是纯 ML Research / Applied Scientist，而是：

> **Backend-oriented AI Application Engineer / AI Agent Developer / LLM Application Engineer**

核心画像：

- 会做 LangGraph / Agent workflow
- 会做 RAG / retrieval / grounding
- 会做 MCP / tool calling
- 会做 FastAPI / backend / cloud infra
- 会做 eval / observability / anti-hallucination
- 能把 LLM Agent 接进真实业务流程

---

## 2. 当前项目组合判断

我现在不缺项目数量。

现有项目链已经包括：

| 项目 | 主要证明能力 |
|---|---|
| `mnemo` / personal knowledge API | FastAPI、PostgreSQL、Redis、JWT、Docker、CI/CD |
| `pka-event-pipeline` | AWS SQS、Lambda、DynamoDB、Terraform、DLQ、idempotency |
| `arxiv-rag` | RAG、hybrid retrieval、reranking、pgvector、eval |
| 3 个 MCP servers | self-authored MCP tools、code intelligence、tool infrastructure |
| `wayfinder` | multi-agent codebase onboarding、LangGraph Supervisor、verification |
| 40-OSS-repo eval | routing accuracy、factual correctness、citation grounding、verification_rate |
| production AI infra layer | LLM gateway、multi-tenancy、OpenTelemetry、cost/rate limit |
| `agent-eval-harness` | agent regression testing、LLM-as-judge、failure taxonomy |

因此不建议新增 Project 11。

---

## 3. 缺口是什么

当前主线很强的是：

| 维度 | 当前状态 |
|---|---|
| 软件工程 | 强 |
| Agent 编排架构 | 强 |
| RAG / retrieval | 中高 |
| LLM eval / grounding | 中高 |
| backend / cloud infra | 中高 |

当前相对缺的是：

| 缺口 | 说明 |
|---|---|
| 企业业务流程场景 | 目前 Wayfinder 偏 codebase onboarding / developer tooling，不是 CRM、客服、招聘、billing 这类企业 workflow |
| 权限边界 | Agent 哪些工具能自动执行，哪些必须人工确认，需要更清晰 |
| 审批队列 | high-risk action 需要 human-in-the-loop |
| 审计日志 | 企业 Agent 需要知道每一步为什么执行、谁批准、输入输出是什么 |
| 失败处理 | API timeout、低置信度、policy violation、工具失败后的 fallback |
| 业务指标 | 不只是 factual correctness，还要有 approval accuracy、unsafe-action blocking、cost per candidate 等业务级 metric |

核心判断：

> 我不需要再做一个完整项目，而是需要让现有 Project 6 看起来更像真实企业 Agent 系统。

---

## 4. 最终方案

### 4.1 不新增独立项目

不要新开一个完整 `recruiting-agent-crm` 项目。

正确做法是在 Project 6 `wayfinder` 中增加：

> **Enterprise Workflow Case Study：Permission-Gated Recruiting CRM Agent Demo**

它是一个 case study / examples module / demo workload，不是主项目。

### 4.2 它补什么

这个 case study 用来证明：

- 我理解 enterprise workflow agent 不是 chatbot
- 我知道 Agent 工具调用必须有 permission policy
- 我知道高风险动作需要 human approval
- 我知道企业系统需要 audit log
- 我知道要处理 API failure / low confidence / unsafe actions
- 我知道怎么设计 workflow-level eval metrics
- 我知道怎么把 Agent 架构迁移到非 codebase 场景

---

## 5. 放在哪里

推荐目录结构：

```text
wayfinder/
├── app/
│   ├── graphs/
│   │   ├── wayfinder_graph.py
│   │   └── enterprise_workflow_graph.py
│   ├── tools/
│   │   ├── mock_crm.py
│   │   ├── mock_email.py
│   │   ├── mock_policy_store.py
│   │   ├── approval_queue.py
│   │   └── audit_log.py
│   └── schemas/
│       ├── candidate.py
│       ├── job.py
│       ├── approval.py
│       └── audit.py
├── examples/
│   └── enterprise_workflow/
│       ├── README.md
│       ├── recruiting_crm_demo.py
│       ├── mock_candidates.json
│       ├── mock_jobs.json
│       ├── mock_contacts.json
│       ├── mock_policy.md
│       └── expected_outputs/
│           ├── sample_audit_log.json
│           ├── sample_approval_task.json
│           └── sample_agent_report.md
├── docs/
│   └── case_studies/
│       ├── enterprise_workflow_agent.md
│       └── enterprise_eval_report.md
```

---

## 6. Case Study 主题

### 名称

```text
Permission-Gated Recruiting CRM Agent
```

### 一句话说明

> A lightweight enterprise workflow demo that simulates recruiting/referral CRM automation with permission-gated tool execution, approval queues, audit logs, unsafe-action blocking, and workflow-level evals.

### 业务流程

```text
candidate profile
→ parse candidate
→ match jobs
→ draft referral / cold outreach
→ risk check
→ approval routing
→ mock CRM update
→ audit log
→ final report
```

---

## 7. LangGraph 节点设计

新增文件：

```text
app/graphs/enterprise_workflow_graph.py
```

推荐 8 个节点：

| 节点 | 作用 |
|---|---|
| `parse_candidate` | 解析候选人 profile，提取 skills、experience、target role、risk flags |
| `match_jobs` | 根据候选人信息和 job description 做岗位匹配 |
| `draft_outreach` | 生成 referral / cold message 草稿 |
| `risk_check` | 检查高风险内容，例如夸大经历、敏感身份、自动发送邮件、未验证指标 |
| `approval_router` | 根据 risk level 和 tool permission 决定自动执行还是进入审批 |
| `mock_crm_update` | 更新模拟 CRM 状态 |
| `audit_logger` | 记录每一步工具调用和决策 |
| `final_report` | 输出 workflow summary 和 action status |

状态流：

```text
NEW
→ PARSED
→ MATCHED
→ DRAFTED
→ RISK_CHECKED
→ WAITING_APPROVAL / AUTO_APPROVED
→ CRM_UPDATED / BLOCKED / ESCALATED
→ COMPLETED
```

---

## 8. State Schema 设计

建议新增：

```python
class EnterpriseWorkflowState(TypedDict):
    run_id: str
    candidate: CandidateProfile
    jobs: list[JobDescription]
    contacts: list[Contact]
    parsed_profile: dict
    job_matches: list[JobMatch]
    outreach_draft: str
    risk_flags: list[RiskFlag]
    risk_level: Literal["low", "medium", "high"]
    proposed_actions: list[ProposedAction]
    approval_tasks: list[ApprovalTask]
    audit_events: list[AuditEvent]
    final_status: Literal["completed", "waiting_approval", "blocked", "failed"]
    final_report: str
```

---

## 9. Tool Policy 设计

新增文件：

```text
app/tools/tool_permissions.py
```

示例：

```python
TOOL_POLICIES = {
    "read_candidate": "allow",
    "match_jobs": "allow",
    "draft_outreach": "allow",
    "update_crm_status": "allow_if_low_risk",
    "send_email": "requires_approval",
    "bulk_send_email": "requires_approval",
    "delete_candidate": "deny",
}
```

解释逻辑：

| Policy | 含义 |
|---|---|
| `allow` | Agent 可自动执行 |
| `allow_if_low_risk` | 只有 low-risk 时可自动执行 |
| `requires_approval` | 必须创建 approval task |
| `deny` | 永远不允许 Agent 自动执行 |

面试表达：

> I separated tool permissions from the agent graph. The model can propose actions, but the policy layer decides whether the action can execute, needs approval, or must be blocked.

---

## 10. Approval Queue 设计

新增文件：

```text
app/tools/approval_queue.py
```

Approval task schema：

```python
class ApprovalTask(BaseModel):
    task_id: str
    run_id: str
    action_name: str
    action_summary: str
    risk_level: Literal["low", "medium", "high"]
    reason: str
    status: Literal["pending", "approved", "rejected", "needs_edit"]
    created_at: datetime
```

触发审批的场景：

| 场景 | 结果 |
|---|---|
| 自动发送 email | requires approval |
| 修改 CRM 状态且 risk high | requires approval |
| 候选人信息不完整 | needs human review |
| 生成内容涉及夸大经历 | blocked or needs edit |
| 批量发送 outreach | requires approval |

---

## 11. Audit Log 设计

新增文件：

```text
app/tools/audit_log.py
```

每个 tool call / node decision 都记录：

```python
class AuditEvent(BaseModel):
    event_id: str
    run_id: str
    node_name: str
    tool_name: str | None
    input_summary: str
    output_summary: str
    risk_level: Literal["low", "medium", "high"] | None
    approval_required: bool
    status: Literal["success", "failed", "blocked", "waiting_approval"]
    latency_ms: int
    cost_usd: float
    error_type: str | None
    created_at: datetime
```

样例 JSON：

```json
{
  "run_id": "run_001",
  "node": "draft_outreach",
  "tool": "mock_email_draft",
  "risk_level": "medium",
  "approval_required": true,
  "latency_ms": 842,
  "cost_usd": 0.012,
  "status": "success"
}
```

---

## 12. Mock Tools 设计

### 12.1 `mock_crm.py`

功能：

- `read_candidate(candidate_id)`
- `update_candidate_status(candidate_id, status)`
- `add_note(candidate_id, note)`
- `create_referral_request(candidate_id, job_id)`

注意：

- 不接真实 CRM
- 所有 mutation 都经过 permission policy
- update/delete/bulk action 需要检查 approval

### 12.2 `mock_email.py`

功能：

- `draft_email(to, subject, body)`
- `send_email(...)`

要求：

- `draft_email` 可以 allow
- `send_email` 必须 `requires_approval`
- demo 中可以只生成 draft，不真实发送

### 12.3 `mock_policy_store.py`

功能：

- 存储 outreach policy
- 存储 allowed / denied action
- 提供 risk check 规则

示例 policy：

```text
- Do not claim direct referral unless a contact agreed.
- Do not invent work authorization details.
- Do not exaggerate project metrics.
- Do not send emails automatically without explicit approval.
- Do not disclose sensitive personal data unless required.
```

---

## 13. 示例数据设计

放在：

```text
examples/enterprise_workflow/
```

### 13.1 `mock_candidates.json`

至少 50 条 synthetic candidates。

每条包括：

```json
{
  "candidate_id": "cand_001",
  "name": "Alex Chen",
  "education": "MS Computer Science",
  "skills": ["Python", "FastAPI", "LangGraph", "RAG"],
  "experience": ["Backend internship", "RAG project"],
  "target_roles": ["AI Engineer", "Backend Engineer"],
  "location": "San Francisco",
  "constraints": ["needs sponsorship"]
}
```

### 13.2 `mock_jobs.json`

至少 20 条 job descriptions。

每条包括：

```json
{
  "job_id": "job_001",
  "company": "Salesforce",
  "title": "AI Agent Engineer",
  "requirements": ["Python", "LangGraph", "RAG", "API integration", "HITL"],
  "nice_to_have": ["CRM", "Salesforce", "enterprise workflow"],
  "location": "San Francisco"
}
```

### 13.3 `mock_contacts.json`

至少 20 条 contacts。

每条包括：

```json
{
  "contact_id": "contact_001",
  "company": "Salesforce",
  "role": "Software Engineer",
  "relationship": "alumni",
  "allowed_contact_method": "draft_only"
}
```

---

## 14. Failure Handling

必须覆盖以下失败类型：

| Failure Mode | Handling |
|---|---|
| Missing candidate info | ask human / mark incomplete |
| No matching job found | return low-confidence report |
| Low fit score | route to human approval |
| Email send requested | create approval task, do not send |
| CRM update high risk | approval required |
| Tool timeout | retry once with exponential backoff |
| Policy violation | block action and log reason |
| LLM hallucinated contact | block if contact not found in mock_contacts |

核心原则：

> The agent may propose actions, but it cannot execute high-risk mutations without policy and approval.

---

## 15. Eval 设计

新增：

```text
docs/case_studies/enterprise_eval_report.md
```

Benchmark 规模建议：

```text
50 synthetic candidates
20 job descriptions
20 contacts
10 risky cases
```

Metrics：

| Metric | 说明 |
|---|---|
| `job_match_precision` | top-k job match 是否合理 |
| `draft_acceptance_rate` | outreach draft 是否可直接使用或轻微修改 |
| `approval_routing_accuracy` | 高风险动作是否正确进入审批 |
| `unsafe_action_blocking_rate` | 危险动作是否被阻止 |
| `tool_call_success_rate` | mock tools 是否成功执行 |
| `avg_latency_ms` | 平均处理时间 |
| `cost_per_candidate_usd` | 每个候选人处理成本 |
| `human_intervention_rate` | 需要人工介入的比例 |

示例结果格式：

```md
| Metric | Result |
|---|---:|
| Job match precision@3 | 82% |
| Draft acceptance rate | 74% |
| Approval routing accuracy | 91% |
| Unsafe action blocking rate | 100% |
| Tool-call success rate | 96% |
| Average latency | 4.2s |
| Cost per candidate | $0.04 |
| Human intervention rate | 28% |
```

注意：所有数据必须可复现，不要写无法 defend 的数字。

---

## 16. README 添加内容

在 `wayfinder` 主 README 加：

```md
## Enterprise Workflow Case Study

To show that Wayfinder's agent architecture generalizes beyond codebase onboarding, I added a permission-gated recruiting CRM workflow demo.

The demo simulates an enterprise agent that parses candidate profiles, matches roles, drafts referral outreach, updates CRM state, and routes high-risk actions through human approval.

Key production-safety features:
- risk-tiered tool permissions
- human approval queue
- audit logs for every tool call
- unsafe-action blocking
- failure-mode classification
- cost and latency tracking
```

---

## 17. 简历写法

不要新增一个独立 project title。

在 `wayfinder` 项目下加一条 bullet：

```text
Extended Wayfinder with an enterprise workflow case study that modeled recruiting CRM automation with permission-gated tool execution, approval queues, audit logs, unsafe-action blocking, and workflow-level evals over synthetic candidate/job datasets.
```

如果需要更短版本：

```text
Added a permission-gated enterprise workflow demo with approval queues, audit logs, unsafe-action blocking, and synthetic CRM evals to show safe agent execution beyond codebase onboarding.
```

---

## 18. Codex 修改任务清单

### Task A — Add directory structure

Create:

```text
app/graphs/enterprise_workflow_graph.py
app/tools/mock_crm.py
app/tools/mock_email.py
app/tools/mock_policy_store.py
app/tools/approval_queue.py
app/tools/audit_log.py
app/tools/tool_permissions.py
app/schemas/candidate.py
app/schemas/job.py
app/schemas/approval.py
app/schemas/audit.py
examples/enterprise_workflow/
docs/case_studies/
```

### Task B — Add schemas

Implement Pydantic models for:

- `CandidateProfile`
- `JobDescription`
- `Contact`
- `JobMatch`
- `RiskFlag`
- `ProposedAction`
- `ApprovalTask`
- `AuditEvent`
- `EnterpriseWorkflowState`

### Task C — Add mock tools

Implement mock tools:

- read candidate
- match jobs
- draft email
- create approval task
- update CRM status
- write audit event
- block unsafe action

### Task D — Add LangGraph workflow

Implement 8-node workflow:

```text
parse_candidate
match_jobs
draft_outreach
risk_check
approval_router
mock_crm_update
audit_logger
final_report
```

### Task E — Add example runner

Create:

```text
examples/enterprise_workflow/recruiting_crm_demo.py
```

It should:

1. Load candidate / job / contact JSON files
2. Run one candidate through the graph
3. Print final report
4. Save audit log and approval task to `expected_outputs/`

### Task F — Add docs

Create:

```text
docs/case_studies/enterprise_workflow_agent.md
docs/case_studies/enterprise_eval_report.md
examples/enterprise_workflow/README.md
```

### Task G — Add tests

Add tests for:

- policy decisions
- approval routing
- unsafe email send blocking
- audit event creation
- missing contact handling
- high-risk CRM update requiring approval

---

## 19. 最小版本范围

不要 overbuild。

### 必须做

- LangGraph workflow
- mock CRM
- mock email draft
- tool permissions
- approval queue
- audit log
- example data
- case study doc
- eval report

### 不必须做

- 真实 Gmail API
- 真实 Salesforce API
- 独立前端 dashboard
- 独立部署
- 完整登录系统
- 完整 SaaS 化

核心原则：

```text
workflow realism > UI polish
permission boundary > model cleverness
eval report > fancy demo
```

---

## 20. 执行顺序

### Step 1 — 先完成 Wayfinder 主体

优先完成：

- LangGraph Supervisor
- 3 sub-agents
- 5 MCP servers
- Verifier
- HITL
- EVAL_REPORT
- README
- demo video

### Step 2 — 再加 Enterprise Workflow Case Study

用 20–30 小时做 lightweight version。

### Step 3 — 把它写进 README / 简历

只写一条 bullet，不新增项目。

---

## 21. 对外讲法

面试中可以这样说：

> My main project is Wayfinder, a tool-grounded codebase onboarding agent. I also added an enterprise workflow case study to demonstrate that the same agent architecture can support permission-gated business workflows with human approval, auditability, and risk-controlled tool execution.

更具体：

> I did not want the agent to behave like an unconstrained chatbot. I added a policy layer so the model can propose actions, but high-risk mutations such as sending emails or updating CRM state require approval. Every tool call is logged with risk level, latency, status, and error type.

---

## 22. 最终判断

最终 Project 6 结构应该是：

```text
Project 6 wayfinder
├── 主体：codebase onboarding agent
├── eval：40 OSS repo benchmark
├── infra：LLM gateway / OTel / HITL / checkpointer
└── case study：enterprise workflow agent demo
```

这样既不稀释主线，又补足 AI Agent Developer 岗位最看重的 enterprise workflow / safety / auditability / HITL 能力。
