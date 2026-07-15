from typing import List, Dict, Any, TypedDict, Annotated, Optional
import os
import re
from langgraph.graph import StateGraph, END
from langchain_groq import ChatGroq
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
from backend.config import settings
from backend.services.rag_service import rag_service
from backend.services.search_service import search_service
import logging

logger = logging.getLogger("agent_graph")

# Define Graph State
class AgentState(TypedDict):
    chat_id: str
    user_query: str
    chat_history: List[BaseMessage]
    search_enabled: bool
    rag_enabled: bool
    summary_type: Optional[str] # "short", "detailed", "bullets", "executive" or None
    
    # Internal states
    search_docs: List[Dict[str, Any]]
    rag_docs: List[Dict[str, Any]]
    
    # Outputs
    response: str
    citations: List[Dict[str, Any]]

# Initialize LLM
llm = ChatGroq(
    model="llama-3.3-70b-specdec", # Groq fast model. Fallback: llama-3.3-70b-versatile
    groq_api_key=settings.GROQ_API_KEY,
    temperature=0.3,
    streaming=True
)

# Nodes implementation
async def retrieve_rag_node(state: AgentState) -> Dict[str, Any]:
    """Retrieves related sections from ChromaDB matching query"""
    query = state["user_query"]
    chat_id = state["chat_id"]
    
    if not state.get("rag_enabled"):
        return {"rag_docs": []}
    
    try:
        results = rag_service.query_rag(chat_id, query)
        return {"rag_docs": results}
    except Exception as e:
        logger.error(f"RAG retrieval node error: {e}")
        return {"rag_docs": []}

async def web_search_node(state: AgentState) -> Dict[str, Any]:
    """Retrieves search pages from Tavily matching query"""
    query = state["user_query"]
    
    if not state.get("search_enabled"):
        return {"search_docs": []}
        
    try:
        results = await search_service.search(query)
        return {"search_docs": results}
    except Exception as e:
        logger.error(f"Search retrieval node error: {e}")
        return {"search_docs": []}

async def summarizer_node(state: AgentState) -> Dict[str, Any]:
    """Processes summarization requests for files uploaded in the chat"""
    chat_id = state["chat_id"]
    summary_type = state.get("summary_type", "short")
    
    # Retrieve all document context from Chroma for the chat
    # To summarize, we query the DB with a general search or pull direct chunks.
    # For a general summarization, we pull up to 15 relevant chunks containing text
    try:
        chunks = rag_service.query_rag(chat_id, query="document overview", top_k=12)
        if not chunks:
            return {
                "response": "No uploaded documents found to summarize. Please upload a PDF, DOCX, or TXT file first.",
                "citations": []
            }
        
        context = "\n\n".join([c["page_content"] for c in chunks])
        
        prompt_templates = {
            "short": "Provide a brief summary (under 250 words) highlight of the following text:\n\n{context}",
            "detailed": "Provide a detailed, comprehensive summary of the following documents, structuring key concepts and sections:\n\n{context}",
            "bullets": "Summarize the key points of the following text in bullet items:\n\n{context}",
            "executive": "Write a formal Executive Summary of the following document contents, outlining problem statement, key findings, and action items:\n\n{context}"
        }
        
        prompt = prompt_templates.get(summary_type, prompt_templates["short"]).format(context=context)
        
        messages = [
            SystemMessage(content="You are an expert academic research assistant who excels at writing clear, objective summaries."),
            HumanMessage(content=prompt)
        ]
        
        resp = await llm.ainvoke(messages)
        
        # Setup citations based on source files represented in chunks
        seen_docs = set()
        citations = []
        for i, doc in enumerate(chunks):
            src_name = doc["metadata"].get("source", "Document")
            page_num = doc["metadata"].get("page", 1)
            citation_key = f"{src_name} - Page {page_num}"
            if citation_key not in seen_docs:
                seen_docs.add(citation_key)
                citations.append({
                    "title": f"{src_name} (Page {page_num})",
                    "url": "",
                    "snippet": doc["page_content"][:150] + "..."
                })

        return {
            "response": resp.content,
            "citations": citations
        }
    except Exception as e:
        logger.error(f"Summarizer node error: {e}")
        return {
            "response": f"Failed to generate summary: {str(e)}",
            "citations": []
        }

