# -LLM-evaluation-pipeline

## Overview
A Python-based evaluation pipeline for assessing LLM responses across three key dimensions:
1. **Response Relevance & Completeness**
2. **Hallucination / Factual Accuracy**
3. **Latency & Costs**

## Features
- ✅ Handles non-standard JSON (removes comments, trailing commas)
- ✅ Rigorous claim verification with numerical fact-checking
- ✅ Detects hallucinations by verifying facts against context
- ✅ Comprehensive metrics: grounding scores, completeness analysis, cost breakdown
- ✅ Command-line interface for flexible usage
- ✅ No heavy dependencies (only Python standard library)

## Requirements
- Python 3.7+
- No external packages required (uses only standard library)

## Installation
No installation needed! Just ensure you have Python 3.7 or higher:

```bash
python --version
```

## Usage

### Basic Usage
```bash
python LLM.py --chat <chat_file.json> --context <context_file.json>
```

### Examples

**Example 1: Evaluate sample conversation 01**
```bash
python LLM.py --chat sample-chat-conversation-01.json --context sample_context_vectors-01.json
```

**Example 2: Evaluate sample conversation 02 with custom output**
```bash
python LLM.py --chat sample-chat-conversation-02.json --context sample_context_vectors-02.json --out report_02.json
```

**Example 3: View help**
```bash
python LLM.py --help
```

## Command-Line Arguments

| Argument | Required | Description | Default |
|----------|----------|-------------|---------|
| `--chat` | Yes | Path to chat conversation JSON file | - |
| `--context` | Yes | Path to context vectors JSON file | - |
| `--out` | No | Output report filename | `evaluation_report.json` |

## Input File Format

### Chat Conversation JSON
```json
{
    "chat_id": 12345,
    "user_id": 67890,
    "conversation_turns": [
        {
            "turn": 1,
            "sender_id": 1,
            "role": "AI/Chatbot",
            "message": "Hello! How can I help?",
            "created_at": "2025-11-16T17:04:44.000000Z"
        }
    ]
}
```

### Context Vectors JSON
```json
{
    "status": "success",
    "data": {
        "vector_data": [...],
        "sources": {
            "final_response": ["Response text here"],
            "vectors_used": [123, 456],
            "vectors_info": [...]
        }
    }
}
```

## Output Report Structure

The evaluation generates a comprehensive JSON report with the following sections:

### 1. Response Relevance & Completeness
- Overall score and grounding metrics
- Completeness analysis (substantiality, specifics, keyword coverage)
- Context utilization statistics
- Citation analysis

### 2. Hallucination & Factual Accuracy
- Hallucination risk score and level
- Claim-by-claim verification
- Supported vs. unsupported claims
- Ground truth validation

### 3. Latency & Costs
- Response time analysis (seconds, milliseconds, categorization)
- Detailed cost breakdown (input/output tokens)
- Efficiency metrics (cost per word, tokens per word)

### 4. Overall Assessment
- Quality score
- Performance rating
- Cost efficiency rating
- Actionable recommendations

## Example Output

```json
{
    "evaluation_metadata": {...},
    "1_response_relevance_and_completeness": {
        "overall_score": 0.75,
        "grounding_score": 0.690,
        "completeness_analysis": {...}
    },
    "2_hallucination_and_factual_accuracy": {
        "hallucination_risk_score": 0.8,
        "risk_level": "High (>0.3)",
        "factual_accuracy_score": 0.2,
        "claim_analysis": {
            "total_claims_extracted": 5,
            "supported_claims": 1,
            "unsupported_claims": 4
        }
    },
    "3_latency_and_costs": {
        "latency_analysis": {
            "latency_seconds": 9.0,
            "latency_category": "Slow (5-10s)"
        },
        "cost_analysis": {
            "total_cost_usd": 0.045985
        }
    }
}
```

## Pipeline Architecture & Flow Diagram

### System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                   LLM EVALUATION PIPELINE                       │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
        ┌─────────────────────────────────────────┐
        │         INPUT PROCESSING                │
        └─────────────────────────────────────────┘
                 │                    │
                 │                    │
    ┌────────────▼──────────┐    ┌───▼───────────────┐
    │  Chat Conversation    │    │  Context Vectors  │
    │       JSON            │    │       JSON        │
    └────────────┬──────────┘    └───┬───────────────┘
                 │                    │
                 │  JSON Cleaning     │
                 │  • Comments        │
                 │  • Trailing commas │
                 │  • Malformations  │
                 │                    │
                 └────────┬───────────┘
                          │
                 ┌────────▼────────┐
                 │  TURN MATCHING  │
                 │  Module         │
                 └────────┬────────┘
                          │
          ┌───────────────┼───────────────┐
          │               │               │
    ┌─────▼─────┐  ┌──────▼──────┐  ┌────▼────┐
    │ RELEVANCE │  │ HALLUCINATION│ │ LATENCY │
    │ ANALYSIS  │  │   DETECTION  │ │  & COST │
    └─────┬─────┘  └──────┬───────┘ └────┬────┘
          │               │               │
          └───────────────┼───────────────┘
                          │
                 ┌────────▼────────┐
                 │  FINAL REPORT   │
                 │   GENERATION    │
                 └────────┬────────┘
                          │
                          ▼
                 evaluation_report.json
