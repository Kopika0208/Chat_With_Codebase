# cache.py
"""
Cached resource loading and initialization.
All expensive operations are cached to improve performance.
Multi-repo safe.
"""

import os
import json
import traceback
import streamlit as st
from langchain_groq import ChatGroq
from langchain_community.vectorstores import FAISS
from langchain_community.embeddings import JinaEmbeddings

from redis_storage import get_json, repo_exists

from query_understanding import QueryUnderstanding
from unified_retrieval import UnifiedRetriever

try:
    from .graph_rag import create_graph_rag_retriever
    from .graph_traversal import load_knowledge_graph
except ImportError:
    from graph_rag import create_graph_rag_retriever
    from graph_traversal import load_knowledge_graph


# ======================================================
# 🔧 CONFIG
# ======================================================
EMBED_MODEL = "jina-embeddings-v2-base-code"

# Data directory is at project root, not inside retrieval/
DATA_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data"
)


def get_repo_paths(repo_name: str):
    base = os.path.join(DATA_DIR, repo_name)
    return {
        "base": base,
        "vector": os.path.join(base, "vector_store"),
        "callgraph": os.path.join(base, "call_graph.json"),
        "bootchain": os.path.join(base, "boot_chain.json"),
        "corestructures": os.path.join(base, "core_structures.json"),
        "knowledge": os.path.join(base, "knowledge_graph.json"),
        "symbol": os.path.join(base, "symbol_table.json"),
        "dataflow": os.path.join(base, "dataflow_analysis.json"),
        "asyncpatterns": os.path.join(base, "async_patterns.json"),
    }


# ======================================================
# 📊 GRAPH / METADATA LOADERS
# ======================================================
@st.cache_data(show_spinner=False)
def load_call_graph_cached(repo_name: str):
    if not repo_exists(repo_name, "call_graph"):
        return None
    return get_json(repo_name, "call_graph") or None


@st.cache_data(show_spinner=False)
def load_boot_chain_cached(repo_name: str):
    if not repo_exists(repo_name, "boot_chain"):
        return {}
    try:
        return get_json(repo_name, "boot_chain") or {}
    except Exception as e:
        print(f"⚠️ Failed to load boot chain for {repo_name}: {e}")
        return {}


@st.cache_data(show_spinner=False)
def load_core_structures_cached(repo_name: str):
    if not repo_exists(repo_name, "core_structures"):
        return {}
    try:
        return get_json(repo_name, "core_structures") or {}
    except Exception as e:
        print(f"Failed to load core structures for {repo_name}: {e}")
        return {}


@st.cache_data(show_spinner=False)
def load_knowledge_graph_cached(repo_name: str):
    if not repo_exists(repo_name, "knowledge_graph"):
        return {}
    try:
        return get_json(repo_name, "knowledge_graph") or {}
    except Exception as e:
        print(f"⚠️ Failed to load KG for {repo_name}: {e}")
        return {}


@st.cache_resource(show_spinner=False)
def load_graph_traversal_cached(repo_name: str):
    if not repo_exists(repo_name, "knowledge_graph"):
        return None
    try:
        kg_data = get_json(repo_name, "knowledge_graph")
        if not kg_data:
            return None
        return load_knowledge_graph(kg_data)
    except Exception as e:
        print(f"⚠️ Failed to load traversal for {repo_name}: {e}")
        return None


@st.cache_data(show_spinner=False)
def load_symbol_table_cached(repo_name: str):
    if not repo_exists(repo_name, "symbol_table"):
        return {}
    try:
        return get_json(repo_name, "symbol_table") or {}
    except Exception as e:
        print(f"⚠️ Failed to load symbol table for {repo_name}: {e}")
        return {}


@st.cache_data(show_spinner=False)
def load_dataflow_data_cached(repo_name: str):
    if not repo_exists(repo_name, "dataflow_analysis"):
        return {}
    try:
        return get_json(repo_name, "dataflow_analysis") or {}
    except Exception as e:
        print(f"⚠️ Failed to load dataflow for {repo_name}: {e}")
        return {}


# ======================================================
# 🔢 EMBEDDINGS & VECTORSTORE
# ======================================================
@st.cache_data(show_spinner=False)
def load_async_patterns_cached(repo_name: str):
    if not repo_exists(repo_name, "async_patterns"):
        return {}
    try:
        return get_json(repo_name, "async_patterns") or {}
    except Exception as e:
        print(f"Failed to load async patterns for {repo_name}: {e}")
        return {}


@st.cache_resource(show_spinner=False)
def get_embeddings():
    return JinaEmbeddings(jina_api_key=os.getenv("JINA_API_KEY"), model_name=EMBED_MODEL)


@st.cache_resource(show_spinner=False)
def get_vectorstore(repo_name: str):
    paths = get_repo_paths(repo_name)
    embeddings = get_embeddings()
    return FAISS.load_local(
        paths["vector"],
        embeddings,
        allow_dangerous_deserialization=True,
    )


# ======================================================
# 🤖 LLM
# ======================================================
@st.cache_resource(show_spinner=False)
def get_llm():
    return ChatGroq(model="moonshotai/kimi-k2-instruct-0905", temperature=0)


# ======================================================
# 🔗 GRAPH-RAG
# ======================================================
@st.cache_resource(show_spinner=False)
def get_graph_rag_retriever(repo_name: str):
    try:
        vectorstore = get_vectorstore(repo_name)
        if not repo_exists(repo_name, "knowledge_graph"):
            print(f"[Graph-RAG] KG missing for {repo_name}")
            return None

        kg_data = get_json(repo_name, "knowledge_graph")
        if not kg_data:
            print(f"[Graph-RAG] KG payload missing for {repo_name}")
            return None

        all_documents = list(vectorstore.docstore._dict.values())

        retriever = create_graph_rag_retriever(
            vectorstore=vectorstore,
            knowledge_graph_source=kg_data,
            documents=all_documents,
        )

        return retriever

    except Exception as e:
        print(f"[Graph-RAG] Failed for {repo_name}: {e}")
        traceback.print_exc()
        return None


# ======================================================
# 🧠 QUERY UNDERSTANDING
# ======================================================
def get_query_understanding(repo_name: str):
    kg = load_knowledge_graph_cached(repo_name)
    return QueryUnderstanding(knowledge_graph=kg)


# ======================================================
# 🔀 UNIFIED RETRIEVER
# ======================================================
@st.cache_resource(show_spinner=False)
def get_unified_retriever(repo_name: str):
    try:
        vectorstore = get_vectorstore(repo_name)

        symbol_table_data = load_symbol_table_cached(repo_name)
        dataflow_data = load_dataflow_data_cached(repo_name)
        call_graph_data = load_call_graph_cached(repo_name)

        all_documents = list(vectorstore.docstore._dict.values())

        return UnifiedRetriever(
            vectorstore=vectorstore,
            symbol_table_data=symbol_table_data,
            dataflow_data=dataflow_data,
            call_graph_data=call_graph_data,
            all_documents=all_documents,
        )

    except Exception as e:
        print(f"⚠️ Failed unified retriever for {repo_name}: {e}")
        traceback.print_exc()
        return None
