# AgentScope System Design v8.3

## 1. Purpose

AgentScope is an experimental platform for building and comparing agent architectures. Coding tasks are the first workload. The stable product is the harness around agents; an individual agent topology is a replaceable experiment.

The platform provides common execution, tool, policy, model, observability, verification, persistence, and evaluation boundaries so architectures can be compared without rebuilding infrastructure.

### 1.1 Primary use cases

1. Run a software-engineering task through a selected agent architecture.
2. Execute commands and manipulate a task workspace without exposing the host.
3. Compare architectures, models, prompts, and reasoning settings against identical scenarios.
4. Verify task completion independently of the agent's claim.
5. Diagnose a run from normalized traces, tool results, costs, and artifacts.
6. Extend the platform with new topologies without bypassing shared safety controls.

### 1.2 Users

- Agent developers implementing and debugging a topology.
- Platform developers maintaining runtime, tools, policy, observability, and evaluation.
- Researchers comparing architecture and model configurations.
- End users submitting coding tasks through CLI, UI, or API adapters.

### 1.3 Non-goals

The initial platform is not:

- a general autonomous-computing service;
- a multi-tenant production control plane;
- a universal declarative graph language;
- a replacement for source control or CI;
- a system that grants models direct access to credentials or the host environment.

## 2. Current implementation status

| Increment | Status | Delivered |
|---|---|---|
| Phase 0 | Complete | Architecture contracts, bootstrap/config separation, runtime protocol and boundary policies, telemetry foundation, security tests, ADRs, and repository hygiene |
| Phase 1A.1 | Complete | Concrete Docker Sandboxes runtime, lifecycle and cleanup, environment/filesystem/network isolation, native resource limits, timeout termination, real-backend contract/security suite, and dedicated smoke workflow |
| Phase 1A.2+ | Planned | Model integration, OpenTelemetry evolution, Tool Gateway, first agent topology, budgets, verification, service, and end-to-end acceptance |

Phase 1A.1 is the current implementation baseline. Sections describing later components are normative target design, not claims that those components already exist.

## 3. System requirements

### 3.1 Functional requirements

- Select an `AgentArchitecture` by stable key and resolve its canonical version.
- Invoke models through typed adapters with native structured tool calling.
- Validate and execute all actions through one Tool Gateway.
- Execute untrusted commands through `SandboxRuntime`.
- Confine file operations to one task workspace.
- Enforce iteration, time, token, cost, and policy limits.
- Verify completion using evidence independent of the agent conversation.
- Produce normalized run, tool, usage, cost, verification, and evaluation records.
- Support CLI first, then UI and API adapters through `AgentService`.

### 3.2 Security requirements

- No implicit host environment inheritance.
- No model-visible credential lookup.
- No host path access outside the task workspace.
- No external network access under the default policy.
- No shell reinterpretation for ordinary command execution.
- Bounded command duration and output.
- Native CPU and memory limits.
- A reported timeout guarantees the remote command cannot continue.
- Sandbox cleanup is explicit, observable, idempotent after success, and retryable after failure.
- Telemetry is sanitized before export; sanitization failure drops the event.

### 3.3 Quality attributes

| Attribute | Requirement |
|---|---|
| Maintainability | Small components with explicit ownership and package-level contracts |
| Testability | Protocol boundaries, deterministic fakes, fault injection, and separately marked external tests |
| Observability | Stable semantic events/spans independent of export backend |
| Reproducibility | Versioned architecture, scenario, model, prompt, tool schema, runtime image, and `sbx` metadata |
| Reliability | Typed outcomes, bounded cleanup, graceful telemetry degradation, explicit stop reasons |
| Performance | Persistent sandbox per run; serialized actions initially; asynchronous telemetry export |

## 4. Architecture

