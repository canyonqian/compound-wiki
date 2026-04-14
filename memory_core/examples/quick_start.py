"""
Compound Wiki Memory Core — 5 Minute Quick Start
================================================

This example shows how to add AUTOMATIC memory to ANY AI Agent
with just a few lines of code.

The key insight: You don't need to change how your Agent works.
You just wrap it with MemoryCore and it automatically:
  1. Extracts knowledge from every conversation turn
  2. Stores facts in a shared Wiki (concurrent-safe for multi-Agent)
  3. Builds a knowledge graph of relationships
  4. Uses accumulated memory to improve future responses

## Two Extraction Modes:

Mode 1: Agent-Native (RECOMMENDED, ZERO COST)
  The hosting Agent uses its OWN LLM intelligence to extract facts.
  No external API call. No extra cost. This is how you should integrate.

Mode 2: LLM Fallback (Optional)
  If no Agent is available, calls OpenAI/Anthropic/Ollama API.
  Requires API keys or local Ollama. See examples 1-4 for this mode.

Prerequisites (only needed for LLM Fallback mode):
  pip install httpx
  
For Agent-Native mode, no prerequisites at all!
"""

import asyncio
import os
import sys

# Add project root to path (quick_start is at: project_root/memory_core/examples/)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from memory_core import MemoryCore


# ============================================================
# Example 1: The simplest possible integration — @mc.hook decorator
# ============================================================

async def example_decorator():
    """Zero-code-change integration using decorator."""
    
    print("=" * 60)
    print("Example 1: @mc.hook Decorator — Zero Code Changes")
    print("=" * 60)
    
    # Initialize Memory Core
    mc = MemoryCore(wiki_path="./wiki", raw_path="./raw")
    await mc.initialize()
    
    # --- Your existing Agent function (UNCHANGED) ---
    async def my_chatbot(user_message: str) -> str:
        """Your existing AI chatbot. No changes needed."""
        
        # Simulate an LLM response (replace with your actual LLM call)
        responses = {
            "hello": "Hi! How can I help you today?",
            "i prefer typescript for frontend": (
                "Great choice! TypeScript provides type safety "
                "and better developer experience for large "
                "frontend projects."
            ),
            "we chose redis for caching": (
                "Redis is excellent for caching. Its in-memory "
                "data structures give sub-millisecond latency, "
                "and pub/sub support enables real-time features."
            ),
            "my team uses microservices": (
                "Microservices architecture allows independent "
                "deployment and scaling. Make sure you have "
                "proper observability and inter-service "
                "communication patterns."
            ),
        }
        return responses.get(user_message.lower(), 
                             f"I understand: {user_message}")
    
    # --- Just add ONE line: the decorator ---
    hooked_chat = mc.hook(my_chatbot)
    
    # Simulate a conversation
    print("\n--- Simulating Conversation ---\n")
    
    conversations = [
        ("Hello!", "Hi! How can I help you today?"),
        ("I prefer TypeScript for frontend projects", 
         "Great choice! TypeScript provides type safety..."),
        ("We chose Redis over Memcached for caching",
         "Redis is excellent for caching..."),
        ("My team uses microservices architecture",
         "Microservices architecture allows independent deployment..."),
        ("What do you know about our project?",
         None),  # This will query the Wiki!
    ]
    
    for user_msg, expected_response in conversations:
        print(f"[User] {user_msg}")
        
        if expected_response:
            # Normal chat call — memory happens automatically!
            response = await hooked_chat(user_msg)
            print(f"[AI] {response[:100]}...")
            
            # Also call remember explicitly (same thing decorator does internally)
            result = await mc.remember(user_msg, response)
            if result.facts_extracted > 0:
                print(f"   >> Auto-stored {result.facts_extracted} facts!")
        else:
            # Query mode — ask the Wiki what we know
            answer = await mc.query(user_msg)
            print(f"[Wiki] Answer: {answer[:200]}...")
        
        print()
    
    # Show final stats
    stats = await mc.get_stats()
    print("\n--- Session Statistics ---")
    print(f"Total turns processed: {stats['hook_engine']['total_turns_processed']}")
    print(f"Facts extracted & stored: {stats['hook_engine']['facts_written_to_wiki']}")
    
    await mc.shutdown()


# ============================================================
# Example 2: Manual Hook — for non-Python or custom loops
# ============================================================

