"use client";

import { useState, useEffect, useRef } from "react";
import Editor from "@monaco-editor/react";
import { Play, Bot, Search, AlertCircle, CheckCircle2 } from "lucide-react";

type LogMessage = {
  id: string;
  type: "info" | "update" | "error";
  text: string;
};

export default function Home() {
  const [task, setTask] = useState("");
  const [code, setCode] = useState("// The AI's code will appear here...");
  const [logs, setLogs] = useState<LogMessage[]>([]);
  const [isWorking, setIsWorking] = useState(false);
  const ws = useRef<WebSocket | null>(null);
  const logsEndRef = useRef<HTMLDivElement>(null);

  // Auto-scroll logs
  useEffect(() => {
    logsEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [logs]);

  // Initialize WebSocket connection
  useEffect(() => {
    // Connect to your FastAPI backend
    ws.current = new WebSocket("ws://localhost:8000/ws");

    ws.current.onopen = () => {
      addLog("info", "Connected to local LangGraph engine.");
    };

    ws.current.onmessage = (event) => {
      const data = JSON.parse(event.data);

      if (data.type === "info") {
        addLog("info", data.message);
        if (data.message === "Workflow complete!") setIsWorking(false);
      }
      else if (data.type === "update") {
        // Update the code editor
        if (data.state.code) {
          setCode(data.state.code);
        }

        // Log the agent activity
        const agentName = data.node === "developer" ? "Developer Agent" : "Reviewer Agent";
        addLog("update", `${agentName} finished execution loop.`);

        // Log any caught errors
        if (data.state.error && data.state.error !== "SUCCESS") {
          addLog("error", `Execution crashed: ${data.state.error}`);
        }
      }
    };

    return () => ws.current?.close();
  }, []);

  const addLog = (type: "info" | "update" | "error", text: string) => {
    setLogs((prev) => [...prev, { id: Math.random().toString(), type, text }]);
  };

  const runAgents = () => {
    if (!task.trim() || !ws.current) return;

    setLogs([]);
    setCode("// Agents are analyzing the request...");
    setIsWorking(true);

    // Send the task to the Python backend
    ws.current.send(JSON.stringify({ task }));
  };

  return (
    <div className="flex h-screen bg-gray-950 text-gray-300 font-sans">

      {/* LEFT PANEL: Controls & Logs */}
      <div className="w-1/3 flex flex-col border-r border-gray-800 bg-gray-900 shadow-2xl">
        <div className="p-6 border-b border-gray-800">
          <h1 className="text-2xl font-bold text-white mb-2 flex items-center gap-2">
            <Bot className="text-blue-500" /> AutoDev Workspace
          </h1>
          <p className="text-sm text-gray-500 mb-6">Self-Healing Multi-Agent Architecture</p>

          <div className="space-y-4">
            <textarea
              value={task}
              onChange={(e) => setTask(e.target.value)}
              placeholder="E.g., Write a Python script to calculate the 10th Fibonacci number..."
              className="w-full h-32 p-3 bg-gray-950 border border-gray-800 rounded-lg focus:ring-2 focus:ring-blue-500 focus:outline-none resize-none"
            />
            <button
              onClick={runAgents}
              disabled={isWorking}
              className={`w-full py-3 px-4 rounded-lg font-medium flex items-center justify-center gap-2 transition-all ${isWorking
                ? "bg-blue-900/50 text-blue-300 cursor-not-allowed"
                : "bg-blue-600 hover:bg-blue-500 text-white shadow-lg shadow-blue-900/20"
                }`}
            >
              {isWorking ? (
                <span className="animate-pulse">Agents are working...</span>
              ) : (
                <>
                  <Play size={18} /> Run Workflow
                </>
              )}
            </button>
          </div>
        </div>

        {/* LOGS STREAM */}
        <div className="flex-1 overflow-y-auto p-6 space-y-4">
          <h3 className="text-sm font-semibold tracking-wider text-gray-500 uppercase mb-4">Live Execution Logs</h3>
          {logs.map((log) => (
            <div
              key={log.id}
              className={`p-3 rounded-lg text-sm flex items-start gap-3 border ${log.type === "error" ? "bg-red-950/30 border-red-900/50 text-red-400" :
                log.type === "info" ? "bg-gray-800/50 border-gray-700 text-gray-400" :
                  "bg-blue-950/20 border-blue-900/30 text-blue-300"
                }`}
            >
              <span className="mt-0.5">
                {log.type === "error" && <AlertCircle size={16} />}
                {log.type === "info" && <CheckCircle2 size={16} />}
                {log.type === "update" && <Search size={16} />}
              </span>
              <span>{log.text}</span>
            </div>
          ))}
          <div ref={logsEndRef} />
        </div>
      </div>

      {/* RIGHT PANEL: Live Editor */}
      <div className="w-2/3 h-full flex flex-col bg-[#1e1e1e]">
        <div className="flex items-center px-4 py-2 border-b border-gray-800 bg-[#2d2d2d] text-sm text-gray-400">
          agent_workspace.py
        </div>
        <div className="flex-1 pt-4">
          <Editor
            height="100%"
            defaultLanguage="python"
            theme="vs-dark"
            value={code}
            options={{
              readOnly: true,
              minimap: { enabled: false },
              fontSize: 14,
              fontFamily: "'JetBrains Mono', 'Courier New', monospace",
              padding: { top: 16 }
            }}
          />
        </div>
      </div>

    </div>
  );
}