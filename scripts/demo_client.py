import asyncio
import json
import logging

from fastmcp import Client
from fastmcp.client.logging import LogMessage

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)


logger = logging.getLogger(__name__)

LOGGING_LEVEL_MAP = logging.getLevelNamesMapping()


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
                "auth": "oauth",
            },
        }
    }

    client = Client(
        transport=client_config,
        auto_initialize=True,
        timeout=25000,
        log_handler=log_handler,
        progress_handler=progress_handler,
    )

    async with client:
        await client.ping()

        # DEBUG only, uncomment to print the access token
        # token_obj = await client.transport.transport.auth.token_storage_adapter.get_tokens()  # type: ignore  # noqa: ERA001
        # logger.info(token_obj.access_token)  # noqa: ERA001

        prompts = await client.list_prompts()
        logger.info("Available prompts: %s", prompts)

        tools = await client.list_tools()
        logger.info("Available tools: %s", tools)

        search_result = await client.call_tool(
            "search",
            {"query": "Best technology stocks for 2026"},
        )

        logger.info(
            "Search result:\n%s", json.dumps(search_result.data, indent=2)
        )


if __name__ == "__main__":
    asyncio.run(main())
