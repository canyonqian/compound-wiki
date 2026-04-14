from __future__ import annotations
"""
Hook Engine — Event-Driven Automatic Memory
============================================

The Hook Engine makes memory automatic by hooking into the Agent's
conversation lifecycle events:

  on_message(user_msg)        → Check if worth extracting
  on_response(assistant_reply) → Analyze response for knowledge
  on_turn_end(user, assistant) → Full extraction + Wiki write
  on_session_end(history)      → Session summary extraction

This replaces "user clicks button → save" with:
  "Conversation happens → knowledge automatically extracted"

Integration patterns:

  # Pattern 1: Wrap your Agent's chat function
  async def chat(user_message):
      response = await llm.generate(user_message)
      await hook_engine.on_turn_end(user_message, response)
      return response

  # Pattern 2: Use as a middleware
  app.use(MemoryHook(hook_engine))

  # Pattern 3: Claude Code / Cursor tool integration
  # The Agent SDK (agent_sdk.py) handles this automatically

"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple, Awaitable, TYPE_CHECKING
from datetime import datetime
from collections import deque

if TYPE_CHECKING:
    from .extractor import ExtractionResult, FactType, ExtractedFact

logger = logging.getLogger("memory_core.hook_engine")


class HookEvent(Enum):
    """Types of conversation lifecycle events."""
    
    # Core conversation events
    ON_MESSAGE = "on_message"           # User sent a message
    ON_RESPONSE = "on_response"         # Assistant generated a response
    ON_TURN_END = "on_turn_end"         # Complete turn finished
    ON_SESSION_START = "on_session_start"   # New conversation session
    ON_SESSION_END = "on_session_end"     # Session ended
    
    # Knowledge events
    FACT_EXTRACTED = "fact_extracted"   # A fact was extracted
    FACT_WRITTEN = "fact_written"       # A fact was written to Wiki
    
    # System events  
    ERROR = "error"                     # Something went wrong
    THROTTLE = "throttle"               # Rate limited


@dataclass
class HookContext:
    """Context passed through the hook pipeline."""
    
    event: HookEvent
    user_message: str = ""
    assistant_response: str = ""
    turn_number: int = 0
    session_id: str = ""
    agent_id: str = "default"
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    
    @property
    def combined_text(self) -> str:
        return f"{self.user_message} {self.assistant_response}".strip()


@dataclass
class HookResult:
    """Result from a hook handler."""
    
    handled: bool = False
    should_propagate: bool = True       # Continue to next handler?
    data: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None


# Type alias for hook handlers
HookHandler = Callable[[HookContext], Awaitable[HookResult]]


class ThrottleController:
    """
    Rate limiting for extraction to prevent API abuse.
    
    Smart throttling that adapts based on:
    - Time since last extraction
    - Content novelty (vs recent extractions)
    - Token budget
    """
    
    def __init__(self, 
                 min_interval_seconds: float = 30.0,
                 max_per_hour: int = 120,
                 max_per_session: int = 500):
        self.min_interval = min_interval_seconds
        self.max_per_hour = max_per_hour
        self.max_per_session = max_per_session
        
        self._last_extraction_time: float = 0
        self._hourly_count: deque = deque(maxlen=max_per_hour * 2)
        self._session_count: int = 0
        self._lock = asyncio.Lock()
    
    async def check_and_record(self) -> Tuple[bool, str]:
        """Check if we can extract now. Returns (allowed, reason)."""
        async with self._lock:
            now = time.time()
            
            # Minimum interval check
            elapsed = now - self._last_extraction_time
            if elapsed < self.min_interval:
                wait = self.min_interval - elapsed
                return False, f"throttle_min_interval (wait {wait:.1f}s)"
            
            # Hourly rate limit
            cutoff = now - 3600
            while self._hourly_count and self._hourly_count[0] < cutoff:
                self._hourly_count.popleft()
            
            if len(self._hourly_count) >= self.max_per_hour:
                return False, f"throttle_hourly_limit ({self.max_per_hour}/hr)"
            
            # Session limit
            if self._session_count >= self.max_per_session:
                return False, f"throttle_session_limit ({self.max_per_session}/session)"
            
            # Record this extraction
            self._last_extraction_time = now
            self._hourly_count.append(now)
            self._session_count += 1
            
            return True, "ok"
    
    def reset_session(self):
        """Reset session counter."""
        self._session_count = 0


class ConversationBuffer:
    """
    Sliding window buffer of recent conversation turns.
    
    Used by the extractor to provide context for disambiguation.
    Maintains last N turns with their messages.
    """
    
    def __init__(self, max_turns: int = 20):
        self.max_turns = max_turns
        self._turns: List[Dict[str, str]] = deque(maxlen=max_turns)
        self._lock = asyncio.Lock()
    
    async def add_turn(self, user_message: str, assistant_response: str,
                       turn_number: int = 0) -> Dict:
        """Add a completed conversation turn to the buffer."""
        turn = {
            "turn": turn_number,
            "role": "user",
            "content": user_message,
            "response": assistant_response,
            "timestamp": datetime.utcnow().isoformat(),
        }
        async with self._lock:
            self._turns.append(turn)
        return turn
    
    async def get_recent(self, count: int = 5) -> List[Dict]:
        """Get the most recent N turns."""
        async with self._lock:
            return list(self._turns)[-count:]
    
    async def get_all(self) -> List[Dict]:
        """Get all buffered turns."""
        async with self._lock:
            return list(self._turns)
    
    @property
    def turn_count(self) -> int:
        return len(self._turns)
    
    def clear(self):
        self._turns.clear()


class HookEngine:
    """
    The central event dispatcher for automatic memory.
    
    Hooks into an AI Agent's conversation loop and automatically:
    1. Detects when conversations contain valuable information
    2. Extracts structured facts using LLM
    3. Deduplicates against existing Wiki content
    4. Writes new/updated facts to the shared Wiki
    
    Usage:
        engine = HookEngine(config=config)
        
        # In your Agent's main loop:
        while True:
            user_input = await get_user_input()
            response = await generate_response(user_input)
            
            # ← This one line enables automatic memory
            await engine.on_turn_end(user_input, response)
            
            print(response)
    """
    
    def __init__(self, config=None, extractor=None, deduplicator=None, 
                 shared_wiki=None, graph=None):
        from .config import MemoryConfig, DEFAULT_CONFIG
        
        self.config = config or DEFAULT_CONFIG
        self.extractor = extractor
        self.deduplicator = deduplicator
        self.shared_wiki = shared_wiki
        self.graph = graph
        
        # Internal components
        self.throttle = ThrottleController(
            min_interval_seconds=15.0,  # At least 15s between extractions
            max_per_hour=120,
            max_per_session=500,
        )
        self.buffer = ConversationBuffer(max_turns=20)
        
        # Registered hook handlers (extension point)
        self._handlers: Dict[HookEvent, List[HookHandler]] = {}
        
        # Statistics
        self._stats = {
            "total_turns_processed": 0,
            "extractions_triggered": 0,
            "facts_written_to_wiki": 0,
            "facts_deduplicated_away": 0,
            "errors": 0,
            "session_start_time": None,
        }
        
        # State
        self._running = False
        self._session_id: str = ""
        logger.info("HookEngine initialized")
    
    # ============================================================
    # MAIN HOOK METHODS — Call these from your Agent's conversation loop
    # ============================================================
    
    async def on_session_start(self, agent_id: str = "default",
                                metadata: Dict = None) -> None:
        """
        Called when a new conversation session begins.
        
        Resets per-session state and prepares for memory collection.
        """
        self._session_id = f"{agent_id}-{int(time.time())}"
        self._running = True
        self.throttle.reset_session()
        self._stats["session_start_time"] = datetime.utcnow().isoformat()
        
        ctx = HookContext(
            event=HookEvent.ON_SESSION_START,
            session_id=self._session_id,
            agent_id=agent_id,
            metadata=metadata or {},
        )
        await self._dispatch(ctx)
        logger.info(f"Session started: {self._session_id}")
    
    async def on_message(self, user_message: str) -> HookContext:
        """
        Called when the user sends a message (before response generation).
        
        Pre-analysis phase — checks if the incoming message looks like
        it will produce extractable content.
        """
        ctx = HookContext(
            event=HookEvent.ON_MESSAGE,
            user_message=user_message,
            session_id=self._session_id,
            turn_number=self.buffer.turn_count + 1,
        )
        await self._dispatch(ctx)
        return ctx
    
    async def on_response(self, assistant_response: str,
                          user_context: HookContext = None) -> HookContext:
        """
        Called when the assistant generates a response.
        
        Post-generation analysis — examines the response for knowledge.
        """
        ctx = user_context or HookContext(
            event=HookEvent.ON_RESPONSE,
            session_id=self._session_id,
        )
        ctx.event = HookEvent.ON_RESPONSE
        ctx.assistant_response = assistant_response
        
        await self._dispatch(ctx)
        return ctx
    
    async def on_turn_end(self, user_message: str,
                          assistant_response: str,
                          force_extract: bool = False) -> ExtractionResult:
        """
        THE MAIN HOOK — Called after each complete conversation turn.
        
        This is where the magic happens (LLM Fallback Mode):
        1. Buffer the turn in conversation history
        2. Check throttle limits
        3. Run fact extractor (calls external LLM API)
        4. Deduplicate results
        5. Write unique facts to shared Wiki
        6. Update knowledge graph
        
        NOTE: For Agent-Native mode (zero extra cost), use 
        on_turn_end_agent() instead.
        
        Parameters:
            user_message: What the user said
            assistant_response: What the AI replied
            force_extract: Bypass throttle (e.g., explicit "remember")
        
        Returns:
            ExtractionResult with details of what happened
        """
        from .extractor import ExtractionResult
        
        self._stats["total_turns_processed"] += 1
        
        # Step 1: Buffer this turn
        await self.buffer.add_turn(
            user_message, assistant_response,
            turn_number=self._stats["total_turns_processed"]
        )
        
        # Create context
        ctx = HookContext(
            event=HookEvent.ON_TURN_END,
            user_message=user_message,
            assistant_response=assistant_response,
            session_id=self._session_id,
            turn_number=self._stats["total_turns_processed"],
        )
        
        # Step 2: Dispatch to custom handlers
        await self._dispatch(ctx)
        
        # Step 3: Quick exit if no extractor configured
        if not self.extractor:
            result = ExtractionResult(should_extract=False, 
                                       trigger_reason="no_extractor")
            result.processing_time_ms = 0.1
            return result
        
        # Step 4: Throttle check (unless forced)
        if not force_extract:
            allowed, reason = await self.throttle.check_and_record()
            if not allowed:
                logger.debug(f"Throttled: {reason}")
                result = ExtractionResult(should_extract=False,
                                          trigger_reason=f"throttled:{reason}")
                result.processing_time_ms = 0.1
                return result
        
        # Step 5: Get recent history for context
        recent_history = await self.buffer.get_recent(count=6)
        
        # Step 6: RUN EXTRACTION via LLM Fallback (external API call)
        try:
            extraction_result = await self.extractor.extract(
                user_message=user_message,
                assistant_response=assistant_response,
                history=recent_history,
                agent_id=ctx.agent_id,
            )
        except Exception as e:
            logger.error(f"Extraction failed in on_turn_end: {e}")
            self._stats["errors"] += 1
            extraction_result = ExtractionResult(
                should_extract=False,
                trigger_reason=f"extraction_error:{e}",
            )
        
        # Step 7-9: Deduplicate → Write to Wiki → Track stats
        return await self._process_extraction_result(extraction_result, ctx)
    
    async def on_turn_end_agent(
        self,
        user_message: str,
        assistant_response: str,
        agent_extracted_facts: Optional[List[Dict]] = None,
        force_extract: bool = False,
    ) -> ExtractionResult:
        """
        AGENT-NATIVE MODE — The hosting Agent provides its own extracted facts.
        
        This is the RECOMMENDED mode for all AI Agent integrations.
        The Agent uses its OWN LLM intelligence (the same one it uses to chat)
        to extract facts from the conversation. No external API needed. Zero cost.
        
        How it works inside an Agent's chat loop:
        
            # 1. Agent generates response normally
            response = await my_llm.chat(user_message)
            
            # 2. Agent ALSO extracts facts (using SAME LLM, no extra API!)
            #    The extraction prompt is designed for any LLM to understand
            raw_facts = await my_llm.structured_output(
                system_prompt=EXTRACTION_PROMPT,
                user_prompt=format_conversation(user_message, response),
                response_format="json_object"
            )
            # raw_facts = [{"fact_type": "decision", "content": "...", ...}]
            
            # 3. Pass to MemoryCore — done!
            result = await hook_engine.on_turn_end_agent(
                user_message=user_message,
                assistant_response=response,
                agent_extracted_facts=raw_facts,
            )
            # Facts are now deduplicated and written to Wiki automatically
        
        Parameters:
            user_message: What the user said
            assistant_response: What the Agent replied
            agent_extracted_facts: Pre-extracted facts from the Agent itself
                Each dict: {"fact_type": "decision|fact|concept|preference|task|entity",
                           "content": "...", "confidence": 0.0-1.0, 
                           "tags": [...], "entities_mentioned": [...]}
                If None or empty, falls back to rule-based check only
            force_extract: Bypass throttle
        
        Returns:
            ExtractionResult with details of what happened
        """
        from .extractor import ExtractionResult
        
        self._stats["total_turns_processed"] += 1
        
        # Step 1: Buffer this turn
        await self.buffer.add_turn(
            user_message, assistant_response,
            turn_number=self._stats["total_turns_processed"]
        )
        
        ctx = HookContext(
            event=HookEvent.ON_TURN_END,
            user_message=user_message,
            assistant_response=assistant_response,
            session_id=self._session_id,
            turn_number=self._stats["total_turns_processed"],
        )
        
        await self._dispatch(ctx)
        
        # Step 2: Quick exit if no extractor
        if not self.extractor:
            result = ExtractionResult(should_extract=False,
                                       trigger_reason="no_extractor",
                                       mode="agent_native")
            result.processing_time_ms = 0.1
            return result
        
        # Step 3: Throttle check
        if not force_extract:
            allowed, reason = await self.throttle.check_and_record()
            if not allowed:
                logger.debug(f"[Agent-Native] Throttled: {reason}")
                result = ExtractionResult(should_extract=False,
                                          trigger_reason=f"throttled:{reason}",
                                          mode="agent_native")
                result.processing_time_ms = 0.1
                return result
        
        # Step 4: Use Agent-Native extraction (ZERO extra LLM calls!)
        try:
            if self.extractor:
                extraction_result = self.extractor.extract_from_agent(
                    user_message=user_message,
                    assistant_response=assistant_response,
                    extracted_facts=agent_extracted_facts,
                    agent_id=ctx.agent_id,
                    turn_id=f"turn_{self._stats['total_turns_processed']}",
                )
            else:
                extraction_result = ExtractionResult(
                    should_extract=False,
                    trigger_reason="no_extractor",
                    mode="agent_native",
                )
        except Exception as e:
            logger.error(f"[Agent-Native] Extraction failed: {e}")
            self._stats["errors"] += 1
            extraction_result = ExtractionResult(
                should_extract=False,
                trigger_reason=f"extraction_error:{e}",
                mode="agent_native",
            )
        
        # Step 5-7: Deduplicate → Write to Wiki → Track stats
        return await self._process_extraction_result(extraction_result, ctx)
    
    async def _process_extraction_result(
        self, 
        extraction_result: ExtractionResult, 
        ctx: HookContext,
    ) -> ExtractionResult:
        """Shared post-processing pipeline: dedup → write → track."""
        
        # Deduplicate
        if extraction_result.facts and self.deduplicator:
            dedup_result = await self.deduplicator.deduplicate(
                extraction_result.facts
            )
            extraction_result.facts = dedup_result.unique_facts
            
            stats_key = "facts_deduplicated_away"
            self._stats[stats_key] = self._stats.get(stats_key, 0) + \
                                     len(dedup_result.duplicate_facts)
            
            if dedup_result.superseded_facts:
                logger.info(f"Superseded {len(dedup_result.superseded_facts)} old facts")
        
        # Write to Wiki
        if extraction_result.facts and self.shared_wiki:
            try:
                written = await self.shared_wiki.write_facts(
                    extraction_result.facts,
                    agent_id=ctx.agent_id,
                    source="auto_hook",
                )
                self._stats["facts_written_to_wiki"] += written
                
                # Update knowledge graph
                if self.graph and written > 0:
                    await self.graph.add_facts(extraction_result.facts)
                    
            except Exception as e:
                logger.error(f"Wiki write failed: {e}")
                self._stats["errors"] += 1
        
        # Track stats
        if extraction_result.should_extract:
            self._stats["extractions_triggered"] += 1
        
        # Log summary if notable
        if extraction_result.fact_count > 0:
            logger.info(
                f"[Turn #{ctx.turn_number}] {extraction_result.summary()} "
                f"({extraction_result.processing_time_ms:.0f}ms)"
            )
        
        return extraction_result
    
    async def on_session_end(self, session_summary: str = "") -> Dict:
        """
        Called when a conversation session ends.
        
        Performs final cleanup and optionally extracts a session-level
        summary/overview fact for long-term memory.
        """
        self._running = False
        
        ctx = HookContext(
            event=HookEvent.ON_SESSION_END,
            session_id=self._session_id,
            metadata={"session_summary": session_summary},
        )
        await self._dispatch(ctx)
        
        # Generate session statistics
        session_stats = {
            **self._stats,
            "session_id": self._session_id,
            "session_duration_seconds": 0,
            "buffered_turns": self.buffer.turn_count,
        }
        
        if self._stats.get("session_start_time"):
            try:
                start = datetime.fromisoformat(self._stats["session_start_time"])
                session_stats["session_duration_seconds"] = \
                    (datetime.utcnow() - start).total_seconds()
            except Exception:
                pass
        
        logger.info(
            f"Session ended: {self._stats['total_turns_processed']} turns, "
            f"{self._stats['facts_written_to_wiki']} facts written, "
            f"{self._stats['errors']} errors"
        )
        
        # Clear buffer
        self.buffer.clear()
        
        return session_stats
    
    # ============================================================
    # EVENT DISPATCH
    # ============================================================
    
    def on(self, event: HookEvent, handler: HookHandler) -> None:
        """Register a custom hook handler for an event type."""
        if event not in self._handlers:
            self._handlers[event] = []
        self._handlers[event].append(handler)
        logger.debug(f"Registered handler for {event.value}")
    
    async def _dispatch(self, ctx: HookContext) -> List[HookResult]:
        """Dispatch context to all registered handlers for its event."""
        results = []
        handlers = self._handlers.get(ctx.event, [])
        
        for handler in handlers:
            try:
                result = await handler(ctx)
                results.append(result)
                
                if not result.should_propagate:
                    break
                    
            except Exception as e:
                logger.error(f"Handler error for {ctx.event.value}: {e}")
                results.append(HookResult(error=str(e)))
        
        return results
    
    # ============================================================
    # PROPERTIES & UTILITIES
    # ============================================================
    
    @property
    def is_running(self) -> bool:
        return self._running
    
    @property
    def stats(self) -> Dict[str, Any]:
        """Return current engine statistics."""
        return {
            **self._stats,
            "throttle_status": {
                "recent_count": len(self.throttle._hourly_count),
                "session_count": self.throttle._session_count,
            },
            "buffer_turns": self.buffer.turn_count,
            "registered_handlers": {
                ev.value: len(handlers) for ev, handlers in self._handlers.items()
            },
        }
    
    def reset_stats(self):
        """Reset all statistics counters."""
        self._stats = {
            "total_turns_processed": 0,
            "extractions_triggered": 0,
            "facts_written_to_wiki": 0,
            "facts_deduplicated_away": 0,
            "errors": 0,
            "session_start_time": None,
        }


# Import at bottom to avoid circular deps
from .extractor import ExtractionResult
