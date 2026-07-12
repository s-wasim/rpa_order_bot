from typing import Optional

from pydantic import BaseModel, Field


class MatchResult(BaseModel):
    choice_index: Optional[int] = Field(
        description="Index into candidates list of the best match, or null if no confident match"
    )
    confidence: float = Field(description="Confidence score 0.0–1.0")
    reasoning: str = Field(description="Brief reasoning (≤3 sentences)")


def match_product(llm, inventory_item: dict, candidates: list[dict]) -> dict:
    structured_llm = llm.with_structured_output(MatchResult)

    candidates_text = ""
    for i, c in enumerate(candidates):
        candidates_text += f"\n  [{i}] {c['title']} — ${c['price']:.2f}"

    prompt = (
        "You are a purchasing agent matching inventory items to storefront products.\n"
        f"Inventory item: \"{inventory_item['name']}\" (SKU: {inventory_item['sku']})\n"
        "Candidate products from storefront search:"
        f"{candidates_text}\n\n"
        "Select the best match or indicate no confident match exists. "
        "When choice_index is not null, it must be a valid index into the candidates list."
    )

    result = structured_llm.invoke(prompt)
    return result.model_dump()
