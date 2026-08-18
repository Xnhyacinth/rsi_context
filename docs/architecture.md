# Architecture

RSIBench-Context separates the system into three principals that communicate
through immutable, typed artifacts.

1. The researcher reads visible failures and edits only a policy workspace.
2. The context policy compiles document chunks into a provenance-preserving
   `ContextPack` under a hard budget.
3. The evaluator invokes a frozen reader and scorer outside the researcher
   process.

The policy is not an answer-producing agent. It may select span identifiers,
order them, request a registered compression transform, abstain, or request a
bounded reread. The current executable supports selection/compression/ordering/
abstention in `single_reader`; it rejects reread until the adaptive orchestrator
and its call ledger exist. Arbitrary answer strings, model configuration,
decoding flags, metrics, and dataset loaders are outside its capability surface.

## Trust boundaries

The visible evaluator may return item-level scores and gold evidence. The gate
returns only the pre-registered promotion signal. The sealed evaluator is a
separate service and is called once after code, policies, selection rules, and
analysis scripts are frozen.

The current development host cannot create an unprivileged network namespace.
Directory permissions and static policy audits are therefore sufficient only
for local smoke tests. Formal sealed runs require a different OS account, a
container-enabled worker, or a separate node with network and filesystem
isolation.

The development evaluator asks an evaluator-owned factory for a new policy
object for every item and replay. Object-identity checks are only smoke-test
guards: Python module, decorator, and closure state can survive object creation.
Formal gate and sealed evaluation must therefore load the artifact in a new
interpreter or worker for every item and replay. That process-isolated runner is
not implemented in this checkout. The researcher never supplies the factory.
Counterfactual generator objects likewise remain evaluator-side; only the
visible export may enter a researcher workspace.

## Reproducibility boundary

A run is identified by a hash over the model and tokenizer revisions, model
length, dataset revision, evaluator revision, policy hash, serving-profile
hash, semantic/free-text/chunk budgets, call budgets, split, track, and seed.
The canonical reader factory verifies the run against the registered serving
profile and model, then derives the model, output cap, model length, and seed
from that specification. A paper-scale runner must additionally emit a runtime
manifest with the GPU model, vLLM, CUDA, scheduler, shard assignment, batch
boundaries, and environment lock hash. That runtime manifest is not implemented
in this checkout.

Temperature zero and a seed are controls, not a determinism guarantee. Golden
validation uses offline inference, fixed request order, fixed workers, disabled
prefix caching and speculative decoding, and repeated evaluation of the same
artifact.

The endpoint adapter accepts allowlisted hosts only, disables environment
proxies and redirects, caps response bytes, and requires prompt/completion token
usage. These are transport controls, not a substitute for a sealed network.
