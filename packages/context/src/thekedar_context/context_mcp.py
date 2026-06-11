#!/usr/bin/env python3
"""Standard I/O MCP server for Thekedar Context Index dynamic retrieval."""

from __future__ import annotations

import json
import sys
import logging
from typing import Any

from thekedar_shared.settings import get_settings
from thekedar_shared.db import init_db
from thekedar_context.retriever import ContextRetriever
from thekedar_context.schemas import ContextQuery

# Ensure stdout is used strictly for JSON-RPC messages and stderr for logs
logging.basicConfig(level=logging.INFO, stream=sys.stderr)
logger = logging.getLogger("thekedar-context-mcp")


def handle_initialize(msg_id: int) -> dict[str, Any]:
    return {
        "jsonrpc": "2.0",
        "id": msg_id,
        "result": {
            "protocolVersion": "2024-11-05",
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "thekedar-context-mcp", "version": "0.1.0"},
        },
    }


def handle_tools_list(msg_id: int) -> dict[str, Any]:
    return {
        "jsonrpc": "2.0",
        "id": msg_id,
        "result": {
            "tools": [
                {
                    "name": "search_context",
                    "description": "Query the indexed codebase Context Index for symbols, documents, and security details.",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "tenant_id": {"type": "string", "description": "The tenant identifier"},
                            "repo": {"type": "string", "description": "The repository identifier (e.g. org/repo)"},
                            "keywords": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "List of keywords or symbols to search for",
                            },
                            "chunk_types": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Optional filters: doc, symbol, security, service_graph",
                            },
                        },
                        "required": ["tenant_id", "repo", "keywords"],
                    },
                }
            ]
        },
    }


def handle_tools_call(msg_id: int, params: dict[str, Any]) -> dict[str, Any]:
    tool_name = params.get("name")
    args = params.get("arguments", {})

    if tool_name != "search_context":
        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "error": {"code": -32601, "message": f"Method not found: {tool_name}"},
        }

    tenant_id = args.get("tenant_id")
    repo = args.get("repo")
    keywords = args.get("keywords", [])
    chunk_types = args.get("chunk_types", [])

    if not tenant_id or not repo or not keywords:
        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {
                "isError": True,
                "content": [
                    {
                        "type": "text",
                        "text": "Missing required arguments: tenant_id, repo, keywords",
                    }
                ],
            },
        }

    # Query local context index
    try:
        settings = get_settings()
        session_factory = init_db(settings.database_url)
        session = session_factory()
        try:
            retriever = ContextRetriever(settings)
            query_obj = ContextQuery(
                tenant_id=tenant_id,
                repo=repo,
                keywords=keywords,
                chunk_types=chunk_types,
            )
            hits = retriever.query(session, query_obj)

            # Limit results based on setting
            max_results = settings.context_retval_max_results
            hits = hits[:max_results]

            # Format result text
            result_text = json.dumps(hits, indent=2)
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {
                    "content": [{"type": "text", "text": result_text}],
                },
            }
        finally:
            session.close()
    except Exception as e:
        logger.exception("Error executing context query")
        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {
                "isError": True,
                "content": [{"type": "text", "text": f"Error querying index: {str(e)}"}],
            },
        }


def main() -> None:
    logger.info("Thekedar Context MCP Server started on standard I/O")
    for line in sys.stdin:
        if not line.strip():
            continue
        try:
            req = json.loads(line)
        except json.JSONDecodeError:
            logger.warning("Malformed JSON received")
            continue

        method = req.get("method")
        msg_id = req.get("id")

        if method == "initialize":
            res = handle_initialize(msg_id)
        elif method == "initialized":
            continue
        elif method == "tools/list":
            res = handle_tools_list(msg_id)
        elif method == "tools/call":
            res = handle_tools_call(msg_id, req.get("params", {}))
        else:
            res = {
                "jsonrpc": "2.0",
                "id": msg_id,
                "error": {"code": -32601, "message": f"Method not found: {method}"},
            }

        # Write output followed by newline and flush
        sys.stdout.write(json.dumps(res) + "\n")
        sys.stdout.flush()


if __name__ == "__main__":
    main()
