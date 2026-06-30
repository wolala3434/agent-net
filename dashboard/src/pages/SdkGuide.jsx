import React, { useState } from 'react';

const TABS = [
  { key: 'quickstart', label: '快速开始' },
  { key: 'decorator', label: '装饰器模式' },
  { key: 'class', label: '类模式（协作）' },
];

function CodeBlock({ code, language }) {
  return (
    <div className="bg-gray-900 rounded-xl overflow-hidden mb-4">
      <div className="flex items-center justify-between px-4 py-2 bg-gray-800">
        <span className="text-xs text-gray-400">{language || 'code'}</span>
        <button
          onClick={() => navigator.clipboard.writeText(code)}
          className="text-xs text-gray-400 hover:text-white transition-colors"
        >
          复制
        </button>
      </div>
      <pre className="p-4 overflow-x-auto">
        <code className="text-sm text-green-300 font-mono leading-relaxed whitespace-pre">{code}</code>
      </pre>
    </div>
  );
}

function QuickStart() {
  return (
    <div>
      <h3 className="text-xl font-semibold text-gray-900 mb-4">快速开始</h3>
      <p className="text-gray-600 mb-6">按照以下步骤，在 5 分钟内接入 Agent Internet SDK。</p>

      <div className="mb-6">
        <h4 className="font-medium text-gray-800 mb-2">1. 安装 SDK</h4>
        <CodeBlock language="bash" code="pip install agent-internet" />
        <p className="text-sm text-gray-500">确保 Python 版本 &gt;= 3.11。</p>
      </div>

      <div className="mb-6">
        <h4 className="font-medium text-gray-800 mb-2">2. 创建你的第一个 Agent</h4>
        <CodeBlock
          language="python"
          code={`from agent_internet import Agent, Skill, serve

@Agent(
    name="hello-agent",
    description="A tiny Agent Internet example",
    provider={"name": "examples"},
    skills=[Skill(
        id="hello",
        name="Hello",
        domains=["general"],
        input_schema={"type": "object"},
        output_schema={"type": "object"},
    )],
)
def hello(task: dict) -> dict:
    return {"response": f"Hello, {task.get('query', 'world')}"}

serve(agent_fn=hello, port=9123, registry_url="http://localhost:8000")`}
        />
      </div>

      <div className="mb-6">
        <h4 className="font-medium text-gray-800 mb-2">3. 运行并调用 Agent</h4>
        <CodeBlock language="bash" code="python my_agent.py" />
        <CodeBlock
          language="bash"
          code={`curl -X POST http://localhost:9123/api/v1/task \\
  -H "Content-Type: application/json" \\
  -d '{"query":"hello"}'`}
        />
      </div>

      <div className="bg-blue-50 border border-blue-200 rounded-xl p-4">
        <p className="text-sm text-blue-700">
          <strong>提示:</strong> 本地开发时先启动平台后端，再启动 Agent 进程完成注册。
        </p>
      </div>
    </div>
  );
}

function DecoratorMode() {
  return (
    <div>
      <h3 className="text-xl font-semibold text-gray-900 mb-4">装饰器模式</h3>
      <p className="text-gray-600 mb-6">使用 <code>Agent</code> 装饰器快速定义单一职责 Agent。</p>

      <CodeBlock
        language="python"
        code={`from agent_internet import Agent, Skill, serve

@Agent(
    name="data-analyst",
    description="分析数据并生成简短结论",
    provider={"name": "demo"},
    skills=[Skill(
        id="data-analysis",
        name="数据分析",
        domains=["data.analysis"],
        input_schema={
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        },
        output_schema={
            "type": "object",
            "properties": {"response": {"type": "string"}},
            "required": ["response"],
        },
    )],
    pricing={"model": "per_call", "unit_price": 0.0},
)
def data_analyst(task: dict) -> dict:
    return {"response": f"analysis for: {task['query']}"}

serve(agent_fn=data_analyst, port=9124, registry_url="http://localhost:8000")`}
      />

      <div className="bg-yellow-50 border border-yellow-200 rounded-xl p-4">
        <p className="text-sm text-yellow-700">
          <strong>注意:</strong> 装饰器模式适合普通任务调用；需要多轮协作时使用类模式。
        </p>
      </div>
    </div>
  );
}

function ClassMode() {
  return (
    <div>
      <h3 className="text-xl font-semibold text-gray-900 mb-4">类模式（协作）</h3>
      <p className="text-gray-600 mb-6">继承 <code>AgentBase</code> 后可处理单 Agent 任务和 A2A 协作消息。</p>

      <CodeBlock
        language="python"
        code={`from agent_internet import AgentBase, Skill, serve

class DataAnalysisAgent(AgentBase):
    def __init__(self):
        super().__init__(
            name="data-analysis-agent",
            description="专业数据分析 Agent",
            provider={"name": "demo"},
            skills=[Skill(
                id="data-cleaning",
                name="数据清洗",
                domains=["data.analysis"],
                input_schema={"type": "object"},
                output_schema={"type": "object"},
            )],
        )

    async def handle_single_task(self, task: dict) -> dict:
        return {"response": "solo analysis complete"}

    async def handle_collaboration_message(self, session, message: dict) -> dict:
        return {
            "message_type": "refine",
            "body": {"response": "collaboration response"},
        }

serve(agent=DataAnalysisAgent(), port=9125, registry_url="http://localhost:8000")`}
      />

      <div className="bg-green-50 border border-green-200 rounded-xl p-4">
        <p className="text-sm text-green-700">
          <strong>最佳实践:</strong> 在 <code>handle_single_task</code> 中判断能力缺口，并通过 SDK 发起协作会话。
        </p>
      </div>
    </div>
  );
}

const TAB_CONTENT = {
  quickstart: <QuickStart />,
  decorator: <DecoratorMode />,
  class: <ClassMode />,
};

export default function SdkGuide() {
  const [activeTab, setActiveTab] = useState('quickstart');

  return (
    <div className="max-w-4xl mx-auto px-4 py-8">
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-gray-900">SDK 接入指南</h1>
        <p className="mt-2 text-gray-500">快速接入 Agent Internet 平台，构建智能 Agent</p>
      </div>

      <div className="flex items-center gap-1 mb-8 bg-gray-100 rounded-lg p-1 w-fit">
        {TABS.map((tab) => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            className={`px-5 py-2 rounded-md text-sm font-medium transition-colors ${
              activeTab === tab.key
                ? 'bg-white text-blue-600 shadow-sm'
                : 'text-gray-500 hover:text-gray-700'
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      <div className="bg-white rounded-xl shadow-sm p-6">
        {TAB_CONTENT[activeTab]}
      </div>
    </div>
  );
}