```text
CLI / UI / API adapters
          │
          ▼
     AgentService
          │
          ▼
ArchitectureRegistry ──► selected AgentArchitecture
          │                        │
          │                        ▼
          │                 LangGraph workflow
          │                        │
          ├──────────────┬─────────┼───────────────┐
          ▼              ▼         ▼               ▼
    ModelRegistry   ToolGateway  Verifier    Budget/Policy
                         │
                 ┌───────┴────────┐
                 ▼                ▼
          Workspace tools   SandboxRuntime
                                   │
                                   ▼
                          SbxSandboxRuntime
                                   │
                                   ▼
                         Docker Sandbox/microVM

All components ──► AgentScope observability ──► OpenTelemetry/OTLP
                                                   │
                                             Phoenix/Langfuse

AgentService ──► run records / evaluation artifacts / persistence
```

### 4.1 Stable boundaries

- `AgentService` is the only execution API exposed to clients.
- `AgentArchitecture` owns topology, not infrastructure.
- `ToolGateway` is the only action-dispatch boundary.
- `SandboxRuntime` is the only command-execution boundary.
- Workspace policy is shared by every file-facing component.
- Model adapters normalize provider behavior before graph code consumes it.
- Observability exporters do not define internal event semantics.
- Verification and evaluation use independent evidence.

### 4.2 Dependency direction

```text
Adapters → AgentService → AgentArchitecture
                         ├── Models
                         ├── ToolGateway → Runtime / Workspace
                         ├── Policy / Budgets
                         ├── Verification
                         └── Observability
```

Infrastructure packages must not import concrete architecture implementations. Architecture implementations may depend only on public platform contracts.

## 5. Run lifecycle

```text
accept request
    ↓
resolve configuration and architecture identity
    ↓
prepare isolated workspace and runtime
    ↓
invoke model
    ↓
validate structured tool calls and policy
    ↓
execute calls serially through ToolGateway
    ↓
append normalized observations
    ↓
continue, pause for approval, or request finish
    ↓
run independent verification
    ├── fail → continue or stop by budget
    └── pass → finalize report
    ↓
flush telemetry, persist records, close runtime
```

Terminal stop reasons are normalized: `completed`, `max_iterations`, `max_runtime`, `max_tokens`, `max_cost`, `timeout`, `tool_failure`, `verification_failure`, `model_failure`, `policy_violation`, and `cancelled`.

A pending human approval is a paused state, not a terminal result.

## 6. Agent architecture boundary

`AgentArchitecture` represents one control topology. Its identity contains a stable key and implementation version. `ArchitectureRegistry` resolves configuration keys to registered implementations; callers cannot supply an unrelated version string.

An architecture may define:

- graph nodes and edges;
- architecture-specific serializable state;
- role prompts;
- model-role assignments;
- planning, reflection, delegation, or memory behavior.

An architecture must not bypass:

- Tool Gateway validation or policy;
- runtime/workspace confinement;
- model usage and cost normalization;
- observability conventions;
- verification and evaluation boundaries.

The first topology is `SimpleToolAgent`:

```text
prepare → agent → tools → agent → verify
                    ▲        │
                    └────────┘
```

Planner/executor, validator, delegation, parallel, and memory variants are separate implementations rather than modes in one universal graph.

## 7. State and runtime context

Durable graph state contains serializable data only:

- IDs and canonical configuration identity;
- messages and normalized tool observations;
- counters, budgets, stop state, and verification state;
- references to artifacts and traces.

Live dependencies remain outside durable state:

- authenticated model clients;
- `SandboxRuntime` instances;
- Tool Gateway and policy objects;
- telemetry providers/exporters;
- verifier implementations;
- database or storage clients.

Graph nodes return explicit state updates. They do not mutate shared state in place.

## 8. Execution runtime

### 8.1 Runtime contract

```python
class SandboxRuntime(Protocol):
    @property
    def workspace(self) -> WorkspaceRoot: ...
    def execute(self, request: ExecRequest) -> ExecResult: ...
    def close(self) -> None: ...
```

File methods are not part of `SandboxRuntime`. Workspace tools use host-side confined file access. Only command execution crosses into the sandbox.

### 8.2 Request and result