async def example_manual():
    """Manual hook integration pattern."""
    
    print("\n" + "=" * 60)
    print("Example 2: Manual Hook Pattern")
    print("=" * 60)
    
    mc = MemoryCore(wiki_path="./wiki", raw_path="./raw")
    await mc.initialize()
    
    # Simulated conversation turns
    turns = [
        ("User wants dark mode UI", 
         "Noted! I'll use dark color scheme going forward."),
        ("Decision: PostgreSQL for analytics DB",
         "PostgreSQL is ideal for analytics with its powerful "
         "query optimizer and JSONB support."),
        ("TODO: Implement auth middleware by Friday",
         "Added to task list. Auth middleware is critical for security."),
    ]
    
    for user_msg, ai_response in turns:
        print(f"\nProcessing: '{user_msg[:50]}...'")
        
        # ← THE ONE LINE THAT ENABLES AUTO-MEMORY →
        result = await mc.remember(user_msg, ai_response)
        
        if result.success:
            print(f"  [OK] {result.message}")
        else:
            print(f"  [FAIL] {result.message}")
    
    await mc.shutdown()


# ============================================================
# Example 3: Context Manager — clean resource management
# ============================================================

async def example_context_manager():
    """Using async context manager for clean setup/teardown."""
    
    print("\n" + "=" * 60)
    print("Example 3: Async Context Manager")
    print("=" * 60)
    
    async with MemoryCore(wiki_path="./wiki") as mc:
        result = await mc.remember(
            "User's name is Alice, she's a backend engineer",
            "Nice to meet you, Alice! As a backend engineer, "
            "you probably work with APIs and databases."
        )
        print(f"Stored: {result.facts_written} facts")
        
        answer = await mc.query("What do we know about the user?")
        print(f"\nWiki knows:\n{answer}")


# ============================================================
# Example 4: Multi-Agent scenario
# ============================================================

async def example_multi_agent():
    """Two Agents sharing one Wiki concurrently."""
    
    print("\n" + "=" * 60)
    print("Example 4: Multi-Agent Concurrent Access")
    print("=" * 60)
    
    from memory_core.agent_sdk import AgentConfig, AgentType
    
    # Both Agents point to SAME wiki directory
    agent_a = MemoryCore(
        wiki_path="./wiki",
        agent_config=AgentConfig(
            agent_type=AgentType.CUSTOM,
            agent_id="code-reviewer-agent",
            auto_extract=True,
        )
    )
    
    agent_b = MemoryCore(
        wiki_path="./wiki",
        agent_config=AgentConfig(
            agent_type=AgentType.CUSTOM,
            agent_id="documentation-agent", 
            auto_extract=True,
        )
    )
    
    await asyncio.gather(agent_a.initialize(), agent_b.initialize())
    
    # Both agents work simultaneously
    async def agent_a_work():
        results = []
        for msg, resp in [
            ("Code review: should use async/await not callbacks",
             "Agreed. Modern JavaScript should prefer async/await."),
            ("Team decided on REST API, not GraphQL",
             "REST is simpler and sufficient for this use case."),
        ]:
            r = await agent_a.remember(msg, resp)
            results.append(r)
        return results
    
    async def agent_b_work():
        results = []
        for msg, resp in [
            ("Doc format: Markdown preferred over reStructuredText",
             "Noted. Using Markdown for all documentation."),
            ("Project uses Python 3.11+ with type hints",
             "Great practice. Type hints improve code quality."),
        ]:
            r = await agent_b.remember(msg, resp)
            results.append(r)
        return results
    
    # Run both agents concurrently — SharedWiki handles locking automatically
    results_a, results_b = await asyncio.gather(
        agent_a_work(), agent_b_work()
    )
    
    total_a = sum(r.facts_written for r in results_a)
    total_b = sum(r.facts_written for r in results_b)
    
    print(f"Agent A (code-reviewer): stored {total_a} facts")
    print(f"Agent B (documentation): stored {total_b} facts")
    print("\n[OK] Both wrote to same Wiki safely (no conflicts!)")
    
    await asyncio.gather(agent_a.shutdown(), agent_b.shutdown())


# ============================================================
# Example 5: Agent-Native Mode — ZERO Extra Cost (RECOMMENDED)
# ============================================================

