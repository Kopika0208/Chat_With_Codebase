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
from langchain_huggingface import HuggingFaceEmbeddings

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
EMBED_MODEL = "mixedbread-ai/mxbai-embed-large-v1"

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
        "knowledge": os.path.join(base, "knowledge_graph.json"),
        "symbol": os.path.join(base, "symbol_table.json"),
        "dataflow": os.path.join(base, "dataflow_analysis.json"),
    }


# ======================================================
# 📊 GRAPH / METADATA LOADERS
# ======================================================
@st.cache_data(show_spinner=False)
def load_call_graph_cached(repo_name: str):
    paths = get_repo_paths(repo_name)
    if not os.path.exists(paths["callgraph"]):
        return None
    with open(paths["callgraph"], "r", encoding="utf-8") as f:
        return json.load(f)


@st.cache_data(show_spinner=False)
def load_knowledge_graph_cached(repo_name: str):
    paths = get_repo_paths(repo_name)
    if not os.path.exists(paths["knowledge"]):
        return {}
    try:
        with open(paths["knowledge"], "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"⚠️ Failed to load KG for {repo_name}: {e}")
        return {}


@st.cache_resource(show_spinner=False)
def load_graph_traversal_cached(repo_name: str):
    paths = get_repo_paths(repo_name)
    kg_path = paths["knowledge"]
    if not os.path.exists(kg_path):
        return None
    try:
        return load_knowledge_graph(kg_path)
    except Exception as e:
        print(f"⚠️ Failed to load traversal for {repo_name}: {e}")
        return None


@st.cache_data(show_spinner=False)
def load_symbol_table_cached(repo_name: str):
    paths = get_repo_paths(repo_name)
    if not os.path.exists(paths["symbol"]):
        return {}
    try:
        with open(paths["symbol"], "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"⚠️ Failed to load symbol table for {repo_name}: {e}")
        return {}


@st.cache_data(show_spinner=False)
def load_dataflow_data_cached(repo_name: str):
    paths = get_repo_paths(repo_name)
    if not os.path.exists(paths["dataflow"]):
        return {}
    try:
        with open(paths["dataflow"], "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"⚠️ Failed to load dataflow for {repo_name}: {e}")
        return {}


# ======================================================
# 🔢 EMBEDDINGS & VECTORSTORE
# ======================================================
@st.cache_resource(show_spinner=False)
def get_embeddings():
    return HuggingFaceEmbeddings(model_name=EMBED_MODEL)


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
    return ChatGroq(model="llama-3.1-8b-instant", temperature=0)


# ======================================================
# 🔗 GRAPH-RAG
# ======================================================
@st.cache_resource(show_spinner=False)
def get_graph_rag_retriever(repo_name: str):
    try:
        paths = get_repo_paths(repo_name)
        vectorstore = get_vectorstore(repo_name)

        if not os.path.exists(paths["knowledge"]):
            print(f"[Graph-RAG] KG missing for {repo_name}")
            return None

        all_documents = list(vectorstore.docstore._dict.values())

        retriever = create_graph_rag_retriever(
            vectorstore=vectorstore,
            knowledge_graph_path=paths["knowledge"],
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