```python
@dataclass(frozen=True, slots=True)
class ExecRequest:
    command: tuple[str, ...]
    cwd: str = "."
    env: Mapping[str, str] = field(default_factory=dict)
    timeout_s: float | None = None
    max_output_bytes: int = 1_000_000


class ExecStatus(StrEnum):
    COMPLETED = "completed"
    TIMED_OUT = "timed_out"
    INFRA_FAILURE = "infra_failure"


@dataclass(frozen=True, slots=True)
class ExecResult:
    status: ExecStatus
    exit_code: int | None = None
    stdout: bytes = b""
    stderr: bytes = b""
    truncated: bool = False
    duration_s: float = 0.0
    message: str = ""
```

Contract rules:

- Commands remain argument vectors; no host shell reparses them.
- `COMPLETED` always carries an exit code, including non-zero user-command exits.
- `TIMED_OUT` and `INFRA_FAILURE` do not carry an exit code.
- Output limits apply independently to stdout and stderr.
- `message` is human-readable diagnostic text, not a machine-readable code.
- `cwd` is workspace-relative and validated before external invocation.
- `timeout_s=None` selects the configured runtime default.

### 8.3 Concrete backend

`SbxSandboxRuntime` owns one named Docker Sandbox and one workspace. `SbxCli` is a private argv-only subprocess boundary.

Verified baseline:

| Property | Value |
|---|---|
| `sbx` version | `v0.39.0` |
| Sandbox agent | `shell` |
| Sandbox Python | 3.14 major/minor |
| CPU control | `sbx create --cpus` |
| Memory control | `sbx create --memory`; minimum 1 GiB |
| Network control | sandbox-scoped `--deny-network "**"` |
| Workspace mount | canonical host path mounted at the same path |

Runtime instances are single-owner and not concurrency-safe. `execute()` and `close()` must be serialized.

### 8.4 Environment policy

The runtime constructs the command environment from:

```text
empty host-derived baseline
    + sandbox-local PATH/TMPDIR
    + explicitly requested variables accepted by a positive allowlist
```

The runtime validates the policy itself. It never copies the host environment and never emits bare `-e NAME`, because `sbx` interprets that form as a host-variable lookup. It emits only explicit `NAME=value` pairs.

`HOME` is not overridden: the real backend does not mount the workspace at `/workspace`, so the shell image keeps its valid native home.

### 8.5 Workspace confinement

`WorkspaceRoot` stores an existing canonical absolute directory. `resolve_within` rejects absolute candidates, parent traversal, and symlink targets outside the root before any `sbx` call.

The sandbox mount is a second isolation layer. Files outside the mounted workspace are unavailable inside the microVM even if a path-like string is passed as an ordinary command argument.

Workspace writes are not transactional. After timeout or command failure, files may be partial. They remain available for diagnosis; the caller decides whether to inspect, discard, or remount the workspace.

### 8.6 Network policy

Phase 1A.1 supports only `NetworkPolicy.DISABLED`. The serialized value `"disabled"` is normalized; any other value is rejected. Every valid configuration applies sandbox-scoped deny-all policy.

`sbx` uses transparent interception. A local TCP `connect()` may succeed even when traffic is denied. Verification therefore tests useful communication: external HTTP cannot complete successfully and raw TCP data cannot reach a controlled host service.

### 8.7 Timeout semantics

Killing local `sbx exec` does not terminate the remote command. Timeout therefore invalidates the whole sandbox.

```text
execution deadline
    ↓
sbx stop
    ├── success → INVALID, return TIMED_OUT
    └── failure → sbx rm -f
                     ├── confirmed → CLOSED, return TIMED_OUT
                     └── unconfirmed → INVALID, return INFRA_FAILURE
```

Invariant: `TIMED_OUT` means the remote command is known to be unable to continue.

### 8.8 Creation and cleanup

Creation applies unique naming, resource limits, deny-all networking, and exactly one workspace. Any create error or timeout triggers compensating forced removal because local failure does not prove remote allocation was atomic.

