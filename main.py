import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from typing import TypedDict
from e2b_code_interpreter import Sandbox
from langgraph.graph import StateGraph, END
import subprocess

# Load environment variables
load_dotenv()

# Initialize the LLM
llm = ChatOpenAI(
    api_key=os.getenv("OPENROUTER_API_KEY"),
    base_url="https://openrouter.ai/api/v1",
    model="openrouter/free", # The :free tag is important!
    temperature=0
)

def call_llm(prompt: str) -> str:
    messages = [
        SystemMessage(content=(
            "You are an expert Python developer. Output ONLY valid, runnable Python code. "
            "Do NOT include markdown formatting, backticks, or explanations. "
            "CRITICAL: Do NOT use the input() function. The code will run in a headless environment without user interaction. "
            "Return the raw code and nothing else."
        )),
        HumanMessage(content=prompt)
    ]
    return llm.invoke(messages).content

# 1. Define the State
class AgentState(TypedDict):
    task: str
    code: str
    error: str
    iterations: int

# 2. Node A: The Developer
def developer_agent(state: AgentState):
    print("🤖 Developer is writing code...")
    
    # If there is an error, we tell the LLM to fix it. 
    # If not, we just give it the base task.
    if state["error"]:
        prompt = f"Fix this code: {state['code']}. It threw this error: {state['error']}"
    else:
        prompt = f"Write a python script for: {state['task']}"
    
    # [Call your LLM API here to generate the code]
    raw_code = call_llm(prompt) 
    clean_code = raw_code
    if "```" in clean_code:
        # Split by backticks and grab the actual code block (usually the second item)
        blocks = clean_code.split("```")
        if len(blocks) >= 3:
            clean_code = blocks[1]
            # Remove the "python" keyword if it's on the first line
            if clean_code.lower().startswith("python"):
                clean_code = clean_code[6:]
    
    return {"code": clean_code, "iterations": state["iterations"] + 1}

# 3. Node B: The Reviewer (Execution)
# 3. Node B: The Reviewer (Cloud Execution)
def reviewer_agent(state: AgentState):
    print("☁️ Reviewer is spinning up the E2B Cloud Sandbox...")
    
    # The 'with' statement ensures the sandbox is automatically destroyed when finished
    with Sandbox.create() as sandbox:
        print("🔎 Running code in isolated environment...")
        
        # Execute the AI's code inside the cloud VM
        execution = sandbox.run_code(state["code"])
        
        # Check if the execution crashed
        if execution.error:
            error_message = f"{execution.error.name}: {execution.error.value}"
            print(f"❌ Code crashed! Sending error back to developer:\n{error_message}")
            return {"error": error_message}
            
        else:
            print("✅ Code executed successfully!")
            # You can also capture execution.logs.stdout if you want to see the prints
            return {"error": "SUCCESS"}

# 4. The Judge (Conditional Edge)
def route_next_step(state: AgentState):
    # If it passed, or we tried too many times, stop.
    if state["error"] == "SUCCESS" or state["iterations"] >= 3:
        return "end"
    
    # Otherwise, loop back to the developer
    return "developer"

# 5. Build the State Machine
workflow = StateGraph(AgentState)

# Add our agents
workflow.add_node("developer", developer_agent)
workflow.add_node("reviewer", reviewer_agent)

# Define the flow
workflow.set_entry_point("developer")
workflow.add_edge("developer", "reviewer")

# Add the self-healing loop
workflow.add_conditional_edges(
    "reviewer",
    route_next_step,
    {
        "developer": "developer", # Go back and fix it
        "end": END                # Finish
    }
)

app = workflow.compile()

# Initial state with a task that usually requires a retry
initial_state = {
    "task": "Write a python script that fetches the HTML from 'https://example.com' using ONLY the built-in 'socket' library (do NOT use requests or urllib), parses out the title tag, and prints it.",
    "code": "",
    "error": "",
    "iterations": 0
}

# Run the graph
print("🚀 Starting the self-healing loop...")
final_state = app.invoke(initial_state)

print("\n✅ Final Code Output:")
print(final_state["code"])