# cache.py
"""
Cached resource loading and initialization.
All expensive operations are cached to improve performance.
"""

import os
import json
import traceback
import streamlit as st
from langchain_groq import ChatGroq
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings

from ingestion.ingest import VECTOR_DIR, CALLGRAPH_PATH
from query_understanding import QueryUnderstanding
from unified_retrieval import UnifiedRetriever

try:
    from .graph_rag import create_graph_rag_retriever
    from .graph_traversal import load_knowledge_graph
except ImportError:
    from graph_rag import create_graph_rag_retriever
    from graph_traversal import load_knowledge_graph

EMBED_MODEL = "mixedbread-ai/mxbai-embed-large-v1"


@st.cache_resource(show_spinner=False)
def load_knowledge_graph_cached():
    """Load knowledge graph from disk."""
    kg_path = os.path.join(os.path.dirname(CALLGRAPH_PATH), "knowledge_graph.json")
    if os.path.exists(kg_path):
        try:
            with open(kg_path, "r", encoding="utf-8") as f:
                kg = json.load(f)
            return kg
        except Exception as e:
            print(f"⚠️ Failed to load knowledge graph: {e}")
            return {}
    return {}


@st.cache_resource(show_spinner=False)
def load_graph_traversal_cached():
    """Load knowledge graph and create traversal engine."""
    kg_path = os.path.join(os.path.dirname(CALLGRAPH_PATH), "knowledge_graph.json")
    if os.path.exists(kg_path):
        try:
            graph = load_knowledge_graph(kg_path)
            return graph
        except Exception as e:
            print(f"⚠️ Failed to load graph traversal: {e}")
            return None
    return None


@st.cache_resource(show_spinner=False)
def load_symbol_table_cached():
    """Load symbol table from disk."""
    st_path = os.path.join(os.path.dirname(CALLGRAPH_PATH), "symbol_table.json")
    if os.path.exists(st_path):
        try:
            with open(st_path, "r", encoding="utf-8") as f:
                st_data = json.load(f)
            return st_data
        except Exception as e:
            print(f"⚠️ Failed to load symbol table: {e}")
            return {}
    return {}


@st.cache_resource(show_spinner=False)
def load_dataflow_data_cached():
    """Load data flow analysis from disk."""
    df_path = os.path.join(os.path.dirname(CALLGRAPH_PATH), "dataflow_analysis.json")
    if os.path.exists(df_path):
        try:
            with open(df_path, "r", encoding="utf-8") as f:
                df_data = json.load(f)
            return df_data
        except Exception as e:
            print(f"⚠️ Failed to load dataflow analysis: {e}")
            return {}
    return {}


@st.cache_resource(show_spinner=False)
def load_call_graph_cached():
    """Load call graph from disk."""
    if os.path.exists(CALLGRAPH_PATH):
        try:
            with open(CALLGRAPH_PATH, "r", encoding="utf-8") as f:
                cg_data = json.load(f)
            return cg_data
        except Exception as e:
            print(f"⚠️ Failed to load call graph: {e}")
            return {}
    return {}


@st.cache_resource(show_spinner=False)
def get_embeddings():
    """Get embedding model."""
    return HuggingFaceEmbeddings(model_name=EMBED_MODEL)


@st.cache_resource(show_spinner=False)
def get_vectorstore():
    """Load FAISS vectorstore."""
    embeddings = get_embeddings()
    return FAISS.load_local(VECTOR_DIR, embeddings, allow_dangerous_deserialization=True)


@st.cache_resource(show_spinner=False)
def get_llm():
    """Get LLM instance."""
    return ChatGroq(model="llama-3.1-8b-instant", temperature=0.2)


@st.cache_resource(show_spinner=False)
def get_graph_rag_retriever():
    """Create Graph-RAG retriever with knowledge graph integration."""
    try:
        # Step 1: Get vectorstore
        print("[Graph-RAG] Step 1: Loading vectorstore...")
        vectorstore = get_vectorstore()
        print(f"[Graph-RAG] ✓ Vectorstore loaded")
        
        # Step 2: Check knowledge graph path
        print("[Graph-RAG] Step 2: Checking knowledge graph...")
        kg_path = os.path.join(os.path.dirname(CALLGRAPH_PATH), "knowledge_graph.json")
        print(f"[Graph-RAG] Knowledge graph path: {kg_path}")
        
        if not os.path.exists(kg_path):
            print(f"[Graph-RAG] ⚠️ Knowledge graph not found at {kg_path}")
            print(f"[Graph-RAG] Available files in {os.path.dirname(kg_path)}:")
            if os.path.exists(os.path.dirname(kg_path)):
                for f in os.listdir(os.path.dirname(kg_path)):
                    print(f"    - {f}")
            return None
        print(f"[Graph-RAG] ✓ Knowledge graph exists")
        
        # Step 3: Get all documents from vectorstore
        print("[Graph-RAG] Step 3: Extracting documents from vectorstore...")
        if not hasattr(vectorstore, 'docstore') or not hasattr(vectorstore.docstore, '_dict'):
            print(f"[Graph-RAG] ⚠️ Vectorstore structure unexpected: {type(vectorstore.docstore)}")
            return None
        all_documents = list(vectorstore.docstore._dict.values())
        print(f"[Graph-RAG] ✓ Extracted {len(all_documents)} documents")
        
        # Step 4: Create retriever
        print("[Graph-RAG] Step 4: Creating Graph-RAG retriever...")
        retriever = create_graph_rag_retriever(vectorstore, kg_path, all_documents)
        print(f"[Graph-RAG] ✓ Graph-RAG retriever created successfully")
        return retriever
    except Exception as e:
        print(f"[Graph-RAG] ❌ Failed to create Graph-RAG retriever: {e}")
        traceback.print_exc()
        return None

def get_query_understanding():
    """Initialize query understanding system with knowledge graph."""
    kg = load_knowledge_graph_cached()
    return QueryUnderstanding(knowledge_graph=kg)


@st.cache_resource(show_spinner=False)
def get_unified_retriever():
    """Initialize unified retriever with all components."""
    try:
        vectorstore = get_vectorstore()
        
        symbol_table_path = os.path.join(os.path.dirname(CALLGRAPH_PATH), "symbol_table.json")
        dataflow_path = os.path.join(os.path.dirname(CALLGRAPH_PATH), "dataflow_analysis.json")
        call_graph_path = CALLGRAPH_PATH
        
        # Load JSON data
        symbol_table_data = {}
        if os.path.exists(symbol_table_path):
            with open(symbol_table_path, "r", encoding="utf-8") as f:
                symbol_table_data = json.load(f)
        
        dataflow_data = {}
        if os.path.exists(dataflow_path):
            with open(dataflow_path, "r", encoding="utf-8") as f:
                dataflow_data = json.load(f)
        
        call_graph_data = {}
        if os.path.exists(call_graph_path):
            with open(call_graph_path, "r", encoding="utf-8") as f:
                call_graph_data = json.load(f)
        
        # Get all documents from vectorstore
        all_documents = list(vectorstore.docstore._dict.values())
        
        retriever = UnifiedRetriever(
            vectorstore=vectorstore,
            symbol_table_data=symbol_table_data,
            dataflow_data=dataflow_data,
            call_graph_data=call_graph_data,
            all_documents=all_documents
        )
        return retriever
    except Exception as e:
        print(f"⚠️ Failed to initialize unified retriever: {e}")
        traceback.print_exc()
        return None
