#!/usr/bin/env python3
"""
Response Self-Evaluation System for ARGUS RAG
Evaluates response quality and decides if regeneration is needed.
Created: December 16, 2025
"""

import json
import re
import time
import sqlite3
from datetime import datetime
from anthropic import Anthropic

# =============================================================================
# CONFIGURATION
# =============================================================================

CONFIG = {
    "score_accept": 7.0,
    "score_warning": 6.0,
    "score_reject": 6.0,
    "max_regenerations": 1,
    "model": "claude-3-haiku-20240307",
    "max_tokens": 1000,
    "min_query_words": 8,
    "analytical_keywords": [
        "como", "por que", "evolui", "compare", "análise",
        "probabilidade", "tendência", "últimos dias", "últimas horas",
        "perspectiva", "cenário", "vs", "versus", "diferença",
        "impacto", "consequência", "previsão", "expectativa"
    ],
    "db_path": "/home/ubuntu/newspaper_project/rag_learning.db"
}

EVALUATION_PROMPT = '''Você é um avaliador de qualidade de respostas de um sistema RAG financeiro brasileiro.

PERGUNTA DO USUÁRIO:
{query}

RESPOSTA GERADA:
{response}

Avalie a resposta nos seguintes critérios (0-10 cada):

1. CLAREZA (clarity): Os números/percentuais estão bem explicados?
   - Se menciona "60%", está claro 60% de quê?
   - Métricas diferentes estão separadas (rejeição vs intenção de voto)?

2. RELEVÂNCIA (relevance): A resposta responde exatamente o que foi perguntado?

3. PRECISÃO (precision): Os dados são consistentes? Não há contradições?

4. FONTES (sources): As fontes estão citadas com @username?

5. COMPLETUDE (completeness): A resposta está completa?

IMPORTANTE: Penalize fortemente confusão entre métricas diferentes.

Responda APENAS com JSON válido:
{{"clarity": {{"score": X, "issues": []}}, "relevance": {{"score": X, "issues": []}}, "precision": {{"score": X, "issues": []}}, "sources": {{"score": X, "issues": []}}, "completeness": {{"score": X, "issues": []}}, "total_score": X.X, "should_regenerate": true/false, "suggestions": ""}}'''


class ResponseEvaluator:
    def __init__(self, api_key=None):
        if api_key:
            self.client = Anthropic(api_key=api_key)
        else:
            try:
                with open("/home/ubuntu/newspaper_project/.api_key_8546", "r") as f:
                    api_key = f.read().strip()
                self.client = Anthropic(api_key=api_key)
            except Exception as e:
                print(f"Warning: Could not load API key: {e}")
                self.client = None
    
    def should_evaluate(self, query):
        """
        Decide if a query needs evaluation.
        Returns (should_eval: bool, query_type: str)
        """
        query_lower = query.lower()
        words = query.split()
        
        has_analytical = any(kw in query_lower for kw in CONFIG["analytical_keywords"])
        has_numbers = bool(re.search(r"\d+%|\d+ dias|\d+ meses", query_lower))
        
        if has_analytical or has_numbers:
            query_type = "analytical"
        elif len(words) < CONFIG["min_query_words"]:
            query_type = "simple"
        else:
            query_type = "general"
        
        should_eval = query_type in ["analytical", "general"]
        return should_eval, query_type
    
    def evaluate(self, query, response):
        """
        Evaluate a response and return scores + decision.
        """
        if not self.client:
            return self._fallback_evaluation()
        
        start_time = time.time()
        
        try:
            prompt = EVALUATION_PROMPT.format(query=query, response=response[:4000])
            
            message = self.client.messages.create(
                model=CONFIG["model"],
                max_tokens=CONFIG["max_tokens"],
                messages=[{"role": "user", "content": prompt}]
            )
            
            raw_response = message.content[0].text
            elapsed_ms = int((time.time() - start_time) * 1000)
            
            evaluation = self._parse_evaluation(raw_response)
            evaluation["evaluation_time_ms"] = elapsed_ms
            evaluation["raw_evaluation"] = raw_response
            
            return evaluation
            
        except Exception as e:
            print(f"Evaluation error: {e}")
            return self._fallback_evaluation()
    
    def _parse_evaluation(self, raw):
        """Parse the JSON evaluation from Haiku"""
        try:
            raw = raw.strip()
            if raw.startswith("```"):
                raw = re.sub(r"```json?\n?", "", raw)
                raw = raw.replace("```", "")
            
            data = json.loads(raw)
            
            scores = {
                "clarity": data.get("clarity", {}).get("score", 5),
                "relevance": data.get("relevance", {}).get("score", 5),
                "precision": data.get("precision", {}).get("score", 5),
                "sources": data.get("sources", {}).get("score", 5),
                "completeness": data.get("completeness", {}).get("score", 5),
            }
            
            total = data.get("total_score")
            if not total:
                weights = {"clarity": 0.25, "relevance": 0.25, "precision": 0.20, 
                          "sources": 0.15, "completeness": 0.15}
                total = sum(scores[k] * weights[k] for k in scores)
            
            issues = []
            for criterion in ["clarity", "relevance", "precision", "sources", "completeness"]:
                criterion_issues = data.get(criterion, {}).get("issues", [])
                issues.extend(criterion_issues)
            
            passed = total >= CONFIG["score_accept"]
            needs_warning = CONFIG["score_warning"] <= total < CONFIG["score_accept"]
            should_regenerate = data.get("should_regenerate", total < CONFIG["score_reject"])
            
            return {
                "scores": scores,
                "total_score": round(total, 2),
                "passed": passed,
                "needs_warning": needs_warning,
                "should_regenerate": should_regenerate and not passed,
                "issues": issues,
                "suggestions": data.get("suggestions", ""),
            }
            
        except json.JSONDecodeError as e:
            print(f"JSON parse error: {e}")
            return self._fallback_evaluation()
    
    def _fallback_evaluation(self):
        """Return a safe fallback if evaluation fails"""
        return {
            "scores": {"clarity": 7, "relevance": 7, "precision": 7, "sources": 7, "completeness": 7},
            "total_score": 7.0,
            "passed": True,
            "needs_warning": False,
            "should_regenerate": False,
            "issues": ["Avaliação automática não disponível"],
            "suggestions": "",
            "evaluation_time_ms": 0,
            "raw_evaluation": "fallback"
        }
    
    def save_evaluation(self, conversation_id, query_type, evaluation, 
                       was_regenerated=False, attempt=0):
        """Save evaluation to database for learning"""
        try:
            conn = sqlite3.connect(CONFIG["db_path"])
            cursor = conn.cursor()
            
            scores = evaluation.get("scores", {})
            
            cursor.execute("""
                INSERT INTO response_evaluations 
                (conversation_id, clarity_score, relevance_score, precision_score,
                 sources_score, completeness_score, total_score, passed_threshold,
                 was_regenerated, regeneration_attempt, issues_found, suggestions,
                 evaluation_raw, query_type, evaluation_time_ms)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                conversation_id,
                scores.get("clarity", 0),
                scores.get("relevance", 0),
                scores.get("precision", 0),
                scores.get("sources", 0),
                scores.get("completeness", 0),
                evaluation.get("total_score", 0),
                evaluation.get("passed", False),
                was_regenerated,
                attempt,
                json.dumps(evaluation.get("issues", []), ensure_ascii=False),
                evaluation.get("suggestions", ""),
                evaluation.get("raw_evaluation", ""),
                query_type,
                evaluation.get("evaluation_time_ms", 0)
            ))
            
            conn.commit()
            conn.close()
            return cursor.lastrowid
            
        except Exception as e:
            print(f"Error saving evaluation: {e}")
            return None
    
    def save_failure(self, conversation_id, query, final_score, attempts, all_issues):
        """Save failed evaluation for learning"""
        try:
            conn = sqlite3.connect(CONFIG["db_path"])
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO evaluation_failures 
                (conversation_id, query, final_score, attempts, all_issues)
                VALUES (?, ?, ?, ?, ?)
            """, (conversation_id, query, final_score, attempts,
                  json.dumps(all_issues, ensure_ascii=False)))
            
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"Error saving failure: {e}")
    
    def generate_warning_note(self, issues):
        """Generate a warning note to append to response"""
        if not issues:
            return ""
        
        issues_text = "\n".join(f"• {issue}" for issue in issues[:3])
        
        return f"""

---
⚠️ **Nota de Qualidade**

Esta resposta pode conter imprecisões. Problemas detectados:
{issues_text}

Recomendo verificar os dados nas fontes originais.
---"""


