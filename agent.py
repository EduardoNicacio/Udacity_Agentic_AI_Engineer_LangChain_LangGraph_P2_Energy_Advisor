import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage
from langgraph.prebuilt import create_react_agent
from tools import TOOL_KIT

load_dotenv()


class Agent:
    def __init__(self, instructions: str, model: str = "gpt-4o-mini"):
        self.instructions = instructions
        self.model_name = model

        llm = ChatOpenAI(
            model=model,
            temperature=0.0,
            base_url="https://openai.vocareum.com/v1",
            api_key=os.getenv("VOCAREUM_API_KEY")
        )

        self.graph = create_react_agent(
            name="energy_advisor",
            prompt=SystemMessage(content=instructions),
            model=llm,
            tools=TOOL_KIT,
        )

    def invoke(self, question: str, context: str = None) -> dict:
        messages = []
        if context:
            messages.append(("system", context))

        messages.append(("user", question))

        try:
            response = self.graph.invoke(
                input={
                    "messages": messages
                }
            )
            return response
        except Exception as e:
            error_msg = f"Agent encountered an error: {str(e)}"
            return {
                "messages": [
                    {"role": "system", "content": error_msg}
                ]
            }

    def get_agent_tools(self) -> list:
        return [t.name for t in TOOL_KIT]
