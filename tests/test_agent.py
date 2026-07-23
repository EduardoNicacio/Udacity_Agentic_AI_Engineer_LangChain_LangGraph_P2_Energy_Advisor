import pytest
from unittest.mock import patch, MagicMock, PropertyMock


PROMPT = "You are an energy advisor."


class TestAgentConstructor:
    def test_creates_with_default_model(self):
        with patch("agent.ChatOpenAI") as mock_llm, \
             patch("agent.create_react_agent") as mock_graph:
            mock_llm.return_value = MagicMock()
            mock_graph.return_value = MagicMock()

            from agent import Agent
            agent = Agent(instructions=PROMPT)

            mock_llm.assert_called_once_with(
                model="gpt-4o-mini",
                temperature=0.0,
                base_url="https://openai.vocareum.com/v1",
                api_key="test-api-key"
            )
            assert mock_graph.called
            assert agent.instructions == PROMPT

    def test_creates_with_custom_model(self):
        with patch("agent.ChatOpenAI") as mock_llm, \
             patch("agent.create_react_agent") as mock_graph:
            mock_llm.return_value = MagicMock()
            mock_graph.return_value = MagicMock()

            from agent import Agent
            agent = Agent(instructions=PROMPT, model="gpt-4o")

            mock_llm.assert_called_once_with(
                model="gpt-4o",
                temperature=0.0,
                base_url="https://openai.vocareum.com/v1",
                api_key="test-api-key"
            )
            assert agent.model_name == "gpt-4o"

    def test_stores_instructions(self):
        with patch("agent.ChatOpenAI"), patch("agent.create_react_agent"):
            from agent import Agent
            agent = Agent(instructions=PROMPT)
            assert agent.instructions == PROMPT

    def test_prompt_passed_as_system_message(self):
        with patch("agent.ChatOpenAI") as mock_llm, \
             patch("agent.create_react_agent") as mock_graph:
            from agent import Agent
            from langchain_core.messages import SystemMessage

            mock_llm.return_value = MagicMock()
            mock_graph.return_value = MagicMock()

            Agent(instructions=PROMPT)

            call_kwargs = mock_graph.call_args.kwargs
            prompt_arg = call_kwargs.get("prompt")
            assert prompt_arg is not None
            assert isinstance(prompt_arg, SystemMessage)
            assert prompt_arg.content == PROMPT

    def test_tools_passed_to_graph(self):
        with patch("agent.ChatOpenAI") as mock_llm, \
             patch("agent.create_react_agent") as mock_graph:
            from agent import Agent
            from tools import TOOL_KIT

            mock_llm.return_value = MagicMock()
            mock_graph.return_value = MagicMock()

            Agent(instructions=PROMPT)

            call_kwargs = mock_graph.call_args.kwargs
            assert call_kwargs.get("tools") == TOOL_KIT

    def test_graph_name_is_energy_advisor(self):
        with patch("agent.ChatOpenAI") as mock_llm, \
             patch("agent.create_react_agent") as mock_graph:
            from agent import Agent

            mock_llm.return_value = MagicMock()
            mock_graph.return_value = MagicMock()

            Agent(instructions=PROMPT)

            call_kwargs = mock_graph.call_args.kwargs
            assert call_kwargs.get("name") == "energy_advisor"


class TestAgentInvoke:
    def test_invoke_calls_graph(self):
        with patch("agent.ChatOpenAI") as mock_llm, \
             patch("agent.create_react_agent") as mock_graph:
            from agent import Agent

            mock_llm.return_value = MagicMock()
            mock_graph_instance = MagicMock()
            mock_graph.return_value = mock_graph_instance

            agent = Agent(instructions=PROMPT)
            agent.invoke(question="Test question")

            mock_graph_instance.invoke.assert_called_once()

    def test_invoke_returns_graph_result(self):
        with patch("agent.ChatOpenAI") as mock_llm, \
             patch("agent.create_react_agent") as mock_graph:
            from agent import Agent

            mock_llm.return_value = MagicMock()
            mock_graph_instance = MagicMock()
            expected = {"messages": [MagicMock()]}
            mock_graph_instance.invoke.return_value = expected
            mock_graph.return_value = mock_graph_instance

            agent = Agent(instructions=PROMPT)
            result = agent.invoke(question="Test question")
            assert result == expected

    def test_invoke_with_context(self):
        with patch("agent.ChatOpenAI") as mock_llm, \
             patch("agent.create_react_agent") as mock_graph:
            from agent import Agent

            mock_llm.return_value = MagicMock()
            mock_graph_instance = MagicMock()
            mock_graph.return_value = mock_graph_instance

            agent = Agent(instructions=PROMPT)
            agent.invoke(question="Test", context="Location: SF")

            call_kwargs = mock_graph_instance.invoke.call_args.kwargs
            messages = call_kwargs["input"]["messages"]
            system_contexts = [
                m for m in messages if isinstance(m, tuple) and m[0] == "system"
            ]
            assert any("Location: SF" in str(m) for m in system_contexts)

    def test_invoke_without_context(self):
        with patch("agent.ChatOpenAI") as mock_llm, \
             patch("agent.create_react_agent") as mock_graph:
            from agent import Agent

            mock_llm.return_value = MagicMock()
            mock_graph_instance = MagicMock()
            mock_graph.return_value = mock_graph_instance

            agent = Agent(instructions=PROMPT)
            agent.invoke(question="Test")

            call_kwargs = mock_graph_instance.invoke.call_args.kwargs
            messages = call_kwargs["input"]["messages"]
            system_msgs = [
                m for m in messages if isinstance(m, tuple) and m[0] == "system"
            ]
            assert len(system_msgs) == 0

    def test_invoke_error_returns_error_dict(self):
        with patch("agent.ChatOpenAI") as mock_llm, \
             patch("agent.create_react_agent") as mock_graph:
            from agent import Agent

            mock_llm.return_value = MagicMock()
            mock_graph_instance = MagicMock()
            mock_graph_instance.invoke.side_effect = RuntimeError("API call failed")
            mock_graph.return_value = mock_graph_instance

            agent = Agent(instructions=PROMPT)
            result = agent.invoke(question="Test")
            assert "messages" in result
            last_msg = result["messages"][-1]
            content = last_msg.get("content") if isinstance(last_msg, dict) else str(last_msg)
            assert "error" in str(content).lower() or "Error" in str(content)

    def test_invoke_passes_question_as_user_message(self):
        with patch("agent.ChatOpenAI") as mock_llm, \
             patch("agent.create_react_agent") as mock_graph:
            from agent import Agent

            mock_llm.return_value = MagicMock()
            mock_graph_instance = MagicMock()
            mock_graph.return_value = mock_graph_instance

            agent = Agent(instructions=PROMPT)
            agent.invoke(question="What is the best time to charge my EV?")

            call_kwargs = mock_graph_instance.invoke.call_args.kwargs
            messages = call_kwargs["input"]["messages"]
            user_msgs = [
                m for m in messages if isinstance(m, tuple) and m[0] == "user"
            ]
            assert len(user_msgs) == 1
            assert "best time to charge" in str(user_msgs[0][1])


class TestAgentGetTools:
    def test_returns_tool_names(self):
        with patch("agent.ChatOpenAI"), patch("agent.create_react_agent"):
            from agent import Agent
            agent = Agent(instructions=PROMPT)
            tool_names = agent.get_agent_tools()
            assert isinstance(tool_names, list)
            assert len(tool_names) == 7
            assert "get_weather_forecast" in tool_names
            assert "get_electricity_prices" in tool_names
            assert "calculate_energy_savings" in tool_names
