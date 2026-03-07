import anthropic, os
client = anthropic.Anthropic(api_key=os.environ.get("CLAUDE_API_KEY",""))
r = client.messages.create(
    model="claude-haiku-4-5-20251001",
    max_tokens=50,
    messages=[{"role":"user","content":"Say hello"}]
)
print("SUCCESS:", r.content[0].text)
