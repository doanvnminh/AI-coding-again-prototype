import os
import json
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from langgraph.graph import StateGraph, END
from typing import TypedDict
from e2b_code_interpreter import Sandbox

load_dotenv()

# --- 1. YOUR EXISTING SETUP & AGENTS ---
llm = ChatOpenAI(
    api_key=os.getenv("OPENROUTER_API_KEY"),
    base_url="https://openrouter.ai/api/v1",
    model="openrouter/free", 
    temperature=0
)

def call_llm(prompt: str) -> str:
    messages = [
        SystemMessage(content="You are an expert Python developer. Output ONLY valid, runnable Python code. Do NOT include markdown formatting, backticks, or explanations. Return the raw code and nothing else."),
        HumanMessage(content=prompt)
    ]
    return llm.invoke(messages).content

class AgentState(TypedDict):
    task: str
    code: str
    error: str
    iterations: int

def developer_agent(state: AgentState):
    if state["error"]:
        prompt = f"Fix this code: {state['code']}. It threw this error: {state['error']}"
    else:
        prompt = f"Write a python script for: {state['task']}"
    
    return {"code": call_llm(prompt), "iterations": state["iterations"] + 1}

def reviewer_agent(state: AgentState):
    with Sandbox.create() as sandbox:
        execution = sandbox.run_code(state["code"])
        if execution.error:
            return {"error": f"{execution.error.name}: {execution.error.value}"}
        else:
            return {"error": "SUCCESS"}

def route_next_step(state: AgentState):
    if state["error"] == "SUCCESS" or state["iterations"] >= 3:
        return "end"
    return "developer"

workflow = StateGraph(AgentState)
workflow.add_node("developer", developer_agent)
workflow.add_node("reviewer", reviewer_agent)
workflow.set_entry_point("developer")
workflow.add_edge("developer", "reviewer")
workflow.add_conditional_edges("reviewer", route_next_step, {"developer": "developer", "end": END})

# Compile the graph
langgraph_app = workflow.compile()

# --- 2. NEW: FASTAPI WEBSOCKET SERVER ---
app = FastAPI()

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    # 1. Accept the connection from the frontend
    await websocket.accept()
    print("🟢 Client connected")
    
    try:
        # 2. Wait for the user to send a prompt (e.g., {"task": "Write a sorting script"})
        data = await websocket.receive_text()
        task_request = json.loads(data).get("task", "print('No task provided')")
        
        initial_state = {
            "task": task_request,
            "code": "",
            "error": "",
            "iterations": 0
        }
        
        await websocket.send_text(json.dumps({"type": "info", "message": "Agent loop started..."}))

        # 3. Stream the graph! 
        # Instead of waiting for the end, .stream() yields the state every time a node finishes.
        for output in langgraph_app.stream(initial_state):
            
            # Output looks like: {'developer': {'code': '...', 'iterations': 1}}
            for node_name, state_update in output.items():
                
                # Send the live update back to the frontend
                await websocket.send_text(json.dumps({
                    "type": "update",
                    "node": node_name,
                    "state": state_update
                }))
                
        await websocket.send_text(json.dumps({"type": "info", "message": "Workflow complete!"}))

    except WebSocketDisconnect:
        print("🔴 Client disconnected")

# --- ADD THIS TO THE VERY BOTTOM OF server.py ---
if __name__ == "__main__":
    import uvicorn
    # This tells Python to run the FastAPI app on port 8000
    uvicorn.run("server:app", host="127.0.0.1", port=8000, reload=True)