```

### Detailed Processing Flow

#### **Phase 1: Data Ingestion & Validation**

```
START
  │
  ├─► Load Chat JSON
  │     ├─ Remove comments (//)
  │     ├─ Fix trailing commas
  │     ├─ Fix malformed properties
  │     └─ Parse JSON
  │
  ├─► Load Context JSON
  │     ├─ Same cleaning steps
  │     └─ Parse JSON
  │
  ├─► Validate Data Structure
  │     ├─ Check for required fields
  │     ├─ Verify conversation_turns exists
  │     └─ Verify sources/final_response exists
  │
  └─► Continue to Phase 2
```

#### **Phase 2: Turn Matching**

```
Context Response (from context JSON)
  │
  ├─► Strategy 1: Substring Match
  │     ├─ Extract first 30 chars from final_response
  │     ├─ Search in all AI/Chatbot messages
  │     └─ Match found? ──► YES ──► Use this turn
  │                    └─► NO ──┐
  │                             │
  └─► Strategy 2: Jaccard Similarity (Fallback)
        ├─ Extract all words from context response
        ├─ For each AI message:
        │   ├─ Calculate word overlap (intersection/union)
        │   └─ Calculate similarity score 
        ├─ Find best match
        ├─ Score > 0.4? ──► YES ──► Use this turn
        │              └─► NO  ──► ERROR: Cannot match
        │
        └─► Continue to Phase 3 (if matched)
```

#### **Phase 3: Three-Pillar Analysis**

**3A. Relevance & Completeness Analysis**

```
AI Response + User Query + Context
  │
  ├─► Grounding Score Calculation
  │     ├─ Extract meaningful words (remove stop words)
  │     ├─ Calculate intersection with context
  │     └─ Score = overlap / response_words
  │
  ├─► Completeness Check
  │     ├─ Is response substantive? (>15 words)
  │     ├─ Has specific details? (numbers/prices)
  │     ├─ Keyword coverage from query
  │     └─ Combined score (0-1)
  │
  ├─► Context Utilization
  │     ├─ Count sources used
  │     ├─ Calculate coverage ratio
  │     └─ Extract citations/URLs
  │
  └─► Output: Relevance Metrics
```

**3B. Hallucination Detection**

```
AI Response
  │
  ├─► Extract Claims
  │     ├─ Split into sentences
  │     ├─ Filter out questions
  │     └─ Keep assertions (>20 chars)
  │
  ├─► For Each Claim:
  │     │
  │     ├─► Has Numbers/Prices?
  │     │     ├─ YES ──► Numerical Fact Check
  │     │     │           ├─ Extract all numbers
  │     │     │           ├─ Verify in context
  │     │     │           ├─ Extract prices (Rs./$/USD)
  │     │     │           ├─ Verify in context
  │     │     │           └─ Both match? ──► SUPPORTED
  │     │     │                          └─► UNSUPPORTED
  │     │     │
  │     │     └─ NO ──► Semantic Matching
  │     │               ├─ Extract 3-word phrases
  │     │               ├─ Check phrase matches in context
  │     │               ├─ Calculate word overlap
  │     │               └─ >70% overlap OR >50% phrases? 
  │     │                           ├─► YES: SUPPORTED
  │     │                           └─► NO: UNSUPPORTED
  │     │
  │     └─► Record Verification Result
  │           ├─ Supported: true/false
  │           ├─ Confidence score
  │           └─ Verification method used
  │
  ├─► Aggregate Results
  │     ├─ Count supported claims
  │     ├─ Count unsupported claims
  │     ├─ Hallucination Risk = unsupported / total
  │     └─ Factual Accuracy = 1 - risk
  │
  └─► Output: Hallucination Metrics
```

**3C. Latency & Cost Analysis**

```
User Turn + AI Turn + Context Vectors
  │
  ├─► Latency Calculation
  │     ├─ Parse user timestamp
  │     ├─ Parse AI timestamp
  │     ├─ Calculate delta (seconds)
  │     └─ Categorize:
  │           ├─ <2s  : Fast
  │           ├─ 2-5s : Normal
  │           ├─ 5-10s: Slow
  │           └─ >10s : Very Slow
  │
  ├─► Token Counting
  │     ├─ Count context tokens (from vectors_info)
  │     ├─ Estimate response tokens (chars / 4)
  │     └─ Calculate total
  │
  ├─► Cost Calculation
  │     ├─ Input cost = (context_tokens/1M) × $5
  │     ├─ Output cost = (response_tokens/1M) × $15
  │     ├─ Total cost = input + output
  │     └─ Efficiency metrics:
  │           ├─ Cost per word
  │           └─ Tokens per word
  │
  └─► Output: Performance & Cost Metrics
```

#### **Phase 4: Report Generation**

```
All Analysis Results
  │
  ├─► Calculate Overall Scores
  │     ├─ Quality = (relevance + accuracy) / 2
  │     ├─ Performance = based on latency
  │     └─ Cost Efficiency = based on total cost
  │
  ├─► Generate Recommendations
  │     ├─ Check thresholds:
  │     │   ├─ Relevance < 0.5? → Improve relevance
  │     │   ├─ Hallucination > 0.3? → Verify accuracy
  │     │   ├─ Latency > 10s? → Optimize speed
  │     │   └─ Cost > $0.1? → Reduce context size
  │     └─ Combine into actionable message
  │
  ├─► Structure JSON Report
  │     ├─ Metadata section
  │     ├─ Query/Response summary
  │     ├─ Three analysis sections
  │     └─ Overall assessment
  │
  └─► Write to File
        └─► evaluation_report.json

END
```

### Key Decision Points

| Stage | Decision | Criteria | Action |
|-------|----------|----------|--------|
| **Turn Matching** | Can match turn? | Substring OR Jaccard > 0.4 | Continue / Return error |
| **Claim Verification** | Has numbers? | Regex match for digits/prices | Numerical check / Semantic check |
| **Support Check** | Is claim supported? | Numbers verified AND phrases match | Mark SUPPORTED / UNSUPPORTED |
| **Risk Level** | Hallucination risk | % unsupported claims | High (>0.3) / Medium / Low |
| **Performance** | Response speed | Latency in seconds | Fast / Normal / Slow / Very Slow |
| **Cost Efficiency** | Total cost | $ per query | Efficient / Moderate / Expensive |

### Data Flow Example

For a typical evaluation:

```
Input Files:
  chat.json (2KB) + context.json (85KB)
        ↓
  JSON Cleaning (removes ~10 malformations)
        ↓
  Turn Matching (finds Turn #10 via substring)
        ↓
  ┌──────────────┬──────────────┬───────────────┐
  │              │              │               │
  Relevance      Hallucination  Latency & Cost
  Analysis       Detection      Analysis
  │              │              │               │
  Score: 0.75    Risk: 0.8      Time: 9s
  10 sources     4/5 unsupported Cost: $0.046
  │              │              │               │
  └──────────────┴──────────────┴───────────────┘
                      ↓
              Overall Assessment
                      ↓
              evaluation_report.json (7KB)
```

## How It Works

### Hallucination Detection
The pipeline uses a rigorous verification process:
1. **Extracts claims** from AI responses (sentences making assertions)
2. **Identifies numerical facts** (prices, numbers, dates)
3. **Verifies each claim** against the provided context:
   - For claims with numbers: Checks if exact numbers exist in context
   - For general claims: Uses phrase-level matching (3+ word sequences)
4. **Calculates risk scores** based on supported vs. unsupported claims

### Completeness Assessment
Analyzes if responses fully answer user queries by checking:
- Response substantiality (length, detail)
- Presence of specific information (numbers, facts)
- Keyword coverage from the original query
- Question type matching

### Cost Calculation
Estimates API costs based on token usage:
- Input tokens: Context vectors used
- Output tokens: AI response length
- Configurable pricing model ($5/1M input, $15/1M output by default)

## Customization

You can modify pricing constants in the `LLMEvaluationPipeline` class:

```python
class LLMEvaluationPipeline:
    def __init__(self, chat_file_path: str, context_file_path: str):
        # Update these values to match your API pricing
        self.INPUT_TOKEN_PRICE_PER_MILLION = 5.0   # $5 per 1M tokens
        self.OUTPUT_TOKEN_PRICE_PER_MILLION = 15.0  # $15 per 1M tokens
```

## Troubleshooting

**Problem: FileNotFoundError**
- Solution: Ensure file paths are correct and files exist
- Use absolute paths if needed

**Problem: JSON parsing errors**
- Solution: The script auto-cleans common JSON issues, but verify your JSON is valid

**Problem: No claims detected**
- Solution: Ensure AI responses contain complete sentences (not just acknowledgments)

## Performance

- **Speed**: Processes typical evaluations in <1 second
- **Memory**: Minimal footprint (~10-20MB for standard conversations)
- **Scale**: Can handle conversations with 100+ turns

## License

This evaluation pipeline is designed for educational and assessment purposes.

## Support

For issues or questions about the pipeline, refer to the code comments or the inline help:
```bash
python LLM.py --help
```

## Version History

- **v1.0** (2025-12-12): Initial release with comprehensive evaluation metrics

