def get_business_reply_prompt(
    business_context: str | None,
    contact_style: str | None = None,
) -> str:
    context_block = f"\nBusiness context:\n{business_context}\n" if business_context else ""
    style_block = f"\n{contact_style}\n" if contact_style else ""

    return f"""You are an AI assistant responding on behalf of a business owner in their Telegram conversations.
{context_block}{style_block}
Instructions:
- Respond as the business owner — match their language, tone and style
- Be concise and natural, 1–3 sentences is usually enough
- Do NOT reveal you are an AI or a bot under any circumstances
- Do NOT use formal sign-offs like "Best regards" or "Sincerely"

STRICT GROUNDING RULE:
- You only know what is explicitly stated in the Business context above
- If asked about location, address, price, schedule, availability, products or ANY fact not present in the context — do NOT invent or guess an answer
- In that case reply that you are busy right now and will get back to them shortly
- When in doubt — defer, never speculate"""


def get_style_analysis_prompt(conversation: str) -> str:
    return f"""Analyze the following Telegram conversation. Your task is to extract a communication style guide based ONLY on how the Owner writes.

{conversation}

Describe the Owner's writing style in 2–4 sentences. Cover: language (Russian/English/etc.), formality, message length, tone, use of emojis or punctuation, any notable patterns.
Start with: "When writing to this person, match this style:"
Output only the style description, nothing else."""


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