`close()` immediately makes the runtime non-executable. It succeeds when removal returns success or `sbx ls --json` independently confirms absence. Otherwise it raises `SandboxCleanupError` and remains retryable from `INVALID`. Repeated closure after confirmed removal is a no-op.

## 9. Tool Gateway

Tool Gateway is the policy and dispatch boundary for every model-requested action.

Responsibilities:

1. Parse and validate typed tool input.
2. Attach a stable `tool_call_id`.
3. Evaluate execution and approval policy before side effects.
4. Execute calls serially in provider-emitted order.
5. Dispatch commands to `SandboxRuntime` and files to confined workspace services.
6. Normalize results and errors.
7. Emit observability spans and workspace-mutation metadata.

Initial tools:

- `list_files`
- `read_file`
- `write_file`
- `execute_command`
- `finish`

Later tools add structured patching, tests, Git inspection, delegation, and approved destructive operations.

### 9.1 Structured errors

Tool failures carry stable categories such as:

- `invalid_arguments`
- `path_violation`
- `policy_rejected`
- `timeout`
- `command_failed`
- `runtime_unavailable`
- `output_truncated`
- `internal_error`

Human-readable messages are diagnostic only. Logic uses typed status/category fields.

### 9.2 Structured patching

`apply_patch` uses typed replace operations rather than a custom textual diff grammar. Each operation declares path, old text, new text, and expected occurrence count.

All operations are validated before writing. Same-file operations apply sequentially to the preceding result. If any operation fails, no file is committed. Writes produce before/after hashes and a changed-file manifest.

## 10. Model integration and cost

The model layer separates:

- wire protocol;
- provider/service;
- model identity;
- credentials;
- reasoning and tool-binding options;
- pricing identity.

The first adapter implements an OpenAI-compatible chat-completions interface and is exercised against OpenRouter and Meta Model API/Muse. Provider-specific behavior remains behind the adapter.

### 10.1 Registry

`ModelRegistry` resolves a model key to a configured adapter. Cache identity includes model configuration/version, reasoning options, provider-specific request options, and tool-schema version. Credentials are injected by the trusted composition root and never enter serializable state.

### 10.2 Usage normalization

```python
@dataclass(frozen=True)
class LLMUsage:
    input_tokens: int
    output_tokens: int
    total_tokens: int
    cached_input_tokens: int | None = None
    reasoning_tokens: int | None = None
    provider_reported_cost_usd: float | None = None
```

Provider responses are normalized once. Cost tracking, budgets, evaluation, and observability consume `LLMUsage`; they do not parse raw provider responses independently.

### 10.3 Cost calculation

Cost source precedence:

1. Explicitly authoritative provider-reported cost.
2. Configured pricing applied to normalized usage.
3. Unknown cost.

Unknown cost is never treated as zero for budget enforcement. Pricing units are USD per million tokens and support input, output, and cached input dimensions initially.

## 11. Observability

AgentScope defines backend-neutral semantics above OpenTelemetry. Phoenix and Langfuse are OTLP destinations, not architectural dependencies.

### 11.1 Trace hierarchy

```text
agent.run
├── architecture.invoke
├── model.invoke
├── tool.validate
├── tool.execute
│   └── task.subagent.run
├── verification.run
└── persistence.flush
```

Core attributes include run/scenario/configuration identity, architecture key/version, model/provider/protocol, tool name/call ID, normalized status/error category, token usage, cost source/value, duration, runtime image, `sbx` version, and network policy.

### 11.2 Export policy

- Batch export during normal execution.
- Bounded flush and shutdown.
- No-op and in-memory implementations for tests and degraded operation.
- Export/configuration failure must not fail the agent run.
- Sanitization occurs before export; failure drops telemetry.
- Raw credentials, environment values, full prompts, and unrestricted file contents are not default attributes.

## 12. Verification and evaluation

Verification decides whether an online run may finish. Evaluation measures correctness and compares configurations after the run. They share scenario metadata but not necessarily evidence.

