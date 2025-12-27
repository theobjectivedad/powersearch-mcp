# AGENTS.md

## Golden Rules

AI Agents are required to follow these **Golden Rules** at all times.

* **Humans are Sometimes Wrong**. Always question assumptions, even when they come from a human. If something seems off, raise your concerns, push back, clarify assumptions, start a discussion.
**Simplicity is the ultimate sophistication**. Architecture, design, testing/testability, and implementation maximize simplicity for all users, developers, and maintainers.
* **Challenge Assumptions**: Challenge your initial assumptions about how things "should" be. Revisit and refine to eliminate unnecessary complexity.
* **Developer Ergonomics**: All changes need to make intuitive and logical sense to human maintainers. If developers have too many touch points when making updates, the design has failed. When implementing new features, start with the developer experience and work backwards into functional requirements. Before making a change, ask yourself "how could this change cause confusion to a human maintainer" and do your best to accommodate within reason.
* **Maintainability First**: If engineers sustaining the application don't have the right visibility to troubleshoot in production, the design has failed.
* **User Experience Excellence**: If end users find features to be hard to use, slow, and/or unreliable, the design has failed.
* **Ruthless Prioritization**: Implementing unnecessary features and complexity that add minimal value to the developer and end user experience must be challenged.
* **Seamless Integration**: Every component must work together seamlessly. Quality must go all the way through.
* **Hidden Beauty**: Remember, the code that nobody sees and "just works" must be as beautiful as the parts that are regularly updated.
* **Obsess Over Details**: Obsess over every aspect of the implementation, from interfaces and clarity in naming to internal structure; perfection in details matter, quality must go all the way through, and the parts that are regularly seen must be as beautiful as the ones that are seldom seen.
* **Locality of Function**: A human maintainer should be able to understand and modify a unit of functionality without mental gymnastics or excessive navigation. The closer related logic lives together, the easier it is to reason about, test, and evolve. Avoid deep hierarchies, hidden abstractions, or scattered definitions that fragment understanding. Favor clear, co-located logic over theoretical purity.
* **The Fewer number of end-user decisions the better**: If you better understand the full context of the problem being solved then you can be a better service provider. For example if I hire a lawyer, I don't want them to ask me every question about how to file my paperwork, I want them to understand the context and make the right decisions on my behalf. The same applies to software design. The fewer number of end-user decisions the better.
* **Everything "Just Works"**: Idempotent ops, deterministic behavior, stable interfaces, zero-surprise setup, etc. If a step can be automated, automate it.

## Methodology

### Research FastMCP Best Practices

Before making any changes to the FastMCP framework, you **MUST** research relevant best practices and relevant topics in the FastMCP documentation via the `SearchFastMCP` tool. As-needed, you will read external references via the `fetch` tool. Some example FastMCP topics include:

* **MCP Tools**: Expose functions as executable capabilities
* **MCP Resources**: Expose data sources and dynamic content generators
* **MCP Prompts**: Create reusable, parameterized prompt templates for MCP clients to discover
* **Server composition**: Combine multiple FastMCP servers into a single, larger application using mounting and importing.
* **FastMCP Context**: Access MCP capabilities like logging, progress, and resources
* **Elicitation**: Request structured input from users during tool execution through the MCP context
* **Icons**: Add visual icons to your servers, tools, resources, and prompts
* **Logging**: Send log messages back to MCP clients through the context.
* **MCP Middleware**: Add cross-cutting functionality to your MCP server with middleware that can inspect, modify, and respond to all MCP requests and responses. Some out of the box capabilities include: *authentication and authorization*, *logging and monitoring*, *rate limiting*, *request/response transformation*, *caching*, and *error handling*
* **Progress Reporting**: Update clients on the progress of long-running operations through the MCP context.
* **Proxy Servers**: Use FastMCP to act as an intermediary or change transport for other MCP servers.
* **LLM Sampling**: Request LLM text generation from the client or a configured provider through the MCP context.
* **Storage Backends**: Configure persistent and distributed storage for caching and OAuth state management; supported backends are: *in-memory*, *disk*, and *Redis*.
* **Background Tasks**: Run long-running operations asynchronously with progress tracking
* **Authentication**: MCP server security implementation with various methods such as API keys and OAuth 2.1 integration with external identity providers. FastMCP offers several authentication providers including: `TokenVerifier`, `RemoteAuthProvider`, `OAuthProxy`, and `OAuthProvider`
* **MCP Transports**: *STDIO*, *Streamable HTTP*, and *SSE* (Legacy only)
* **HTTP Deployment Topics**: *uvicorn / ASGI applications*, *custom paths*, *authentication*, *health checks*, *CORS*, *mounting authentication servers*, *horizontal scaling*, *stateless mode*, and *OAuth token security*
* **FastMCP project configuration**: `fastmcp.json` file structure (use for portable, declarative project configuration).
* **Tool Transformation**: Tool transformation allows you to create new, enhanced tools from existing ones. This powerful feature enables you to adapt tools for different contexts, simplify complex interfaces, or add custom logic without duplicating code.
* **FastMCP CLI**:  exposed via the `fastmcp` CLI command
* **Testing FastMCP server**: Using `pytest` and fixtures

Only after you complete your research should you make changes to the PowerSearch MCP.

### Task Management

Use the `todo` tool generously to manage your development tasks: planning, implementation, testing, etc.

### Running

To run the PowerSearch MCP server locally, use the following commands:

STDIO transport:

```shell
uv run fastmcp run fastmcp.json --skip-source --skip-env
```

Streamable HTTP transport:

```shell
uv run fastmcp run fastmcp.json --skip-source --skip-env
```

### Testing

* New code requires new tests; bug fixes must include a regression test (write it to fail first).
* Tests must be deterministic and independent; replace external systems with fakes/contract tests.
* Include ≥1 happy path and ≥1 failure path in pytests.
* Proactively assess risks from concurrency/locks/retries (duplication, deadlocks, etc.).
* Tests also serve as usage examples; include boundary and failure cases.

### Pre-Commit Checks

After making updates and before handing control back to the user, ensure that the pre‑commit checks all pass, run: `uv run pre-commit run --all-files`

### Anti-Patterns

* Don't modify code without reading and understanding the entire context + relevant FastMCP documentation.
* Don't ignore failures or warnings.
* Don't introduce unjustified optimization or abstraction.
* Don't overuse broad exceptions.
