"""
Streamlit UI components for onboarding visualization.
"""

import streamlit as st
from typing import Dict, List

try:
    from .analyzer import CodebaseAnalyzer
except ImportError:
    from analyzer import CodebaseAnalyzer


def render_project_overview(stats: Dict):
    """Render project overview statistics with human-friendly explanation."""
    st.subheader("📊 Project Statistics")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric(
            "📁 Files",
            stats["total_files"],
            help="Total number of source files"
        )
    
    with col2:
        st.metric(
            "⚙️ Functions",
            stats["total_functions"],
            help="Total number of functions/methods"
        )
    
    with col3:
        st.metric(
            "🏛️ Classes",
            stats["total_classes"],
            help="Total number of classes"
        )
    
    # Add human-friendly explanation
    st.markdown("""
    ### 📖 What This Means
    
    This codebase contains **{files}** files with **{funcs}** functions and **{classes}** classes.
    
    **How to approach learning this codebase:**
    1. Start with **Entry & Exit Points** to understand where the code starts and ends
    2. Follow the **Onboarding Roadmap** in order - it's designed to build your understanding progressively
    3. Use the **File Structure** to navigate around
    4. Use **Navigation** to see how functions relate to each other
    5. Check **Documentation** to find functions that need better explanations
    """.format(
        files=stats["total_files"],
        funcs=stats["total_functions"],
        classes=stats["total_classes"]
    ))


def render_entry_exit_points(entry_points: List[Dict], exit_points: List[Dict]):
    """Render entry and exit points with explanations."""
    st.markdown("""
    ### 🎯 Understanding Entry & Exit Points
    
    **Entry Points** are where the application starts running.
    **Exit Points** are functions that don't call anything else (dead ends).
    """)
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("🚀 Entry Points")
        st.markdown("_Where the program starts - begin here to understand the flow_")
        
        if entry_points:
            for idx, ep in enumerate(entry_points[:15], 1):
                st.markdown(f"""
                **{idx}. {ep['name']}** 
                - Location: `{ep['file']}`
                - Type: {ep['type']}
                - Lines: {ep['start_line']}–{ep['end_line']}
                """)
        else:
            st.info("No obvious entry points found. Check for `main()`, `run()`, or `app` functions.")
    
    with col2:
        st.subheader("🏁 Exit Points")
        st.markdown("_Dead-end functions that don't call other functions_")
        
        if exit_points:
            for idx, ep in enumerate(exit_points[:15], 1):
                st.markdown(f"""
                **{idx}. {ep['name']}** 
                - Location: `{ep['file']}`
                - Type: {ep['type']}
                - Lines: {ep['start_line']}–{ep['end_line']}
                """)
        else:
            st.info("No exit points found. All functions call other functions.")


def render_roadmap(roadmap: List[Dict]):
    """Render improved roadmap with natural language explanations."""
    st.markdown("""
    ### 📚 Guided Learning Path
    
    This roadmap shows files and functions in a **logical order** based on code dependencies.
    Start from the top and work your way down to understand the codebase progressively.
    
    **Tip:** Files higher in the list are likely entry points. Files lower are helper utilities.
    """)
    
    if "roadmap_checklist" not in st.session_state:
        st.session_state.roadmap_checklist = {
            i: False for i in range(len(roadmap))
        }
    
    progress = sum(1 for v in st.session_state.roadmap_checklist.values() if v)
    st.progress(progress / max(len(roadmap), 1), text=f"Progress: {progress}/{len(roadmap)} files read")
    
    for idx, item in enumerate(roadmap[:30]):  # Show top 30 files
        file_path = item["file"]
        min_depth = item["min_depth"]
        num_symbols = len(item["symbols"])
        
        # Better depth indicator
        if min_depth == float('inf'):
            depth_desc = "**Isolated** (no connections)"
            depth_icon = "🔌"
        elif min_depth == 0:
            depth_desc = "**Core** - Main entry point"
            depth_icon = "🎯"
        elif min_depth <= 2:
            depth_desc = "**High Priority** - Called early"
            depth_icon = "⭐"
        elif min_depth <= 5:
            depth_desc = "**Medium Priority** - Helper functions"
            depth_icon = "📌"
        else:
            depth_desc = "**Low Priority** - Deep dependencies"
            depth_icon = "📍"
        
        with st.expander(f"{depth_icon} **{file_path}** ({num_symbols} items) - {depth_desc}"):
            checked = st.checkbox(
                "✅ I understand this file",
                value=st.session_state.roadmap_checklist.get(idx, False),
                key=f"roadmap_check_{idx}"
            )
            st.session_state.roadmap_checklist[idx] = checked
            
            st.markdown(f"""
            **What's in this file:**
            - **Item count:** {num_symbols} functions/classes
            - **Dependency level:** {min_depth if min_depth != float('inf') else '∞'} (lower = more important)
            
            **Key items to understand:**
            """)
            
            for symbol in item["symbols"][:8]:  # Show top 8 symbols per file
                symbol_type = "🔧" if symbol.get("type") == "function" else "🏛️" if symbol.get("type") == "class" else "⚙️"
                st.markdown(
                    f"{symbol_type} `{symbol['name']}` ({symbol['end_line'] - symbol['start_line']} lines)"
                )
            
            if len(item["symbols"]) > 8:
                st.markdown(f"... and {len(item['symbols']) - 8} more items")