### 12.1 Verification

Verification commands use `ExecRequest` and declare expected exit codes. The verifier checks required files, command results, meaningful test collection, protected paths, relevant changes, and required outputs.

The verifier reports explicit evidence and flags:

- premature finish;
- vacuous test pass;
- irrelevant changes;
- missing required output;
- test tampering.

### 12.2 Scenario model

A `TaskScenario` contains:

- stable name and version;
- task prompt and fixture version/hash;
- setup and cleanup requests;
- visible verification commands;
- protected hidden checks;
- required/forbidden files and paths;
- resource and policy limits;
- reference solution used to validate the scenario itself.

A scenario is invalid if the initial fixture already passes or its protected reference solution fails.

### 12.3 Configuration identity

Evaluation identity includes:

- scenario and fixture version;
- architecture key/version;
- model and reasoning configuration;
- prompt and tool-schema hashes;
- pricing configuration;
- harness Git SHA;
- runtime image and `sbx` version;
- network policy;
- repetition index.

Comparisons operate on configuration IDs, not informal labels.

### 12.4 Outputs and metrics

Each scenario/repetition produces one record containing completion, verification and hidden-check results, false accept/reject classification, tests, iterations, error counts, tokens, cost, duration, trace/artifact references, and configuration identity.

Primary metrics:

- task success rate;
- verifier precision/recall and false-accept rate;
- cost, latency, tokens, and iterations;
- tool-error distribution;
- trajectory-policy violations;
- variance across repeated runs.

## 13. AgentService and adapters

`AgentService` owns run lifecycle and is the sole interface used by CLI, UI, API, and evaluation runners.

Target operations:

- `start_run`
- `stream_events`
- `cancel_run`
- `get_report`
- `resume_run` for approval decisions

The initial CLI calls the service in process. A later FastAPI adapter exposes REST for commands/status and SSE for progress. WebSockets are added only if bidirectional approval interaction requires them. Request handlers never own active graph or sandbox state directly.

## 14. Policy and human approval

Execution policy controls tools, paths, command forms, environment names, networking, resource budgets, and approval requirements. The model cannot elevate policy.

Sensitive actions pause at `tool.validate` before side effects. Decisions are:

- approve;
- edit arguments and approve;
- reject with feedback;
- respond without executing.

LangGraph interrupt/resume provides the control primitive. A minimal in-memory checkpointer supports same-run approval flow; durable persistence remains a later phase.

## 15. Delegation and future architectures

A `task` tool may invoke a configured subagent. The child receives only its task description as conversation state. It shares the runtime/workspace deliberately but not parent messages or intermediate tool history. The parent receives one synthesized `TaskResult`.

Subagent tool calls remain serialized initially. Concurrent shared-workspace execution is prohibited until explicit scheduling, mutation, and conflict semantics are designed and measured.

An LLM validator may advise the primary agent but cannot replace deterministic online verification.

## 16. Security model

### 16.1 Trust boundaries

| Asset/component | Trust | Model-visible | Model-writable |
|---|---|---|---|
| AgentScope process and source | Trusted | No | No |
| Credentials and host environment | Trusted/secret | No | No |
| Policy and runtime configuration | Trusted | Limited summary | No |
| Task workspace | Untrusted | Yes | Through tools |
| Sandbox process/environment | Untrusted | Yes | Yes |
| Model/provider response | Untrusted | Yes | No |
| Logs/traces/run records | Durable | Indirect | No |

### 16.2 Threats and controls

