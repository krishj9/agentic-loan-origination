# Evaluation Harness

Deterministic scenario generator and evaluation framework for the loan origination system.

## Overview

The evaluation harness provides:

- **Synthetic scenario generation** for deterministic, reproducible test cases
- **Structured metadata** with correlation IDs, seeds, and expected outcomes
- **Multiple scenario types**: document parsing, risk scoring, compliance, and end-to-end flows
- **Schema conformance** using canonical Pydantic models from `/shared`
- **Structured JSON logging** with correlation IDs for traceability

## Phase 6 Implementation Status

### ✅ P6-T1: Scenario Generator (COMPLETE)

Implemented synthetic scenario generator producing structured test cases for:

- **Document parsing scenarios**: Paystub and bank statement extraction/normalization
- **Risk scoring scenarios**: Deterministic risk evaluation across PRIME/NEAR_PRIME/SUBPRIME bands
- **Compliance evaluation scenarios**: Rule-based compliance with flag triggering
- **End-to-end scenarios**: Complete loan origination flows (golden cases)

All scenarios are:
- Deterministic (same seed → same output)
- Reproducible across runs
- Typed using canonical schemas
- Include metadata with correlation IDs, expected outcomes, and evaluation dimensions

### ✅ P6-T2: Scenario Metadata & Utilities (COMPLETE)

Implemented scenario metadata infrastructure:

- **ScenarioMetadata**: Unique IDs, seeds, descriptions, expected outcomes, evaluation dimensions
- **Seed control**: Deterministic randomization with context-based seed derivation
- **Structured logging**: JSON logging with correlation IDs
- **CLI tool**: Generate scenarios from command line

### ✅ P6-T3: Replay Engine (COMPLETE)

Implemented deterministic replay engine:

- **ReplayEngine**: Executes scenarios step-by-step through LangGraph supervisor
- **Execution tracing**: Captures state transitions at each node
- **Tool invocation tracking**: Records all tool inputs/outputs
- **State snapshots**: Before/after snapshots for each node execution

### ✅ P6-T4: Trace Serialization (COMPLETE)

Implemented structured trace serialization:

- **ExecutionTrace**: Complete execution record with metadata
- **NodeExecution**: Per-node execution details with state snapshots
- **ToolInvocation**: Tool call tracking with timing
- **TraceSerializer**: JSON serialization with custom type handling

### ✅ P6-T5: Batch Runner (COMPLETE)

Implemented batch execution and validation:

- **BatchRunner**: Execute multiple scenarios sequentially or in parallel
- **Result validation**: Compare actual vs expected outcomes
- **Report generation**: Summary statistics and detailed results
- **Directory loading**: Load and execute scenarios from filesystem

## Quick Start

### Install Dependencies

```bash
uv sync
```

### Generate Scenarios

Generate 10 scenarios of each type:

```bash
uv run python -m evaluation.cli.generate_scenarios \
  --output-dir ./scenarios \
  --count 10 \
  --base-seed 42
```

### Run Tests

```bash
uv run pytest tests/scenarios/ -v
```

## Architecture

### Scenario Types

#### 1. Document Parsing Scenarios (`DocumentParsingScenario`)

Tests document extraction and normalization:

```python
from evaluation.scenarios import ScenarioGenerator
from shared.schemas import DocumentType

generator = ScenarioGenerator(base_seed=42)
scenario = generator.generate_document_parsing_scenario(
    scenario_id="parse_paystub_001",
    document_type=DocumentType.PAYSTUB,
    seed=42
)
```

**Output structure:**
- Metadata with scenario ID, seed, expected outcomes
- Document type (PAYSTUB or BANK_STATEMENT)
- Expected extracted fields (PayStubFields or BankStatementFields)

#### 2. Risk Scoring Scenarios (`RiskScoringScenario`)

Tests deterministic risk engine evaluation:

```python
from shared.schemas import RiskProfile

scenario = generator.generate_risk_scoring_scenario(
    scenario_id="risk_prime_001",
    risk_profile=RiskProfile.PRIME,
    seed=42
)
```

**Output structure:**
- RiskRequest with applicant data
- Expected RiskResponse with credit score, tradelines, flags
- Risk profile, score range, and explainability fields

#### 3. Compliance Scenarios (`ComplianceScenario`)

Tests rule-based compliance evaluation:

```python
scenario = generator.generate_compliance_scenario(
    scenario_id="compliance_refer_001",
    seed=42,
    trigger_flags=True  # Generate data that triggers compliance flags
)
```

**Output structure:**
- Application financial data
- Expected compliance result with recommended action

#### 4. End-to-End Scenarios (`EndToEndScenario`)

Tests complete loan origination flows:

```python
from shared.schemas import DecisionOutcome

scenario = generator.generate_end_to_end_scenario(
    scenario_id="e2e_approve_001",
    risk_profile=RiskProfile.PRIME,
    expected_outcome=DecisionOutcome.APPROVE,
    seed=42
)
```

