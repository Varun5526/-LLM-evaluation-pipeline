import json
import datetime
from typing import Dict, List, Any, Tuple
import re
import argparse
import sys

class LLMEvaluationPipeline:
    def __init__(self, chat_file_path: str, context_file_path: str):
        self.chat_data = self._load_json(chat_file_path)
        self.context_data = self._load_json(context_file_path)
        
        # Pricing constants (example values based on typical API costs)
        self.INPUT_TOKEN_PRICE_PER_MILLION = 5.0     # $5 per 1M tokens
        self.OUTPUT_TOKEN_PRICE_PER_MILLION = 15.0   # $15 per 1M tokens

    def _load_json(self, file_path: str) -> Any:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Clean non-standard JSON (comments and trailing commas)
            content = re.sub(r'^\s*//.*', '', content, flags=re.MULTILINE)
            content = re.sub(r',(\s*[}\]])', r'\1', content)
            
            # Fix malformed patterns:
            # 1. "id": 35761,ot-to-treat", -> "id": 35761,
            # Pattern: number followed by comma then junk text with quote
            content = re.sub(r'(\d+),([a-zA-Z0-9_\-/\\]+)"', r'\1', content)
            
            # 2. "id": 38488,/book/chapter18", -> "id": 38488, "source_url": "/book/chapter18",
            # Pattern: number, comma, slash (URL without property name)
            content = re.sub(r'("id"\s*:\s*\d+),\s*(/[^"]+)"', r'\1, "source_url": "\2"', content)
            
            # 3. Fix standalone text after commas (corrupted property names)
            # Pattern: comma, text without quotes, then quote (missing property name)
            content = re.sub(r',\s*([a-zA-Z][a-zA-Z0-9_\-]*)"\s*:', r'', content)
            
            data = json.loads(content, strict=False)
            print(f"✓ Loaded {file_path}")
            return data
        except json.JSONDecodeError as e:
            print(f"✗ JSON Error in {file_path}")
            print(f"   Line {e.lineno}, Column {e.colno}: {e.msg}")
            return {}
        except Exception as e:
            print(f"✗ Error loading {file_path}: {e}")
            return {}

    def _parse_timestamp(self, timestamp_str: str) -> datetime.datetime:
        try:
            return datetime.datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
        except ValueError:
            return datetime.datetime.now()

    def _extract_claims(self, text: str) -> List[str]:
        """Extract factual claims from text (sentences that make assertions)"""
        # Split by sentence boundaries
        sentences = re.split(r'[.!?]+', text)
        claims = []
        for sent in sentences:
            sent = sent.strip()
            # Filter out very short sentences and questions
            if len(sent) > 20 and '?' not in sent:
                claims.append(sent)
        return claims

    def _verify_claim_in_context(self, claim: str, context: str) -> Dict[str, Any]:
        """Verify if a claim is supported by the context with rigorous fact-checking"""
        claim_lower = claim.lower()
        context_lower = context.lower()
        
        # Extract numerical facts from claim (prices, numbers, percentages)
        claim_numbers = re.findall(r'\d+(?:,\d{3})*(?:\.\d+)?', claim)
        claim_prices = re.findall(r'(?:rs\.?|rupees|\$|usd?)\s*\d+(?:,\d{3})*', claim_lower)
        
        # Check if claim contains specific factual elements
        has_numerical_facts = len(claim_numbers) > 0 or len(claim_prices) > 0
        
        # For claims with numbers/prices, verify those specific facts appear in context
        if has_numerical_facts:
            numbers_verified = all(num in context for num in claim_numbers)
            prices_verified = all(
                any(price_part in context_lower for price_part in price.split())
                for price in claim_prices
            )
            
            # If claim contains specific numbers/prices that aren't in context, it's unsupported
            if not (numbers_verified and prices_verified):
                return {
                    "supported": False,
                    "confidence": 0.0,
                    "overlap_ratio": 0.0,
                    "claim": claim[:100] + "..." if len(claim) > 100 else claim,
                    "reason": "Specific numerical facts not found in context"
                }
        
        # Extract key phrases (3+ word sequences)
        claim_words = claim_lower.split()
        key_phrases = []
        for i in range(len(claim_words) - 2):
            phrase = ' '.join(claim_words[i:i+3])
            # Skip phrases that are all stop words
            if not all(w in {'the', 'is', 'are', 'was', 'were', 'at', 'in', 'on', 'to', 'of', 'a', 'an', 'and', 'or', 'but'} for w in phrase.split()):
                key_phrases.append(phrase)
        
        # Check if any key phrases from the claim appear in context
        phrase_matches = sum(1 for phrase in key_phrases if phrase in context_lower)
        phrase_match_ratio = phrase_matches / len(key_phrases) if key_phrases else 0
        
        # Word-level overlap analysis
        claim_word_set = set(re.findall(r'\w+', claim_lower))
        context_word_set = set(re.findall(r'\w+', context_lower))
        
        # Remove stop words
        stop_words = {'the', 'is', 'are', 'was', 'were', 'be', 'been', 'being', 
                     'at', 'which', 'on', 'and', 'a', 'an', 'to', 'of', 'in', 
                     'for', 'with', 'it', 'this', 'that', 'by', 'as', 'from',
                     'we', 'you', 'they', 'them', 'their', 'our', 'your', 'can', 'will'}
        
        meaningful_claim = claim_word_set - stop_words
        meaningful_context = context_word_set - stop_words
        
        if not meaningful_claim:
            return {
                "supported": False,
                "confidence": 0.0,
                "overlap_ratio": 0.0,
                "claim": claim[:100] + "..." if len(claim) > 100 else claim,
                "reason": "Claim is too generic"
            }
        
        overlap = meaningful_claim.intersection(meaningful_context)
        word_overlap_ratio = len(overlap) / len(meaningful_claim)
        
        # Stricter verification logic:
        # - If claim has numbers/prices: numerical facts must match + high phrase overlap
        # - Otherwise: require both high word overlap AND phrase matches
        
        if has_numerical_facts:
            # For factual claims with numbers, require 80% word overlap AND phrase matches
            is_supported = word_overlap_ratio > 0.8 and phrase_match_ratio > 0.3
            confidence = (word_overlap_ratio * 0.6) + (phrase_match_ratio * 0.4)
        else:
            # For general claims, require 70% word overlap OR 50% phrase matches
            is_supported = word_overlap_ratio > 0.7 or phrase_match_ratio > 0.5
            confidence = max(word_overlap_ratio, phrase_match_ratio)
        
        return {
            "supported": is_supported,
            "confidence": round(confidence, 3),
            "overlap_ratio": round(word_overlap_ratio, 3),
            "phrase_match_ratio": round(phrase_match_ratio, 3),
            "claim": claim[:100] + "..." if len(claim) > 100 else claim,
            "verification_method": "numerical_fact_check" if has_numerical_facts else "semantic_matching"
        }

    def _calculate_grounding_score(self, response_text: str, context_text: str) -> float:
        """Calculate overall grounding score based on word overlap"""
        response_words = set(re.findall(r'\w+', response_text.lower()))
        context_words = set(re.findall(r'\w+', context_text.lower()))
        
        if not response_words:
            return 0.0
            
        common_words = response_words.intersection(context_words)
        stop_words = {'the', 'is', 'at', 'which', 'on', 'and', 'a', 'an', 'to', 'of', 'in', 'for', 'with', 'it', 'this', 'that'}
        meaningful_common = common_words - stop_words
        meaningful_response = response_words - stop_words
        
        if not meaningful_response:
            return 0.0
            
        return len(meaningful_common) / len(meaningful_response)

    def _assess_completeness(self, user_query: str, ai_response: str, context_text: str) -> Dict[str, Any]:
        """Assess if the response completely answers the user query"""
        # Extract key question words from user query
        query_lower = user_query.lower()
        
        # Identify question type
        question_words = ['what', 'where', 'when', 'who', 'why', 'how', 'which', 'can', 'do', 'does', 'is', 'are']
        detected_questions = [qw for qw in question_words if qw in query_lower.split()[:5]]
        
        # Check if response is substantive (not just acknowledgment)
        is_substantive = len(ai_response.split()) > 15
        
        # Check if response contains specific details (numbers, names, etc.)
        has_specifics = bool(re.search(r'\d+|Rs\.|USD|\$|rupees|dollars', ai_response))
        
        # Calculate how many query keywords appear in response
        query_keywords = set(re.findall(r'\w+', query_lower)) - {'the', 'is', 'can', 'you', 'i', 'a', 'an', 'to', 'of', 'in', 'for'}
        response_keywords = set(re.findall(r'\w+', ai_response.lower()))
        
        keyword_coverage = 0.0
        if query_keywords:
            keyword_coverage = len(query_keywords.intersection(response_keywords)) / len(query_keywords)
        
        completeness_score = (
            (0.3 if is_substantive else 0.0) +
            (0.3 if has_specifics else 0.0) +
            (0.4 * keyword_coverage)
        )
        
        return {
            "completeness_score": round(completeness_score, 2),
            "is_substantive": is_substantive,
            "has_specific_details": has_specifics,
            "keyword_coverage": round(keyword_coverage, 2),
            "question_type": detected_questions[0] if detected_questions else "statement",
            "assessment": "Complete" if completeness_score > 0.7 else "Partial" if completeness_score > 0.4 else "Incomplete"
        }

    def _extract_citations(self, response_text: str) -> List[str]:
        """Extract URLs and citations from response"""
        # Find URLs in markdown format [text](url) or plain URLs
        urls = re.findall(r'\[([^\]]+)\]\(([^)]+)\)', response_text)
        plain_urls = re.findall(r'https?://[^\s\)]+', response_text)
        
        citations = [url[1] for url in urls] + plain_urls
        return list(set(citations))  # Remove duplicates

    def _match_turn(self) -> Tuple[int, Dict, Dict]:
        """Find and return the matched turn index and turn data"""
        context_response_parts = self.context_data.get('data', {}).get('sources', {}).get('final_response', [])
        if isinstance(context_response_parts, list):
            context_response_text = " ".join(context_response_parts)
        else:
            context_response_text = str(context_response_parts)
            context_response_parts = [context_response_text]

        turns = self.chat_data.get('conversation_turns', [])
        matched_turn_index = -1
        
        # Strategy 1: Substring match
        for i, turn in enumerate(turns):
            if turn.get('role') == 'AI/Chatbot':
                msg = turn.get('message', '')
                if context_response_parts:
                    part_to_match = context_response_parts[0].strip()[:30] 
                    if part_to_match in msg:
                        matched_turn_index = i
                        break
        
        # Strategy 2: Jaccard Similarity fallback
        if matched_turn_index == -1:
            best_jaccard = 0.0
            best_idx = -1
            context_words = set(re.findall(r'\w+', context_response_text.lower()))
            
            for i, turn in enumerate(turns):
                if turn.get('role') == 'AI/Chatbot':
                    msg = turn.get('message', '')
                    msg_words = set(re.findall(r'\w+', msg.lower()))
                    
                    if context_words and msg_words:
                        intersection = context_words.intersection(msg_words)
                        union = context_words.union(msg_words)
                        jaccard = len(intersection) / len(union)
                        
                        if jaccard > best_jaccard:
                            best_jaccard = jaccard
                            best_idx = i
            
            if best_jaccard > 0.4:  # Lower threshold for fallback
                matched_turn_index = best_idx

        if matched_turn_index == -1:
            raise ValueError("Could not match Context JSON to a specific Chat Turn.")

        ai_turn = turns[matched_turn_index]
        user_turn = turns[matched_turn_index - 1] if matched_turn_index > 0 else {}
        
        return matched_turn_index, ai_turn, user_turn

    def evaluate(self) -> Dict[str, Any]:
        """Main evaluation function that performs comprehensive analysis"""
        
        print("\n" + "="*60)
        print("LLM RESPONSE EVALUATION PIPELINE")
        print("="*60)
        
        # Match the turn
        try:
            turn_idx, ai_turn, user_turn = self._match_turn()
            print(f"✓ Matched conversation turn #{turn_idx}")
        except ValueError as e:
            print(f"✗ {str(e)}")
            return {"error": str(e)}
        
        # Extract data
        user_message = user_turn.get('message', '') if user_turn else ''
        ai_message = ai_turn.get('message', '')
        
        # Get context data
        vector_data = self.context_data.get('data', {}).get('vector_data', [])
        vectors_info = self.context_data.get('data', {}).get('sources', {}).get('vectors_info', [])
        used_vector_ids = self.context_data.get('data', {}).get('sources', {}).get('vectors_used', [])
        
        # Aggregate context text
        relevant_context_text = ""
        context_sources = []
        for vec in vector_data:
            if not used_vector_ids or vec.get('id') in used_vector_ids:
                relevant_context_text += vec.get('text', '') + " "
                context_sources.append({
                    "id": vec.get('id'),
                    "source_url": vec.get('source_url', 'N/A'),
                    "text_length": len(vec.get('text', '')),
                    "tokens": vec.get('tokens', 0)
                })
        
        # ==================== SECTION 1: RESPONSE RELEVANCE & COMPLETENESS ====================
        print("\n[1/3] Analyzing Response Relevance & Completeness...")
        
        grounding_score = self._calculate_grounding_score(ai_message, relevant_context_text)
        completeness = self._assess_completeness(user_message, ai_message, relevant_context_text)
        citations = self._extract_citations(ai_message)
        
        # Calculate context coverage (how much of context was used)
        context_words = set(re.findall(r'\w+', relevant_context_text.lower()))
        response_words = set(re.findall(r'\w+', ai_message.lower()))
        context_coverage = len(response_words.intersection(context_words)) / len(context_words) if context_words else 0
        
        relevance_completeness = {
            "overall_score": round((grounding_score + completeness['completeness_score']) / 2, 2),
            "grounding_score": round(grounding_score, 3),
            "grounding_interpretation": "High (>0.7)" if grounding_score > 0.7 else "Medium (0.4-0.7)" if grounding_score > 0.4 else "Low (<0.4)",
            "completeness_analysis": completeness,
            "context_utilization": {
                "total_context_sources": len(context_sources),
                "sources_used": len(used_vector_ids) if used_vector_ids else len(context_sources),
                "context_coverage_ratio": round(context_coverage, 3),
                "context_sources_detail": context_sources[:5]  # Top 5 sources
            },
            "citations": {
                "count": len(citations),
                "urls": citations
            },
            "response_characteristics": {
                "length_chars": len(ai_message),
                "length_words": len(ai_message.split()),
                "has_urls": len(citations) > 0,
                "has_numbers": bool(re.search(r'\d+', ai_message))
            }
        }
        
        # ==================== SECTION 2: HALLUCINATION / FACTUAL ACCURACY ====================
        print("[2/3] Analyzing Hallucination & Factual Accuracy...")
        
        # Extract and verify claims
        claims = self._extract_claims(ai_message)
        claim_verifications = []
        
        for claim in claims[:10]:  # Verify up to 10 claims
            verification = self._verify_claim_in_context(claim, relevant_context_text)
            claim_verifications.append(verification)
        
        # Calculate hallucination metrics
        if claim_verifications:
            supported_claims = sum(1 for cv in claim_verifications if cv['supported'])
            hallucination_rate = 1 - (supported_claims / len(claim_verifications))
            avg_claim_confidence = sum(cv['confidence'] for cv in claim_verifications) / len(claim_verifications)
        else:
            hallucination_rate = 0.0
            avg_claim_confidence = 1.0
        
        # Check for manual evaluation note (ground truth)
        manual_note = ai_turn.get('evaluation_note', None)
        has_known_hallucination = manual_note and 'hallucination' in manual_note.lower()
        
        hallucination_analysis = {
            "hallucination_risk_score": round(hallucination_rate, 3),
            "risk_level": "High (>0.3)" if hallucination_rate > 0.3 else "Medium (0.1-0.3)" if hallucination_rate > 0.1 else "Low (<0.1)",
            "factual_accuracy_score": round(1 - hallucination_rate, 3),
            "claim_analysis": {
                "total_claims_extracted": len(claim_verifications),
                "supported_claims": sum(1 for cv in claim_verifications if cv['supported']),
                "unsupported_claims": sum(1 for cv in claim_verifications if not cv['supported']),
                "average_claim_confidence": round(avg_claim_confidence, 3),
                "claim_details": claim_verifications
            },
            "grounding_check": {
                "is_grounded": grounding_score > 0.5,
                "grounding_score": round(grounding_score, 3),
                "interpretation": "Response is well-grounded in provided context" if grounding_score > 0.6 else "Response may contain ungrounded information"
            },
            "ground_truth_validation": {
                "manual_evaluation_available": manual_note is not None,
                "manual_evaluation_note": manual_note,
                "known_hallucination_detected": has_known_hallucination
            }
        }
        
        # ==================== SECTION 3: LATENCY & COSTS ====================
        print("[3/3] Analyzing Latency & Costs...")
        
        # Latency calculation
        if user_turn and 'created_at' in user_turn and 'created_at' in ai_turn:
            user_time = self._parse_timestamp(user_turn['created_at'])
            ai_time = self._parse_timestamp(ai_turn['created_at'])
            latency_seconds = (ai_time - user_time).total_seconds()
            
            latency_info = {
                "latency_seconds": round(latency_seconds, 2),
                "latency_milliseconds": round(latency_seconds * 1000, 0),
                "latency_category": "Fast (<2s)" if latency_seconds < 2 else "Normal (2-5s)" if latency_seconds < 5 else "Slow (5-10s)" if latency_seconds < 10 else "Very Slow (>10s)",
                "user_query_timestamp": user_turn['created_at'],
                "ai_response_timestamp": ai_turn['created_at']
            }
        else:
            latency_info = {
                "latency_seconds": None,
                "error": "Timestamp information not available"
            }
        
        # Token and cost calculation
        total_context_tokens = sum(v.get('tokens_count', 0) for v in vectors_info)
        response_tokens = len(ai_message) // 4  # Heuristic: 1 token ≈ 4 chars
        total_tokens = total_context_tokens + response_tokens
        
        input_cost = (total_context_tokens / 1_000_000) * self.INPUT_TOKEN_PRICE_PER_MILLION
        output_cost = (response_tokens / 1_000_000) * self.OUTPUT_TOKEN_PRICE_PER_MILLION
        total_cost = input_cost + output_cost
        
        cost_analysis = {
            "total_cost_usd": round(total_cost, 6),
            "cost_breakdown": {
                "input_cost_usd": round(input_cost, 6),
                "output_cost_usd": round(output_cost, 6)
            },
            "token_usage": {
                "total_tokens": total_tokens,
                "input_tokens": total_context_tokens,
                "output_tokens": response_tokens,
                "input_percentage": round((total_context_tokens / total_tokens * 100) if total_tokens > 0 else 0, 1),
                "output_percentage": round((response_tokens / total_tokens * 100) if total_tokens > 0 else 0, 1)
            },
            "pricing_model": {
                "input_token_price_per_1m": f"${self.INPUT_TOKEN_PRICE_PER_MILLION}",
                "output_token_price_per_1m": f"${self.OUTPUT_TOKEN_PRICE_PER_MILLION}"
            },
            "efficiency_metrics": {
                "cost_per_word": round(total_cost / len(ai_message.split()) if ai_message.split() else 0, 6),
                "tokens_per_word": round(response_tokens / len(ai_message.split()) if ai_message.split() else 0, 2)
            }
        }
        
        # ==================== FINAL REPORT ====================
        print("\n✓ Evaluation Complete!\n")
        
        final_report = {
            "evaluation_metadata": {
                "evaluation_timestamp": datetime.datetime.now().isoformat(),
                "chat_id": self.chat_data.get('chat_id', 'N/A'),
                "user_id": self.chat_data.get('user_id', 'N/A'),
                "turn_number": turn_idx,
                "evaluator_version": "1.0"
            },
            "query_response_summary": {
                "user_query": user_message,
                "ai_response": ai_message,
                "response_length": len(ai_message),
                "turn_id": ai_turn.get('turn', 'N/A')
            },
            "1_response_relevance_and_completeness": relevance_completeness,
            "2_hallucination_and_factual_accuracy": hallucination_analysis,
            "3_latency_and_costs": {
                "latency_analysis": latency_info,
                "cost_analysis": cost_analysis
            },
            "overall_assessment": {
                "quality_score": round((relevance_completeness['overall_score'] + hallucination_analysis['factual_accuracy_score']) / 2, 3),
                "performance_score": "GOOD" if latency_info.get('latency_seconds', 999) < 5 else "MODERATE" if latency_info.get('latency_seconds', 999) < 10 else "POOR",
                "cost_efficiency": "EFFICIENT" if total_cost < 0.001 else "MODERATE" if total_cost < 0.01 else "EXPENSIVE",
                "recommendation": self._generate_recommendation(
                    relevance_completeness['overall_score'],
                    hallucination_analysis['hallucination_risk_score'],
                    latency_info.get('latency_seconds', 999),
                    total_cost
                )
            }
        }
        
        return final_report

    def _generate_recommendation(self, relevance_score: float, hallucination_risk: float, 
                                 latency: float, cost: float) -> str:
        """Generate actionable recommendations based on metrics"""
        issues = []
        
        if relevance_score < 0.5:
            issues.append("Improve response relevance and completeness")
        if hallucination_risk > 0.3:
            issues.append("High hallucination risk detected - verify factual accuracy")
        if latency > 10:
            issues.append("Optimize response time (currently >10s)")
        if cost > 0.1:
            issues.append("Consider cost optimization strategies")
        
        if not issues:
            return "Response quality is good across all metrics. No immediate action required."
        else:
            return "Action recommended: " + "; ".join(issues)