| Threat | Primary controls |
|---|---|
| Host secret exposure | Composition-root credential injection; runtime env allowlist; no host lookup capability; telemetry sanitizer |
| Host filesystem exposure | One workspace mount; canonical path confinement; black-box sentinel tests |
| Command injection | Argument-vector execution; restricted shell as a separate later capability |
| Network exfiltration | Fail-closed `NetworkPolicy.DISABLED`; sandbox-scoped deny-all; black-box HTTP/raw-data tests |
| Resource exhaustion | Native CPU/memory limits; command deadline; output truncation; run budgets |
| Orphan process after timeout | Whole-sandbox stop/removal before reporting `TIMED_OUT` |
| Cleanup leak | Compensating creation removal; verified retryable `close()`; CI cleanup |
| False completion | Independent verifier, non-vacuous checks, hidden evaluation oracle |
| Telemetry leakage | Mandatory recursive sanitization before export; fail-closed drop |
| Cross-run contamination | Dedicated runtime/workspace per run; concurrency prohibited initially |
| Misconfigured approval | Explicit rules and precedence; no implicit auto-approval in interactive runs |

## 17. Reliability and failure handling

| Failure | Behavior |
|---|---|
| Invalid request/configuration | Reject before side effects |
| Sandbox creation failure | Attempt compensating removal; raise normalized creation error |
| User command exits non-zero | Return `COMPLETED` with exit code |
| Local execution infrastructure fails | Return `INFRA_FAILURE` |
| Command deadline expires | Stop/remove sandbox; return `TIMED_OUT` only after termination is confirmed |
| Cleanup cannot be confirmed | Raise `SandboxCleanupError`; keep runtime invalid and retryable |
| Model/provider failure | Normalize, apply retry policy/budget, then stop explicitly |
| Telemetry exporter failure | Record locally when possible; continue run |
| Sanitization failure | Drop telemetry event |
| Verification failure | Continue within budgets or terminate with explicit reason |

## 18. Testing and CI

### 18.1 Test layers

- Unit: schemas, validation, state transitions, normalization, policy, truncation.
- Component: one subsystem through its public boundary.
- Contract: reusable protocol behavior against fakes and real implementations.
- Integration: collaboration across packages.
- Scenario: complete task-to-verification flows.
- External: real `sbx`, observability backends, and model providers.

### 18.2 Runtime verification

The deterministic suite requires no Docker credentials or live services. The marked real-sandbox suite verifies:

- create, reuse, close, and independently confirmed removal;
- argv fidelity, cwd, output, exit codes, duration, and truncation;
- environment and host-secret isolation;
- workspace-only filesystem visibility and path attacks;
- sandbox-scoped network denial;
- applied CPU/memory limits;
- idle, heartbeat, CPU-bound, and child-process timeout termination;
- normalized creation, execution, timeout, and cleanup failures.

### 18.3 CI policy

- Default CI runs deterministic tests, Ruff, mypy, repository checks, and secret scanning.
- `sbx-smoke.yml` runs on a dedicated self-hosted runner with pinned `sbx v0.39.0`.
- The real suite checks the local CLI and sandbox Python baselines before tests.
- Exploratory local runs may explicitly bypass the CLI version gate; CI may not.
- External credentials are unavailable to untrusted pull-request code.
- Cleanup runs even after test failure.

## 19. Project structure

```text
src/agentscope/
├── architectures/       # topology contracts, identity, registry, implementations
├── bootstrap/           # trusted composition and live-client construction
├── config/              # public and secret configuration
├── runtime/             # runtime protocol, policies, sbx backend
│   ├── sandbox.py
│   ├── requests.py
│   ├── results.py
│   ├── environment.py
│   ├── workspace.py
│   ├── sbx.py
│   └── _sbx_cli.py
├── telemetry/           # current telemetry boundary and exporters
├── models/              # planned model adapters and usage normalization
├── tools/               # planned Tool Gateway and tools
├── verification/        # planned online verifier
├── evaluation/          # planned scenarios and evaluation runner
└── service/             # planned AgentService

tests/
├── unit/
├── component/
├── contract/
├── integration/
├── scenario/
└── external/

docs/
├── adr/
└── findings/
```

Packages are created when they acquire implementation responsibility. Empty speculative packages are avoided.

## 20. Delivery roadmap