**Output structure:**
- Canonical application with applicant data
- Document fixtures (references to synthetic PDFs)
- Expected risk profile, compliance action, decision outcome

### Seed Control

All scenario generation is deterministic:

```python
from evaluation.scenarios.seed_control import SeedContext, seeded_context

# Create a seed context
ctx = SeedContext(base_seed=42, scenario_id="test_001", component="risk")

# Use seeded randomization
with seeded_context(ctx) as rng:
    value = rng.randint(1, 100)  # Deterministic based on context
```

**Key properties:**
- Same seed + scenario ID → identical output
- Component name allows multiple independent random streams per scenario
- No global random state pollution

### Structured Logging

All operations emit structured JSON logs with correlation IDs:

```python
from evaluation.log import configure_logging, get_logger, set_scenario_id

configure_logging(level="INFO")
logger = get_logger(__name__)

set_scenario_id("risk_prime_001")
logger.info("Processing scenario", extra={"credit_score": 750})
```

**Log format:**
```json
{
  "timestamp": "2026-06-23T12:37:47.236589Z",
  "level": "INFO",
  "logger": "evaluation.scenarios.generator",
  "message": "Generated risk scoring scenario",
  "scenario_id": "risk_prime_001",
  "credit_score": 750,
  "source": {
    "file": "generator.py",
    "line": 215,
    "function": "generate_risk_scoring_scenario"
  }
}
```

## Scenario Metadata Structure

Every scenario includes comprehensive metadata:

```python
{
  "scenarioId": "risk_prime_001",           # Unique identifier
  "scenarioType": "RISK_SCORING",           # Type of scenario
  "version": "1.0.0",                       # Schema version
  "seed": 42,                                # Deterministic seed
  "description": "PRIME risk profile...",   # Human-readable description
  "createdAt": "2026-06-23T10:00:00Z",      # Generation timestamp
  "expectedOutcomes": {                     # Expected results for validation
    "riskProfile": "PRIME",
    "creditScoreRange": [720, 800]
  },
  "dimensions": {                           # Evaluation dimensions
    "primaryDimensions": ["ACCURACY", "DETERMINISM"],
    "secondaryDimensions": ["EXPLAINABILITY"]
  },
  "tags": ["golden-case", "prime"],        # Classification tags
  "requirementRefs": ["REQ-5.3", "DESIGN-7"]  # Traceability
}
```

### Evaluation Dimensions

Scenarios are tagged with evaluation dimensions they test:

- **ACCURACY**: Correctness of outputs
- **DETERMINISM**: Reproducibility across runs
- **EXPLAINABILITY**: Quality of rationale/explanation
- **COMPLETENESS**: All required fields populated
- **SCHEMA_CONFORMANCE**: Valid against canonical schemas
- **BUSINESS_RULE_ADHERENCE**: Follows configured rules
- **EDGE_CASE_HANDLING**: Behavior at boundaries
- **ERROR_HANDLING**: Graceful degradation

## Directory Structure

```
evaluation/
├── src/evaluation/
│   ├── scenarios/
│   │   ├── __init__.py
│   │   ├── generator.py          # Main scenario generator
│   │   ├── metadata.py            # Metadata models
│   │   ├── models.py              # Scenario type models
│   │   └── seed_control.py        # Deterministic randomization
│   ├── replay/
│   │   ├── __init__.py
│   │   ├── engine.py              # Replay engine with tracing
│   │   ├── trace.py               # Trace models and serialization
│   │   └── runner.py              # Batch execution runner
│   ├── cli/
│   │   ├── __init__.py
│   │   └── generate_scenarios.py  # CLI tool
│   └── log.py                     # Structured JSON logging
├── tests/
│   ├── scenarios/
│   │   ├── test_generator.py      # Generator tests (30 tests)
│   │   └── test_seed_control.py   # Seed control tests (15 tests)
│   └── replay/
│       ├── test_engine.py         # Replay engine tests (12 tests)
│       ├── test_runner.py         # Batch runner tests (13 tests)
│       └── test_trace.py          # Trace models tests (17 tests)
├── pyproject.toml
└── README.md
```

## Testing

The evaluation harness includes comprehensive tests:

```bash
# Run all tests
uv run pytest tests/scenarios/ -v

# Run with coverage
uv run pytest tests/scenarios/ --cov=evaluation.scenarios --cov-report=term-missing

# Run specific test class
uv run pytest tests/scenarios/test_generator.py::TestRiskScoringScenarios -v
```

**Test coverage:**
- 45 tests across seed control and scenario generation
- Tests for determinism (same seed → same output)
- Tests for schema conformance
- Tests for metadata completeness
- Tests for all scenario types and risk profiles

## Usage Examples

### Generate PRIME Risk Scenario

```python
from evaluation.scenarios import ScenarioGenerator
from shared.schemas import RiskProfile

generator = ScenarioGenerator(base_seed=42)
scenario = generator.generate_risk_scoring_scenario(
    scenario_id="risk_prime_high_income",
    risk_profile=RiskProfile.PRIME,
    seed=100
)

# Save to file
from pathlib import Path
generator.save_scenario(scenario, Path("scenarios/risk_prime_high_income.json"))
```

