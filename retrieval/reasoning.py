# reasoning.py
"""
Multi-step reasoning chain for sophisticated code question answering.
"""

import streamlit as st
from typing import List, Dict

from cache import get_llm, get_vectorstore
from graph import get_graph_aware_retriever
from retrieval import multi_hop_retrieve, infer_metadata_filters_from_query


class MultiStepReasoningChain:
    """Multi-step reasoning chain for sophisticated code question answering."""
    
    def __init__(self, llm, vectorstore, graph_retriever=None, kg=None, call_graph=None):
        self.llm = llm
        self.vectorstore = vectorstore
        self.graph_retriever = graph_retriever
        self.kg = kg or {}
        self.call_graph = call_graph or {}
    
    def step1_classify_intent(self, query: str) -> dict:
        """Classify the intent of the user's question."""
        prompt_text = f"""
Analyze this question about a codebase and classify its intent:

Question: "{query}"

Classify the intent as one of:
1. code_search - user wants to find specific code/function
2. implementation - user wants to understand how something works
3. documentation - user wants explanation/docs
4. fix - user wants to debug or fix something
5. design - user wants architecture/design info
6. test - user wants test-related code

Respond in this exact format:
INTENT: [type]
CONFIDENCE: [0.0-1.0]
KEYWORDS: [comma-separated]
REASONING: [brief explanation]
"""
        try:
            response = self.llm.invoke(prompt_text)
            text = response.content.strip()
            
            intent_type = "code_search"
            confidence = 0.5
            keywords = []
            
            for line in text.split("\n"):
                if line.startswith("INTENT:"):
                    intent_type = line.replace("INTENT:", "").strip().lower()
                elif line.startswith("CONFIDENCE:"):
                    try:
                        confidence = float(line.replace("CONFIDENCE:", "").strip())
                    except:
                        confidence = 0.5
                elif line.startswith("KEYWORDS:"):
                    keywords = [k.strip() for k in line.replace("KEYWORDS:", "").split(",")]
            
            return {
                "intent_type": intent_type,
                "confidence": confidence,
                "reasoning": text,
                "relevant_keywords": keywords,
            }
        except Exception as e:
            print(f"⚠️ Intent classification failed: {e}")
            return {
                "intent_type": "code_search",
                "confidence": 0.0,
                "reasoning": str(e),
                "relevant_keywords": [],
            }
    
    def step2_identify_symbols(self, query: str, intent: dict) -> dict:
        """Identify symbols (functions, classes, variables, etc.) in query."""
        prompt_text = f"""
Extract all code symbols (function, class, variable, module names) from this query:

Query: "{query}"
Intent: {intent.get("intent_type", "unknown")}

List ALL symbols you find, including:
- Exact names mentioned
- Likely related symbols based on naming patterns
- Common abbreviations or variations

Format as:
MENTIONED: [symbol1, symbol2, ...]
INFERRED: [related_symbol1, related_symbol2, ...]
TYPES: [symbol1:type, symbol2:type, ...]

Be specific and include all reasonable interpretations.
"""
        try:
            response = self.llm.invoke(prompt_text)
            text = response.content.strip()
            
            mentioned = []
            inferred = []
            symbol_types = {}
            
            for line in text.split("\n"):
                if line.startswith("MENTIONED:"):
                    mentioned = [
                        s.strip()
                        for s in line.replace("MENTIONED:", "")
                        .strip("[]")
                        .split(",")
                        if s.strip()
                    ]
                elif line.startswith("INFERRED:"):
                    inferred = [
                        s.strip()
                        for s in line.replace("INFERRED:", "")
                        .strip("[]")
                        .split(",")
                        if s.strip()
                    ]
                elif line.startswith("TYPES:"):
                    for pair in line.replace("TYPES:", "").strip("[]").split(","):
                        if ":" in pair:
                            sym, typ = pair.split(":", 1)
                            symbol_types[sym.strip()] = typ.strip()
            
            return {
                "mentioned_symbols": mentioned,
                "inferred_symbols": inferred,
                "symbol_types": symbol_types,
                "confidence_scores": {s: 0.8 for s in mentioned + inferred},
            }
        except Exception as e:
            print(f"⚠️ Symbol identification failed: {e}")
            return {
                "mentioned_symbols": [],
                "inferred_symbols": [],
                "symbol_types": {},
                "confidence_scores": {},
            }
    
    def step3_retrieve_with_graph_walk(self, query: str, symbols: dict, intent: dict) -> list:
        """Retrieve code using initial vector search + graph walking."""
        print("🔎 Step 3: Retrieving with graph walk...")
        inferred_filters = infer_metadata_filters_from_query(query)
        base_docs = multi_hop_retrieve(
            query, inferred_filters, hops=2, base_k=16, top_k=8
        )
        
        retrieved = list(base_docs)
        
        if self.graph_retriever:
            try:
                for doc in list(base_docs)[:5]:
                    expanded = self.graph_retriever.retrieve_graph_aware(
                        doc, include_related=True
                    )
                    for expanded_doc in expanded:
                        if expanded_doc not in retrieved:
                            retrieved.append(expanded_doc)
            except Exception as e:
                print(f"⚠️ Graph-aware expansion failed: {e}")
        
        for symbol in (
            symbols.get("mentioned_symbols", [])
            + symbols.get("inferred_symbols", [])
        )[:5]:
            try:
                sym_docs = self.vectorstore.similarity_search(symbol, k=3)
                for doc in sym_docs:
                    if doc not in retrieved:
                        retrieved.append(doc)
            except Exception:
                pass
        
        print(f"✅ Retrieved {len(retrieved)} chunks total")
        return retrieved
    
    def step4_retrieve_sibling_context(self, retrieved_docs: list) -> list:
        """Enhance with sibling context (related code in same class/file)."""
        enhanced = list(retrieved_docs)
        
        if not self.graph_retriever:
            return enhanced
        
        try:
            for doc in list(retrieved_docs)[:8]:
                meta = doc.metadata or {}
                node_type = meta.get("node_type", "")
                
                if node_type == "method":
                    related = self.graph_retriever.retrieve_graph_aware(
                        doc, include_related=True
                    )
                    for rel_doc in related:
                        if rel_doc not in enhanced:
                            enhanced.append(rel_doc)
                
                parent_class = meta.get("parent_class")
                if parent_class:
                    class_docs = self.vectorstore.similarity_search(
                        parent_class, k=2
                    )
                    for class_doc in class_docs:
                        if class_doc not in enhanced:
                            enhanced.append(class_doc)
        except Exception as e:
            print(f"⚠️ Sibling context retrieval failed: {e}")
        
        print(f"📚 Enhanced to {len(enhanced)} chunks with sibling context")
        return enhanced
    
    def step5_synthesize_answer(
        self,
        query: str,
        intent: dict,
        symbols: dict,
        retrieved_docs: list,
        max_context_chars: int = 12000
    ) -> str:
        """Synthesize final answer using all context."""
        context_parts = []
        total_chars = 0
        
        for doc in retrieved_docs[:15]:
            if total_chars >= max_context_chars:
                break
            
            meta = doc.metadata or {}
            file_path = meta.get("path", "unknown")
            symbol = meta.get("symbol_name", "")
            content = doc.page_content
            
            chunk_info = f"[{file_path}:{symbol}]\n{content}\n"
            if total_chars + len(chunk_info) <= max_context_chars:
                context_parts.append(chunk_info)
                total_chars += len(chunk_info)
        
        context = "\n---\n".join(context_parts)
        
        prompt_text = f"""
Based on the following codebase context, answer this question:

QUESTION: {query}

INTENT: {intent.get("intent_type", "unknown")}
IDENTIFIED SYMBOLS: {', '.join(symbols.get("mentioned_symbols", []))}

RELEVANT CODE:
{context}

Provide a comprehensive answer that:
1. Directly addresses the question
2. Explains relevant code sections
3. References file paths and function names
4. Suggests related code if relevant
5. Is clear and concise

Answer:
"""
        try:
            response = self.llm.invoke(prompt_text)
            return response.content.strip()
        except Exception as e:
            print(f"⚠️ Answer synthesis failed: {e}")
            return f"Error generating answer: {e}"
    
    def reason(self, query: str, enable_graph_walk: bool = True) -> dict:
        """Execute full multi-step reasoning chain."""
        reasoning_trace = []
        
        reasoning_trace.append("Step 1: Intent Classification")
        intent = self.step1_classify_intent(query)
        
        reasoning_trace.append("Step 2: Symbol Identification")
        symbols = self.step2_identify_symbols(query, intent)
        
        reasoning_trace.append("Step 3: Graph-Aware Retrieval")
        retrieved = self.step3_retrieve_with_graph_walk(query, symbols, intent)
        
        reasoning_trace.append("Step 4: Sibling Context")
        enhanced = self.step4_retrieve_sibling_context(retrieved)
        
        reasoning_trace.append("Step 5: Answer Synthesis")
        answer = self.step5_synthesize_answer(query, intent, symbols, enhanced)
        
        return {
            "question": query,
            "intent": intent,
            "symbols": symbols,
            "retrieved_docs": retrieved,
            "enhanced_docs": enhanced,
            "answer": answer,
            "reasoning_trace": reasoning_trace,
        }


@st.cache_resource(show_spinner=False)
def get_reasoning_chain(repo_name: str):  # 🔁 CHANGED
    """Initialize multi-step reasoning chain."""
    try:
        llm = get_llm()
        vectorstore = get_vectorstore(repo_name)  # 🔁 CHANGED
        graph_retriever = get_graph_aware_retriever(repo_name)  # 🔁 CHANGED
        
        import cache as cache_module
        kg = cache_module.load_knowledge_graph_cached(repo_name)  # 🔁 CHANGED
        call_graph = cache_module.load_call_graph_cached(repo_name)  # 🔁 CHANGED
        
        chain = MultiStepReasoningChain(
            llm=llm,
            vectorstore=vectorstore,
            graph_retriever=graph_retriever,
            kg=kg,
            call_graph=call_graph
        )
        print(f"✅ Multi-step reasoning chain initialized for {repo_name}")
        return chain
    except Exception as e:
        print(f"⚠️ Failed to initialize reasoning chain: {e}")
        return None
