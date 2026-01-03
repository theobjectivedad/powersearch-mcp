import asyncio
import json
import logging
import os
from typing import Any

from dotenv import load_dotenv
from fastmcp import Client
from fastmcp.client.logging import LogMessage
from fastmcp.client.sampling import (
    RequestContext,
    SamplingMessage,
    SamplingParams,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)


logger = logging.getLogger(__name__)

LOGGING_LEVEL_MAP = logging.getLevelNamesMapping()


load_dotenv()


def get_default_model() -> str:
    model = os.getenv("OPENAI_DEFAULT_MODEL")
    if not model:
        raise RuntimeError(
            "OPENAI_DEFAULT_MODEL is not set; update your environment or .env"
        )
    return model


async def log_handler(message: LogMessage) -> None:
    msg = message.data.get("msg")
    extra = message.data.get("extra")

    level = LOGGING_LEVEL_MAP.get(message.level.upper(), logging.INFO)

    logger.log(level, msg, extra=extra)


async def progress_handler(
    progress: float, total: float | None, message: str | None
) -> None:
    derived_message = message or "(NO MESSAGE PROVIDED)"
    if total is not None:
        logger.info(
            "Progress: %.1f%% - %s", (progress / total) * 100, derived_message
        )
    else:
        logger.info("Progress: %s - %s", progress, derived_message)


async def sampling_handler(
    messages: list[SamplingMessage],
    _params: SamplingParams,
    _context: RequestContext[Any, Any, Any],
) -> str:
    logger.info("Received messages for sampling:")
    for msg in messages:
        logger.info("Role: %s, Content: %s", msg.role, msg.content)

    return "Demo Sampling Response"


async def main() -> None:
    """Connect to PowerSearch with streamable HTTP.

    To use JWT instead of OAuth2, set ``client_config`` to:

    ```json
    {
      "mcpServers": {
        "powersearch": {
          "transport": "streamable-http",
          "url": "http://127.0.0.1:8099/mcp",
          "headers": {"Authorization": "Bearer token"},
          "auth": "THE_JWT_ACCESS_TOKEN"
        }
      }
    }
    ```
    """

    client_config = {
        "mcpServers": {
            "powersearch": {
                "transport": "streamable-http",
                "url": "http://127.0.0.1:8099/mcp",
            },
        }
    }

    client = Client(
        name="demo_client",
        transport=client_config,
        timeout=25000,
        log_handler=log_handler,
        progress_handler=progress_handler,
    )

    async with client as session:
        await session.ping()

        # DEBUG only, uncomment to print the access token
        # token_obj = await session.transport.transport.auth.token_storage_adapter.get_tokens()  # type: ignore  # noqa: ERA001
        # logger.info(token_obj.access_token)  # noqa: ERA001

        prompts = await session.list_prompts()
        logger.info("Detected prompts: %s", [x.name for x in prompts])

        tools = await session.list_tools()
        logger.info("Detected tools: %s", [x.name for x in tools])

        standard_search_result = await session.call_tool(
            "search",
            {"query": "Best technology stocks for 2026"},
        )

        logger.info(
            "Standard search result:\n%s",
            json.dumps(standard_search_result.data, indent=2),
        )

        summary_search_result = await session.call_tool(
            "summarize_search",
            {
                "query": "Best technology stocks for 2026",
                "intent": "Trading strategy research for personal portfolio.",
                "map_reduce": False,
            },
        )

        logger.info(
            "Summary search result:\n%s",
            json.dumps(
                json.loads(summary_search_result.content[0].text), indent=2
            ),
        )


if __name__ == "__main__":
    asyncio.run(main())