def main():
    """Main execution function with Command Line Arguments"""
    parser = argparse.ArgumentParser(
        description="LLM Evaluation Pipeline - Evaluate AI responses for relevance, hallucination, latency, and cost",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python LLM.py --chat sample-chat-conversation-01.json --context sample_context_vectors-01.json
  python LLM.py --chat conv.json --context ctx.json --out my_report.json
        """
    )
    
    # Arguments allow the user to specify files from the command line
    parser.add_argument("--chat", required=True, help="Path to the chat conversation JSON file")
    parser.add_argument("--context", required=True, help="Path to the context vectors JSON file")
    parser.add_argument("--out", default="evaluation_report.json", help="Path to save the output report (default: evaluation_report.json)")
    
    args = parser.parse_args()
    
    print(f"\n📊 LLM Evaluation Pipeline")
    print(f"Chat File:    {args.chat}")
    print(f"Context File: {args.context}\n")
    
    # Check if files exist before running
    try:
        with open(args.chat, 'r', encoding='utf-8'): 
            pass
        with open(args.context, 'r', encoding='utf-8'): 
            pass
    except FileNotFoundError as e:
        print(f"❌ Error: Could not find file. {e}")
        sys.exit(1)

    # Run evaluation
    try:
        pipeline = LLMEvaluationPipeline(args.chat, args.context)
        results = pipeline.evaluate()
    except Exception as e:
        print(f"❌ Error during evaluation: {e}")
        sys.exit(1)
    
    # Save results
    try:
        with open(args.out, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=4, ensure_ascii=False)
        print(f"📄 Full report saved to: {args.out}")
    except Exception as e:
        print(f"❌ Error saving report: {e}")
        sys.exit(1)

    print(f"\n{'='*60}")
    print(f"SUMMARY")
    print(f"{'='*60}")
    
    if 'overall_assessment' in results:
        oa = results['overall_assessment']
        print(f"Quality Score:   {oa.get('quality_score', 'N/A')}")
        print(f"Performance:     {oa.get('performance_score', 'N/A')}")
        print(f"Cost Efficiency: {oa.get('cost_efficiency', 'N/A')}")
        print(f"\n💡 {oa.get('recommendation', '')}")
    
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