| Phase | Deliverable | Exit criterion |
|---|---|---|
| 0 | Foundations | Deterministic contracts, security boundaries, telemetry base, and documentation complete |
| 1A.1 | Concrete SandboxRuntime | Complete; real command and black-box isolation suite pass |
| 1A.2 | Model, usage, and cost | Scripted tests plus OpenRouter and Meta-compatible smoke paths |
| 1A.3 | OpenTelemetry observability | Equivalent in-memory/Phoenix/Langfuse semantics; bounded shutdown |
| 1A.4 | Tool Gateway | Initial tools execute only through policy-controlled boundaries |
| 1A.5 | SimpleToolAgent | Deterministic structured-tool trajectory passes |
| 1A.6 | Budgets and stop conditions | Every configured limit has deterministic enforcement tests |
| 1A.7 | Online verification | False-finish and vacuous-success cases are rejected |
| 1A.8 | AgentService and CLI | CLI uses only AgentService and owns full cleanup lifecycle |
| 1A.9 | First end-to-end scenario | Live model → tools → sandbox → verifier → trace completes |
| 1B | Editing and regression evaluation | Smoke scenario set produces reproducible evaluation records |
| 1C | Experiment UI | UI runs and compares configurations through AgentService |
| 1D | Delegation experiment | Context isolation and shared-workspace semantics verified |
| 1E | Human approval | Interrupt/resume and all decision types verified |
| 2 | Runtime hardening | Crash recovery, snapshots, tuned limits, artifact retention |
| 3 | Durable persistence | Checkpointing, journal, attempt identity, idempotency |
| 4–6 | Context, memory, topology, and async experiments | Reproducible comparisons against stable baselines |
| 7–8 | Dashboard and service deployment | Decoupled UI/API and externalized coordination |

Immediate next increment: Phase 1A.2.

## 21. Design decisions

1. The harness is stable; agent topology is experimental.
2. Native structured tool calling replaces free-form action parsing.
3. Tool Gateway is the mandatory policy and action boundary.
4. SandboxRuntime is a small protocol; file tools are separate workspace capabilities.
5. Docker Sandboxes is the concrete runtime; `SbxCli` remains private.
6. Runtime environment and network policies fail closed.
7. A timeout invalidates the sandbox and is reported only after remote termination is confirmed.
8. Runtime instances are single-owner and serialized.
9. Live dependencies never enter durable graph state.
10. Verification is independent of agent claims; hidden evaluation is independent of online verification.
11. Usage and cost are normalized before budgets, evaluation, or observability consume them.
12. OpenTelemetry/OTLP is the observability foundation; exporters are replaceable.
13. AgentService is the only client-facing execution boundary.
14. Concurrency, destructive tools, package installation, and network elevation require explicit later policy design.
15. Documentation, ADRs, and empirical findings are maintained with code.

## 22. Open risks and deferred decisions

| Item | Current position | Owner phase |
|---|---|---|
| Externally removed sandbox indistinguishable from command exit 1 | Documented `sbx` CLI limitation; avoid parsing unstable stderr | Runtime upgrade review |
| Sandbox crash recovery | Runtime becomes unusable; no transparent recovery | Phase 2 |
| Workspace rollback/snapshots | Partial state preserved; caller decides recovery | Phase 2 |
| Package installation/network allowlists | Denied | Phase 6 with approval policy |
| Concurrent workspace mutation | Prohibited | Controlled async experiment |
| Durable approval resume | In-memory checkpoint initially | Phase 3 |
| Multi-provider capability abstraction | Add only after verified incompatibility | Model integration evolution |
| Multi-tenant isolation and scheduling | Not an initial product requirement | Deployment phase |

## 23. Definition of success

AgentScope succeeds when:

- a user can run a coding task through a selected architecture without exposing the host;
- completion is supported by independent executable evidence;
- runs are reproducible and attributable to architecture/model/runtime configuration;
- failures are normalized and diagnosable;
- new architectures reuse platform boundaries instead of duplicating infrastructure;
- deterministic and real-infrastructure regressions are separated and visible;
- security invariants remain enforced as the tool and topology surface grows.