### Generate End-to-End Golden Case

```python
from shared.schemas import DecisionOutcome

scenario = generator.generate_end_to_end_scenario(
    scenario_id="golden_approve_001",
    risk_profile=RiskProfile.PRIME,
    expected_outcome=DecisionOutcome.APPROVE,
    seed=500
)

# Verify expected outcomes
assert scenario.expected_decision_outcome == "APPROVE"
assert scenario.expected_risk_profile == RiskProfile.PRIME
assert scenario.canonical_application.annual_income >= 80000
```

### Execute Scenario with Replay Engine

```python
from evaluation.replay import ReplayEngine

# Initialize replay engine with tracing
engine = ReplayEngine(enable_tracing=True)

# Execute scenario
trace = engine.execute_scenario(scenario)

# Examine execution
print(f"Status: {trace.status}")
print(f"Nodes executed: {trace.nodes_executed_count}")
print(f"Duration: {trace.duration_ms}ms")

# Access node-level details
for node_exec in trace.node_executions:
    print(f"Node: {node_exec.node_name}")
    print(f"  State fields before: {node_exec.state_before_count}")
    print(f"  State fields after: {node_exec.state_after_count}")
    print(f"  Tools invoked: {len(node_exec.tool_invocations)}")
```

### Save Execution Trace

```python
from evaluation.replay import TraceSerializer

# Serialize to JSON file
TraceSerializer.save(trace, Path("traces/execution_trace.json"))

# Or get JSON string
json_str = TraceSerializer.to_json(trace, indent=2)
```

### Batch Execution with Validation

```python
from evaluation.replay import BatchRunner

# Initialize batch runner
runner = BatchRunner(max_workers=4)  # Parallel execution

# Load scenarios
scenarios = [
    generator.generate_end_to_end_scenario(
        scenario_id=f"batch_{i}",
        risk_profile=RiskProfile.PRIME,
        expected_outcome=DecisionOutcome.APPROVE,
        seed=1000 + i,
    )
    for i in range(10)
]

# Execute with validation
results = runner.run_scenarios(scenarios, validate=True)

# Generate report
report = runner.generate_report(results, output_path=Path("reports/batch_report.json"))

print(f"Total: {report['summary']['total_scenarios']}")
print(f"Passed: {report['summary']['validation_passed']}")
print(f"Success rate: {report['summary']['success_rate']}%")
```

### Load and Execute from Directory

```python
from pathlib import Path

# Execute all scenarios in a directory
results = runner.run_from_directory(
    scenarios_dir=Path("scenarios/end_to_end"),
    output_dir=Path("traces"),
    validate=True,
)

# Check validation results
for result in results:
    if not result.validation_passed:
        print(f"{result.scenario_id}: {result.validation_errors}")
```

### Batch Generation

```python
from shared.schemas import RiskProfile

profiles = [RiskProfile.PRIME, RiskProfile.NEAR_PRIME, RiskProfile.SUBPRIME]

for i, profile in enumerate(profiles * 10):  # 30 scenarios
    scenario = generator.generate_risk_scoring_scenario(
        scenario_id=f"risk_{profile.value.lower()}_{i:03d}",
        risk_profile=profile,
        seed=2000 + i
    )
    generator.save_scenario(
        scenario,
        Path(f"scenarios/risk/{profile.value.lower()}_{i:03d}.json")
    )
```

## Integration with System

Scenarios integrate with the loan origination system pipeline:

1. **Document Parsing**: Scenarios provide expected extraction outputs for validation
2. **Risk Engine**: Scenarios include expected risk responses for determinism testing
3. **Compliance**: Scenarios test rule-based evaluation with known flag triggers
4. **End-to-End**: Golden cases for replay harness (P6-T4) to test full pipeline

## Next Steps

### Phase 6 Remaining Tasks

- **P6-T3**: Golden-case catalog (build from end-to-end scenarios)
- **P6-T4**: Replay harness (submit scenarios through API, compare results)
- **P6-T5**: Evaluation metrics (accuracy, FP/FN reporting)
- **P6-T6**: Drift detection (compare outcomes against config baseline)
- **P6-T7**: Unit tests (already complete for scenario generator)
- **P6-T8**: Integration tests (graph + real tool wiring)
- **P6-T9**: End-to-end tests (UI → decision flow)
- **P6-T10**: CloudWatch dashboard finalization

## Design Alignment

Implements requirements from:

- **Implementation Plan Phase 6** (P6-T1, P6-T2)
- **Requirements §6**: Document parsing test cases
- **Requirements §7.2**: Golden-case replay
- **Design §10.2**: Evaluation harness architecture
- **Design §10.3**: Metrics and drift detection

All scenarios use canonical schemas from `/shared/schemas` ensuring consistency with the production pipeline.
