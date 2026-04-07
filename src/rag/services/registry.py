from dataclasses import dataclass, field
from typing import Generic, Mapping

from src.rag.core.interfaces import (
    TInterface,
    RagQueryExpander,
    RagRetriever,
    RagPlanner, # 새로 추가
    RagReranker,
    RagFilterer,
    RagAssembler,
    RagCompressor,
    RagPacker,
    RagPromptMaker,
    RagGenerator,
    RagPostChecker,
    RagInputGuard, # 추가
)



@dataclass(frozen=True)
class BaseRegistry(Generic[TInterface]):
    items: Mapping[str, TInterface] = field(default_factory=dict)
    aliases: Mapping[str, str] = field(default_factory=dict)
    default_key: str = "default"
    strict: bool = False

    def resolve_key(self, key: str="") -> str:
        if not key:
            return self.default_key
        return self.aliases.get(key, key)
    
    def get(self, key: str="") -> TInterface:
        k = self.resolve_key(key)
        v = self.items.get(k, None)
        if v is not None:
            return v
        if self.strict:
            raise KeyError(f"Unknown provider: {key} (resolved={k})")
        
        # fallback
        fallback = self.items.get(self.default_key)
        if fallback is None:
            raise KeyError(
                f"Unknown provider: {key} (resolved={k}), "
                f"and default '{self.default_key}' is not registered."
            )
        return fallback

    def keys(self) -> list[str]:
        return sorted(self.items.keys())
    
class InputGuardRegistry(BaseRegistry[RagInputGuard]):
    pass


class QueryExpanderRegistry(BaseRegistry[RagQueryExpander]):
    pass


class RetrieverRegistry(BaseRegistry[RagRetriever]):
    pass


class RerankerRegistry(BaseRegistry[RagReranker]):
    pass


class FiltererRegistry(BaseRegistry[RagFilterer]):
    pass


class AssemblerRegistry(BaseRegistry[RagAssembler]):
    pass


class CompressorRegistry(BaseRegistry[RagCompressor]):
    pass


class PackerRegistry(BaseRegistry[RagPacker]):
    pass


class PromptMakerRegistry(BaseRegistry[RagPromptMaker]):
    pass


class GeneratorRegistry(BaseRegistry[RagGenerator]):
    pass

class PlannerRegistry(BaseRegistry[RagPlanner]):  # 플래너 클래스 추가.
    pass

class PostCheckerRegistry(BaseRegistry[RagPostChecker]):
    pass