async def generate_response_node(state: AgentState) -> Dict[str, Any]:
    """Generates the final answer with footnotes using LLM combined context"""
    query = state["user_query"]
    history = state.get("chat_history", [])
    rag_docs = state.get("rag_docs", [])
    search_docs = state.get("search_docs", [])
    
    # 1. Compile Context
    context_str = ""
    citations = []
    citation_index = 1
    
    if rag_docs:
        context_str += "=== UPLOADED DOCUMENT SOURCE CHUNKS ===\n"
        for doc in rag_docs:
            source = doc["metadata"].get("source", "Uploaded Document")
            page = doc["metadata"].get("page", 1)
            context_str += f"[Doc Citation {citation_index}] (File: {source}, Page {page}):\n{doc['page_content']}\n\n"
            citations.append({
                "id": citation_index,
                "title": f"{source} (Page {page})",
                "url": "",
                "snippet": doc["page_content"]
            })
            citation_index += 1
            
    if search_docs:
        context_str += "=== WEB SEARCH RESULTS ===\n"
        for doc in search_docs:
            context_str += f"[Web Citation {citation_index}] (Title: {doc['title']}, URL: {doc['url']}):\n{doc['snippet']}\n\n"
            citations.append({
                "id": citation_index,
                "title": doc["title"],
                "url": doc["url"],
                "snippet": doc["snippet"]
            })
            citation_index += 1
            
    # System Instruction
    system_prompt = (
        "You are an expert AI Research Assistant. Answer the user's query comprehensively and objectively.\n"
        "You must cite the provided contexts in your answer using bracketed indices (e.g. [1], [2]).\n"
        "Map [Doc Citation X] to [X] and [Web Citation Y] to [Y] accurately inside your response.\n"
        "Only cite from the contexts below. If the provided contexts do not contain the answer, "
        "state that you cannot confirm the answer from the references but answer to your best knowledge if appropriate, "
        "without fabricating source citations. Do not make up URLs.\n\n"
        f"Contexts:\n{context_str}"
    )
    
    # Pack Chat History + New Query
    messages = [SystemMessage(content=system_prompt)]
    for msg in history[-8:]: # Recall last 8 messages for context window management
        messages.append(msg)
    messages.append(HumanMessage(content=query))
    
    try:
        resp = await llm.ainvoke(messages)
        return {
            "response": resp.content,
            "citations": citations
        }
    except Exception as e:
        logger.error(f"Response node error: {e}")
        return {
            "response": f"An error occurred while generating the assistant response: {str(e)}",
            "citations": []
        }

# Graph Routing helper
def route_direction(state: AgentState) -> str:
    """Decides if the node should direct to normal generator or summarizer"""
    if state.get("summary_type") is not None:
        return "summarize"
    return "generate"

# Build StateGraph
workflow = StateGraph(AgentState)

# Add Nodes
workflow.add_node("retrieve_rag", retrieve_rag_node)
workflow.add_node("web_search", web_search_node)
workflow.add_node("summarize", summarizer_node)
workflow.add_node("generate_response", generate_response_node)

# Set Entry Point
workflow.set_entry_point("retrieve_rag")

# Add edges (parallel retrieval)
workflow.add_edge("retrieve_rag", "web_search")

# Add conditional path after search
workflow.add_conditional_edges(
    "web_search",
    route_direction,
    {
        "summarize": "summarize",
        "generate": "generate_response"
    }
)

# Terminate after summaries or generations
workflow.add_edge("summarize", END)
workflow.add_edge("generate_response", END)

# Compile graph
agent_graph = workflow.compile()
