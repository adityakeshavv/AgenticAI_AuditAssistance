import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "backend"))

from agents.router_agent import QueryRouterAgent
from agents.transaction_agent import TransactionAgent

router = QueryRouterAgent()

query = input("Enter Query: ")

route = router.route(query)

if route["agent"] == "transaction_agent":
    agent = TransactionAgent()
    result = agent.run(query, routing_info=route)
else:
    result = {
        "message": "No matching agent found"
    }

print(result)