async def example_agent_native():
    """
    Agent-Native Mode: The Agent uses its OWN LLM to extract facts.
    
    This is the RECOMMENDED pattern for all AI Agent integrations.
    No external API call needed. Zero extra cost.
    
    How it works in practice:
      1. User sends message to Agent
      2. Agent generates response using its LLM (normal chat)  
      3. Agent ALSO extracts facts using SAME LLM intelligence
         (no extra API call — it's part of the same conversation context)
      4. Pass extracted facts to MemoryCore → done!
    
    Cost comparison:
      LLM Fallback mode:   $0.001-0.005 per extraction (extra API call)
      Agent-Native mode:   $0.00 (uses Agent's existing LLM capability)
    """
    
    print("\n" + "=" * 60)
    print("Example 5: Agent-Native Mode — Zero Extra Cost")
    print("=" * 60)
    
    mc = MemoryCore(wiki_path="./wiki", raw_path="./raw")
    await mc.initialize()
    
    # Simulate what an ACTUAL AI Agent does:
    #
    # The Agent receives user message, generates a response,
    # and ALSO produces structured facts — all using the SAME 
    # LLM intelligence it already has.
    
    agent_conversations = [
        {
            "user": "I think we should use PostgreSQL for the analytics database",
            "assistant": (
                "PostgreSQL is an excellent choice for analytics workloads. "
                "Its query optimizer handles complex aggregations efficiently, "
                "and JSONB support gives you flexibility for semi-structured data."
            ),
            "agent_extracted_facts": [
                {"fact_type": "decision", 
                 "content": "User chose PostgreSQL for the analytics database",
                 "confidence": 0.95,
                 "tags": ["database", "decision"],
                 "entities_mentioned": ["PostgreSQL"]},
                {"fact_type": "concept", 
                 "content": "PostgreSQL query optimizer handles complex aggregations well",
                 "confidence": 0.9,
                 "tags": ["database", "performance"],
                 "entities_mentioned": ["PostgreSQL"]},
            ],
        },
        {
            "user": "Our team prefers async/await over callbacks, we're on Node 20",
            "assistant": (
                "That is great! With Node 20 you have full native support for "
                "async/await without transpilation. I'll use async/await style."
            ),
            "agent_extracted_facts": [
                {"fact_type": "preference", 
                 "content": "Team prefers async/await over callbacks",
                 "confidence": 0.95,
                 "tags": ["preference", "code-style"],
                 "entities_mentioned": []},
                {"fact_type": "fact", 
                 "content": "Project runtime is Node.js version 20+",
                 "confidence": 1.0,
                 "tags": ["runtime", "environment"],
                 "entities_mentioned": ["Node.js"]},
            ],
        },
        {
            "user": "We need to implement JWT authentication middleware by Friday",
            "assistant": (
                "Understood. I'll help with JWT auth middleware including token "
                "generation, validation, and refresh rotation."
            ),
            "agent_extracted_facts": [
                {"fact_type": "task", 
                 "content": "Implement JWT authentication middleware by Friday",
                 "confidence": 0.9,
                 "tags": ["task", "deadline", "auth"],
                 "entities_mentioned": ["JWT"]},
                {"fact_type": "decision", 
                 "content": "Using JWT for authentication with refresh token rotation",
                 "confidence": 0.85,
                 "tags": ["decision", "auth", "security"],
                 "entities_mentioned": ["JWT"]},
            ],
        },
    ]
    
    for turn in agent_conversations:
        user_msg = turn["user"]
        ai_resp = turn["assistant"]
        agent_facts = turn["agent_extracted_facts"]
        
        print(f"\n[User] {user_msg[:70]}...")
        
        # === THIS IS THE KEY LINE FOR AGENT-NATIVE MODE ===
        result = await mc.hook_engine.on_turn_end_agent(
            user_message=user_msg,
            assistant_response=ai_resp,
            agent_extracted_facts=agent_facts,  # <-- From Agent itself!
        )
        
        if result.fact_count > 0:
            print(f"  >> [Agent-Native] Extracted {result.fact_count} facts")
            for fact in result.facts:
                print(f"     - [{fact.fact_type.value}] {fact.content[:60]}...")
        else:
            print(f"  >> No facts ({result.trigger_reason})")
    
    stats = mc.extractor.stats
    print(f"\n--- Agent-Native Stats ---")
    print(f"Agent-native extractions: {stats.get('agent_native_count', 0)}")
    print(f"LLM fallback extractions:  {stats.get('llm_fallback_count', 0)}")
    print(f"Total facts found:        {stats.get('total_facts_found', 0)}")
    
    print("\n[OK] Agent-Native mode: 0 extra API calls, 0 extra cost!")
    
    await mc.shutdown()


# ============================================================
# Main entry point
# ============================================================

async def main():
    print("""
============================================================
     Compound Wiki Memory Core -- Quick Start Demo
     
     Ex 1-4: LLM Fallback Mode (needs API key / Ollama)
     Ex 5:   Agent-Native Mode   (ZERO cost, recommended!)
============================================================
    """)
    
    os.makedirs("./wiki/concept", exist_ok=True)
    os.makedirs("./wiki/entity", exist_ok=True)
    os.makedirs("./wiki/synthesis", exist_ok=True)
    os.makedirs("./raw", exist_ok=True)
    
    try:
        await example_decorator()
        await example_manual()
        await example_context_manager()
        await example_multi_agent()
        await example_agent_native()  # <-- NEW!
        
        print("\n" + "=" * 60)
        print("All examples completed successfully!")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n[ERROR] {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
