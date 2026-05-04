# Judge Prompts

Four prompt variants used in the AgentJudgeBench experiments.
Each file contains the raw prompt template with `{placeholder}` variables
that are filled by `SerializeFieldsPreProcessor` at runtime.

| File | Condition | Default score | Description |
|---|---|---|---|
| `judge_with_gt.txt` | C1 (with GT) | 1.0 | Main judging prompt. Receives ground-truth tool calls as a reference block. |
| `judge_no_gt.txt` | C1 (no GT) | 1.0 | Same structural instructions; omits EXPECTED TOOL CALLS block entirely. |
| `judge_no_gt_0.5default.txt` | C2 ablation | 0.5 | Like `judge_no_gt.txt` but instructs the judge to default to 0.5 when uncertain. Tests whether the 1.0 default inflates no-GT alignment. |
| `judge_freeform.txt` | C3 freeform | — | Minimal prompt with no structural instructions. Baseline for prompt ablation. |

## Variable placeholders

All prompts use these template variables (filled by `SerializeFieldsPreProcessor`):

- `{user_message}` — natural-language user query
- `{available_tools}` — JSON array of tool schemas
- `{generated_tool_calls}` — model-predicted tool call sequence
- `{expected_responses}` — ground-truth tool calls (**with-GT prompts only**)
