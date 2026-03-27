# pyre-ignore-all-errors
import json
import logging
import sys
import os

# Ensure backend root is in PYTHONPATH for direct script execution
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from typing import List

# pyre-ignore[21]
from services.rag_service import process_chat
# pyre-ignore[21]
from mistralai import Mistral
# pyre-ignore[21]
from config import get_settings

settings = get_settings()
client = Mistral(api_key=settings.mistral_api_key)

logger = logging.getLogger("evaluator")
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter('%(levelname)s: %(message)s'))
logger.addHandler(handler)
logger.setLevel(logging.INFO)

def calculate_precision_at_k(retrieved_docs: List[dict], expected_docs: List[str], k: int = 3) -> float:
    """Calculates True Positives in top-k retrieved docs using normalized token substring matching."""
    # List comprehension completely bypasses the static index slicing inference issue in Pyre
    retrieved_top_k: List[dict] = [doc for i, doc in enumerate(retrieved_docs) if i < k]
    if not expected_docs or not retrieved_top_k:
        return 0.0
    
    matches_count: int = sum(
        1 for doc in retrieved_top_k
        if any(
            str(exp).strip().lower() in (str(doc.get("source_key", "")) + " " + str(doc.get("title", ""))).strip().lower()
            for exp in expected_docs
        )
    )
            
    return float(matches_count) / float(min(k, len(retrieved_top_k)))

def evaluate_answer_llm_as_judge(question: str, generated_answer: str, expected_answer: str) -> dict:
    """Uses LLM-as-a-judge (Mistral) to grade factuality and relevancy (0-5)."""
    prompt = f"""You are an objective legal evaluator.
Grade the GENERATED ANSWER against the EXPECTED ANSWER for the given QUESTION.
Consider factual accuracy, legal precision, and completeness. Provide a score from 0 to 5.

QUESTION: {question}
EXPECTED ANSWER: {expected_answer}
GENERATED ANSWER: {generated_answer}

Respond ONLY with a JSON object in this exact format: {{"score": <int>, "reason": "<string>"}}"""

    try:
        response = client.chat.complete(
            model=settings.mistral_chat_model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0
        )
        content = response.choices[0].message.content
        
        # Primitive boundary extraction in case the model wraps in markdown blocks
        start_idx = content.find("{")
        end_idx = content.rfind("}") + 1
        if start_idx != -1 and end_idx != 0:
            return json.loads(content[start_idx:end_idx])
            
        return {"score": 0, "reason": "Evaluator output mapping failure"}
    except Exception as e:
        logger.error(f"Failed to parse LLM judge response: {e}")
        return {"score": 0, "reason": f"Execution error: {str(e)}"}

def run_evaluation(dataset_path: str):
    if not os.path.exists(dataset_path):
        logger.error(f"Dataset not found at {dataset_path}")
        return

    with open(dataset_path, "r") as f:
        dataset = json.load(f)

    results: List[dict] = []

    logger.info(f"Starting evaluation on {len(dataset)} examples...")

    for i, item in enumerate(dataset):
        query = item["query"]
        expected_answer = item["expected_answer"]
        expected_docs = item["expected_docs"]
        
        logger.info(f"Evaluating [{i+1}/{len(dataset)}]: {query}")
        
        try:
            # Bypass cache for honest architectural latency and retrieval eval
            result, latency, _ = process_chat(str(query), history=[], filter_source=None, use_cache=False)
            
            # Metric 1: Retrieval Quality (Precision@3)
            precision = float(calculate_precision_at_k(result.get("sources", []), expected_docs, k=3))
            
            # Metric 2: Answer Quality (LLM Grade)
            judge_res = evaluate_answer_llm_as_judge(str(query), str(result.get("answer", "")), str(expected_answer))
            score_val = float(judge_res.get("score", 0.0))
            is_failure = 1 if (score_val <= 2.0 or precision == 0.0) else 0
                
            summary_item = {
                "id": str(item.get("id", f"query-{i}")),
                "precision@3": precision,
                "llm_score": score_val,
                "reason": str(judge_res.get("reason", "N/A")),
                "latency_ms": int(latency),
                "failure": is_failure
            }
            results.append(summary_item)
            logger.info(f"  -> Precision@3: {precision:.2f} | Score: {summary_item['llm_score']}/5 | Latency: {latency}ms")
            
        except Exception as e:
            logger.error(f"Evaluation pipeline failed for query '{query}': {e}")

    dataset_len = len(dataset) if dataset else 0
    if dataset_len > 0:
        total_p = sum(float(r.get("precision@3", 0.0)) for r in results)
        total_s = sum(float(r.get("llm_score", 0.0)) for r in results)
        total_f = sum(int(r.get("failure", 0)) for r in results)
        
        avg_precision = float(total_p) / float(dataset_len)
        avg_score = float(total_s) / float(dataset_len)
        failure_rate = (float(total_f) / float(dataset_len)) * 100.0
    else:
        avg_precision = 0.0
        avg_score = 0.0
        failure_rate = 0.0
    
    summary = {
        "metrics": {
            "total_examples": len(results),
            "average_precision_at_3": avg_precision,
            "average_llm_score": avg_score,
            "failure_rate_percent": failure_rate
        },
        "details": results
    }
    
    output_path = dataset_path.replace(".json", "_results.json")
    with open(output_path, "w") as f:
        json.dump(summary, f, indent=2)
    
    logger.info("========================================")
    logger.info("EVALUATION SUMMARY")
    logger.info(f"Total Examples Assessed: {len(results)}")
    logger.info(f"Average Retrieval Precision@3: {avg_precision:.3f}")
    logger.info(f"Average Generation LLM Score:  {avg_score:.2f} / 5.0")
    logger.info(f"Generation/Retrieval Failure Rate: {failure_rate:.1f}%")
    logger.info(f"Results explicitly saved to: {output_path}")
    logger.info("========================================")

if __name__ == "__main__":
    current_dir = os.path.dirname(os.path.abspath(__file__))
    dataset_file = os.path.join(current_dir, "eval_dataset.json")
    run_evaluation(dataset_file)