def render_file_tree(tree: Dict, level: int = 0):
    """Render file structure as an interactive tree."""
    st.markdown("""
    ### 🌳 Repository Structure
    
    This shows how your code is organized. Expand folders to explore the structure.
    """)
    
    def render_tree_node(node, level=0):
        """Recursively render tree nodes with better formatting."""
        indent = "  " * level
        
        if node["type"] == "folder":
            # Use expander for folders
            with st.expander(f"📁 **{node['name']}**"):
                if node.get("children"):
                    for child in node["children"]:
                        render_tree_node(child, level + 1)
                else:
                    st.markdown("_(Empty folder)_")
        else:
            # Show files as simple items
            st.markdown(f"{indent}📄 `{node['name']}`")
    
    if tree and tree.get("children"):
        render_tree_node(tree)
    else:
        st.info("No files found in this repository.")


def render_navigation_hints(analyzer: CodebaseAnalyzer, selected_symbol: str):
    """Render navigation hints with human-friendly explanations."""
    if not selected_symbol:
        st.info("👇 Select a symbol from the dropdown to explore its relationships")
        return
    
    relations = analyzer.get_related_symbols(selected_symbol)
    symbol_info = analyzer.symbol_table.get(selected_symbol, {})
    
    st.markdown(f"""
    ### 🧭 Understanding: `{selected_symbol}`
    
    **Location:** `{symbol_info.get('file', 'unknown')}`  
    **Type:** {symbol_info.get('type', 'unknown')}  
    **Lines:** {symbol_info.get('start_line', '?')}–{symbol_info.get('end_line', '?')}
    """)
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("""
        #### 👈 **Callers** (Who uses this?)
        
        These functions call your selected function.  
        Understanding callers helps you see *when* and *why* this function is used.
        """)
        
        if relations["callers"]:
            for caller in relations["callers"][:15]:
                st.markdown(f"- `{caller}`")
            if len(relations["callers"]) > 15:
                st.markdown(f"- _{len(relations['callers']) - 15} more..._")
        else:
            st.markdown("_No callers found - this might be an entry point!_")
    
    with col2:
        st.markdown("""
        #### 👉 **Callees** (What does this call?)
        
        These are the functions your selected function calls.  
        Understanding callees helps you see *what* this function depends on.
        """)
        
        if relations["callees"]:
            for callee in relations["callees"][:15]:
                st.markdown(f"- `{callee}`")
            if len(relations["callees"]) > 15:
                st.markdown(f"- _{len(relations['callees']) - 15} more..._")
        else:
            st.markdown("_No callees found - this might be a leaf function!_")


def render_weak_documentation_section(weak_docs: List[Dict], llm, analyzer: CodebaseAnalyzer):
    """Render documentation improvement assistant."""
    st.markdown("""
    ### 📝 Documentation Quality Check
    
    Functions listed here have complex logic but lack clear documentation.  
    Improving their documentation makes the codebase easier to understand for new developers.
    """)
    
    if not weak_docs:
        st.success("✅ Excellent! All symbols have adequate documentation!")
        return
    
    st.warning(f"⚠️ Found {len(weak_docs)} functions/classes that need better documentation")
    
    # Create selector
    symbol_options = {}
    for item in weak_docs[:20]:
        key = f"{item['name']} ({item['file']})"
        symbol_options[key] = item
    
    selected_key = st.selectbox(
        "Choose a symbol to improve documentation:",
        list(symbol_options.keys()),
        key="weak_doc_selector"
    )
    
    if selected_key:
        selected_item = symbol_options[selected_key]
        relations = analyzer.get_related_symbols(selected_item['name'])
        
        st.markdown(f"""
        ### 📋 Current Details: `{selected_item['name']}`
        
        | Property | Value |
        |----------|-------|
        | **File** | `{selected_item['file']}` |
        | **Type** | {selected_item['type']} |
        | **Lines** | {selected_item['start_line']}–{selected_item['end_line']} |
        | **Complexity** | {selected_item['complexity_score']}/100 |
        | **Functions Called** | {selected_item['callees']} |
        | **Called By** | {relations['num_callers']} functions |
        """)
        
        if st.button("🤖 Generate Improved Documentation", key="gen_doc_btn"):
            with st.spinner("Generating documentation..."):
                try:
                    callers_str = ', '.join(relations['callers'][:5]) if relations['callers'] else "None"
                    callees_str = ', '.join(relations['callees'][:5]) if relations['callees'] else "None"
                    
                    prompt = f"""
Generate professional Python documentation for this function/class:

**Name:** {selected_item['name']}
**Type:** {selected_item['type']}
**File:** {selected_item['file']}
**Complexity Score:** {selected_item['complexity_score']}

**Relationships:**
- Called by: {callers_str}
- Calls: {callees_str}

Generate a comprehensive docstring that explains:
1. **Purpose** - What does this do in plain English?
2. **Parameters** - What inputs does it take?
3. **Returns** - What does it produce?
4. **Behavior** - How does it work?
5. **Example Usage** - How is it typically used?

Format as a Python docstring (triple quotes).
"""
                    
                    response = llm.invoke(prompt).content
                    
                    st.success("✅ Documentation generated!")
                    st.markdown("### 📖 Generated Documentation")
                    st.code(response, language="python")
                    
                except Exception as e:
                    st.error(f"Error generating documentation: {e}")


def render_summary(summary: str):
    """Render project summary."""
    st.markdown("### 📖 Project Summary")
    st.markdown(summary)