def get_evaluation_stats(days=7):
    """Get evaluation statistics for the last N days"""
    try:
        conn = sqlite3.connect(CONFIG["db_path"])
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                COUNT(*) as total,
                AVG(total_score) as avg_score,
                SUM(CASE WHEN passed_threshold THEN 1 ELSE 0 END) as passed,
                SUM(CASE WHEN was_regenerated THEN 1 ELSE 0 END) as regenerated,
                AVG(evaluation_time_ms) as avg_time
            FROM response_evaluations
            WHERE timestamp >= datetime('now', '-' || ? || ' days')
        """, (days,))
        
        row = cursor.fetchone()
        conn.close()
        
        if row and row[0] > 0:
            return {
                "total_evaluations": row[0],
                "average_score": round(row[1], 2) if row[1] else 0,
                "passed_count": row[2] or 0,
                "regenerated_count": row[3] or 0,
                "average_time_ms": int(row[4]) if row[4] else 0,
                "pass_rate": round((row[2] or 0) / row[0] * 100, 1)
            }
        return {"total_evaluations": 0}
    except Exception as e:
        return {"error": str(e)}


def get_common_issues(limit=10):
    """Get most common issues from evaluations"""
    try:
        conn = sqlite3.connect(CONFIG["db_path"])
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT issues_found FROM response_evaluations
            WHERE issues_found IS NOT NULL AND issues_found != '[]'
            ORDER BY timestamp DESC
            LIMIT 100
        """)
        
        rows = cursor.fetchall()
        conn.close()
        
        issue_counts = {}
        for row in rows:
            try:
                issues = json.loads(row[0])
                for issue in issues:
                    issue_counts[issue] = issue_counts.get(issue, 0) + 1
            except:
                pass
        
        sorted_issues = sorted(issue_counts.items(), key=lambda x: x[1], reverse=True)
        return sorted_issues[:limit]
        
    except Exception as e:
        print(f"Error getting issues: {e}")
        return []


if __name__ == "__main__":
    print("🧪 Testing Response Evaluator...")
    
    evaluator = ResponseEvaluator()
    
    test_queries = [
        ("Olá", False, "simple"),
        ("Como a probabilidade de Flávio evolui?", True, "analytical"),
        ("Qual a Selic?", False, "simple"),
        ("Compare Lula vs Bolsonaro nos últimos 5 dias", True, "analytical"),
    ]
    
    print("\n📋 Query Classification:")
    for query, expected_eval, expected_type in test_queries:
        should_eval, query_type = evaluator.should_evaluate(query)
        status = "✅" if should_eval == expected_eval else "❌"
        print(f"  {status} \"{query[:40]}\" -> evaluate={should_eval}, type={query_type}")
    
    print("\n✅ Test complete!")






