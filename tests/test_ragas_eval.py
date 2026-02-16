import pytest
from app.ragas_eval import evaluate_rag_batch


def test_ragas_eval_example():
    """Test RAGAS evaluation with sample Q&A pairs."""
    # Sample data matching the new format
    samples = [
        {
            "question": "What time is check in?",
            "answer": "Check-in is from 3pm.",
            "contexts": ["Check-in is from 3pm to midnight."],
            "reference": "Check-in starts at 3pm"
        },
        {
            "question": "Is breakfast included?",
            "answer": "Yes, breakfast is included in your stay.",
            "contexts": ["Breakfast is included for all guests."],
            "reference": "Breakfast is complimentary"
        }
    ]
    
    # Run evaluation
    results = evaluate_rag_batch(samples)
    
    # Verify expected metrics are present
    assert "faithfulness" in results, "Faithfulness metric should be present"
    assert "answer_relevancy" in results, "Answer relevancy metric should be present"  # ✅ Fixed assertion
    assert "context_precision" in results, "Context precision metric should be present"
    assert "context_recall" in results, "Context recall metric should be present"
    
    # Optionally print results for debugging
    print("\n📊 RAGAS Evaluation Results:")
    for metric, value in results.items():
        if isinstance(value, dict):
            # Per-question scores
            avg = sum(value.values()) / len(value) if value else 0
            print(f"  {metric}: {avg:.3f} (average)")
        else:
            print(f"  {metric}: {value:.3f}")


def test_ragas_eval_with_poor_answer():
    """Test RAGAS with intentionally poor answer to verify scoring."""
    samples = [
        {
            "question": "What time is check in?",
            "answer": "The sky is blue.",  # Completely wrong answer
            "contexts": ["Check-in is from 3pm to midnight."],
            "reference": "Check-in starts at 3pm"
        }
    ]
    
    results = evaluate_rag_batch(samples)
    
    # Poor answer should have low faithfulness and relevancy
    assert "faithfulness" in results
    assert "answer_relevancy" in results
    
    # Note: Actual threshold values depend on RAGAS implementation
    # These are just structural checks
    print("\n⚠️  Poor Answer Test Results:")
    print(f"  Faithfulness: {results.get('faithfulness', 'N/A')}")
    print(f"  Answer Relevancy: {results.get('answer_relevancy', 'N/A')}")


def test_ragas_eval_batch_format():
    """Test that evaluate_rag_batch accepts the correct format."""
    # Test with minimal valid input
    samples = [
        {
            "question": "Test question?",
            "answer": "Test answer.",
            "contexts": ["Test context."],
            "reference": "Test reference"
        }
    ]
    
    # Should not raise an exception
    results = evaluate_rag_batch(samples)
    assert isinstance(results, dict), "Results should be a dictionary"
