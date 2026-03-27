# pyre-ignore-all-errors
#!/usr/bin/env python3
import sys
import os
import argparse

# Embed project root logic so CLI runs directly gracefully
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from services.rag_service import process_chat

def main():
    parser = argparse.ArgumentParser(
        description="Clausio Intelligence CLI — RAG Engine Runner",
        epilog="Queries the Clausio RAG service directly, bypassing FastAPI server."
    )
    parser.add_argument("query", type=str, help="Legal question to evaluate against the RAG backend.")
    parser.add_argument("--source", type=str, choices=["eu_ai_act", "rgpd_fr"], help="Optional filter: Target index subset.", default=None)
    parser.add_argument("--no-cache", action="store_true", help="Disable caching locally.")
    
    args = parser.parse_args()
    
    print("\n--------------------------------------------------------------")
    print(f"[QUERY]: {args.query}")
    if args.source:
        print(f"[SOURCE]: {args.source}")
    print("--------------------------------------------------------------")
    print("\nExecuting Pipeline (Retrieving Vectors & Running LLM)...")
    
    try:
        result, latency, cached = process_chat(
            question=args.query, 
            history=[], 
            filter_source=args.source, 
            use_cache=not args.no_cache
        )
        
        print("\n\n[ANSWER]:")
        print(f"{result['answer']}\n")
        
        print("--------------------------------------------------------------")
        print(f"[METADATA]:")
        print(f"  - System Route:   {result['query_type']}")
        print(f"  - Cached:         {cached}")
        print(f"  - Pipeline Time:  {latency}ms")
        print(f"  - LLM Confidence: [{result['confidence']['level']}] (Score: {result['confidence']['score']})")
        if result['contradiction']['has_contradiction']:
            print(f"  - Contradiction:  DETECTED! ({result['contradiction']['explanation']})")
        print(f"  - Sources Used:   {result['chunks_used']} chunks")
        
        for i, src in enumerate(result['sources'], 1):
            print(f"      {i}. {src['title']} (Page {src['page']} | Vector Match: {src['similarity']})")
    
    except Exception as e:
        print(f"\n[FATAL ERROR]: RAG Execution definitively failed: {e}")

if __name__ == "__main__":
    main()
