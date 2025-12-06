import os
from typing import List, Dict, Any, Optional
from langchain_openai import ChatOpenAI
from mcp_use import MCPAgent, MCPClient


class SupersetAIAgent:
    """AI Agent for interacting with Superset via MCP using mcp-use"""
    
    def __init__(self):
        """Initialize the AI agent"""
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable not set")

        self.llm = ChatOpenAI(
            model="gpt-4o",
            temperature=0,
            api_key=api_key
        )

        mcp_server_path = os.getenv("SUPERSET_MCP_PATH")
        if not mcp_server_path:
            raise ValueError("SUPERSET_MCP_PATH environment variable not set")
        
        mcp_python = os.getenv("SUPERSET_MCP_PYTHON", "python")
        
        self.mcp_config = {
            "mcpServers": {
                "superset": {
                    "command": mcp_python,
                    "args": [mcp_server_path]
                }
            }
        }

        
    async def initialize(self):
        """Initialize the agent by connecting to MCP server"""
        print("Superset MCP Agent initialized and ready")
    
    async def chat(
        self,
        messages: List[Dict[str, str]],
        stream: bool = False
    ) -> Dict[str, Any]:
        """
        Process a chat message and interact with Superset
        
        Args:
            messages: List of chat messages in OpenAI format
            stream: Whether to stream the response
            
        Returns:
            Dictionary with response and metadata
        """
        last_user_message = messages[-1]["content"] if messages else ""

        enhanced_query = (
            "You are a basic prototype assistant for Apache Superset. "
            "Keep answers short and focus on the request. "
            f"User request: {last_user_message}"
        )
        
        mcp_client = None
        agent = None
        
        try:
            mcp_client = MCPClient.from_dict(self.mcp_config)
            
            agent = MCPAgent(llm=self.llm, client=mcp_client, max_steps=10)
            
            result = await agent.run(enhanced_query)
            
            return {
                "content": result,
                "role": "assistant",
                "finish_reason": "stop",
                "model": "gpt-4o"
            }
        except Exception as e:
            return {
                "content": f"Ошибка при обработке запроса: {str(e)}",
                "role": "assistant",
                "finish_reason": "error",
                "model": "gpt-4o"
            }
        finally:
            if mcp_client:
                try:
                    await mcp_client.close()
                except Exception as e:
                    print(f"Warning: Error closing MCP client: {e}")
    

_agent: Optional[SupersetAIAgent] = None


def get_agent() -> SupersetAIAgent:
    """Get or create the AI agent singleton"""
    global _agent
    if _agent is None:
        _agent = SupersetAIAgent()
    return _agent
