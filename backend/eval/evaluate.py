"""
eval/evaluate.py
RAGAS evaluation pipeline.

METRICS EXPLAINED:
  faithfulness      — Does the answer stay grounded in retrieved context?
                      Score 1.0 = every claim supported by a chunk
                      Score 0.5 = half the claims are hallucinated

  answer_relevancy  — Does the answer actually address the question?
                      Score 1.0 = perfectly addresses the question
                      Score 0.5 = partially off-topic

  context_precision — Are the retrieved chunks relevant to the question?
                      Score 1.0 = all retrieved chunks are useful
                      Score 0.5 = half the chunks are noise

  context_recall    — Were all necessary chunks retrieved?
                      Score 1.0 = found everything needed to answer
                      Score 0.5 = missed half the relevant passages

HOW TO USE:
  # Run baseline (first time)
  python -m eval.evaluate --tag baseline

  # After adding HyDE
  python -m eval.evaluate --tag with_hyde

  # After adding router
  python -m eval.evaluate --tag with_router

  Results saved to eval/results/<tag>.csv
  Compare runs to measure improvement.
"""
import sys
import json
import argparse
from pathlib import Path
from datetime import datetime
from loguru import logger

sys.path.insert(0, str(Path(__file__).parent.parent))

from datasets import Dataset
from ragas import evaluate
from ragas.metrics import faithfulness, answer_relevancy, context_precision, context_recall

from chain.rag_chain import answer
from retrieval.retriever import retrieve


def load_test_set(path: str = "eval/test_set.json") -> list[dict]:
    with open(path) as f:
        return json.load(f)


def run_evaluation(tag: str = "eval", skip_oos: bool = True) -> dict:
    """
    Run RAGAS evaluation on all test questions.

    Args:
        tag: Label for this run (used in filename)
        skip_oos: Skip out-of-scope questions (they have no valid retrieval)
    """
    test_set = load_test_set()

    if skip_oos:
        test_set = [q for q in test_set if q.get("ground_truth") != "OUT_OF_SCOPE"]
        logger.info(f"Running eval on {len(test_set)} questions (OOS excluded)")

    questions, answers_list, contexts, ground_truths = [], [], [], []

    for item in test_set:
        q = item["question"]
        logger.info(f"[{item['id']}] Evaluating: {q[:60]}...")

        try:
            result = answer(q)
            chunks = retrieve(q)
            questions.append(q)
            answers_list.append(result["answer"])
            contexts.append([c["content"] for c in chunks])
            ground_truths.append(item["ground_truth"])
        except Exception as e:
            logger.error(f"Failed on {item['id']}: {e}")
            continue

    dataset = Dataset.from_dict({
        "question": questions,
        "answer": answers_list,
        "contexts": contexts,
        "ground_truth": ground_truths,
    })

    logger.info("Running RAGAS metrics...")
    result = evaluate(
        dataset,
        metrics=[faithfulness, answer_relevancy, context_precision, context_recall],
    )

    # Save results
    Path("eval/results").mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"eval/results/{tag}_{timestamp}.csv"
    result.to_pandas().to_csv(filename, index=False)

    # Print summary
    logger.success(f"\n=== RAGAS Results [{tag}] ===")
    summary = {}
    for metric in ["faithfulness", "answer_relevancy", "context_precision", "context_recall"]:
        score = result[metric]
        summary[metric] = round(score, 3)
        logger.success(f"  {metric:25s}: {score:.3f}")

    logger.success(f"\nFull results saved to: {filename}")

    # Save summary for EVAL_HISTORY.md
    summary_file = "eval/results/summary.json"
    history = []
    if Path(summary_file).exists():
        with open(summary_file) as f:
            history = json.load(f)

    history.append({
        "tag": tag,
        "timestamp": timestamp,
        "n_questions": len(questions),
        **summary,
    })

    with open(summary_file, "w") as f:
        json.dump(history, f, indent=2)

    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--tag", type=str, default="eval", help="Label for this run (e.g. baseline, with_hyde)")
    parser.add_argument("--include-oos", action="store_true", help="Include out-of-scope questions")
    args = parser.parse_args()
    run_evaluation(tag=args.tag, skip_oos=not args.include_oos)
