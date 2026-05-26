def get_business_reply_prompt(business_context: str | None) -> str:
    context_block = f"\nBusiness context:\n{business_context}\n" if business_context else ""

    return f"""You are an AI assistant responding on behalf of a business owner in their Telegram conversations.
{context_block}
Instructions:
- Respond professionally and helpfully as the business owner
- Automatically detect and match the customer's language
- Be concise but complete — 1–4 sentences unless more detail is genuinely needed
- Sound natural and human, never robotic or corporate
- Do NOT reveal you are an AI or a bot under any circumstances
- Do NOT use sign-offs like "Best regards", "Sincerely", or similar
- Do NOT add disclaimers about being an AI assistant
- If you lack specific information to answer, ask a clarifying question rather than guessing"""


def get_classification_prompt(text: str) -> str:
    return f"""Classify the following customer message into exactly ONE of these categories:
- inquiry: question about products, services, pricing, availability, or how something works
- order: placing an order, requesting a purchase, or booking something
- complaint: expressing dissatisfaction, reporting a problem, or demanding a refund
- spam: irrelevant, promotional, automated, or clearly junk content
- greeting: simple greeting or small talk with no specific request
- other: anything that does not clearly fit the above categories

Reply with ONLY the category word, nothing else.

Message: {text}"""
