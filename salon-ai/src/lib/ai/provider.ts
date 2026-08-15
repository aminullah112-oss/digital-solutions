/**
 * AI provider abstraction. Swap the active provider via AI_PROVIDER env var
 * without touching any calling code (pipeline.ts, response.ts).
 *
 * - "rule-based" (default): deterministic, offline, zero-credential engine.
 *   This is what powers Demo Mode and works immediately without API keys.
 * - "anthropic": drop-in real-LLM provider. Wire up ANTHROPIC_API_KEY and
 *   implement `generateReply` with a Messages API call — the rest of the
 *   app (scoring, handoff, pipeline) is provider-agnostic and needs no changes.
 */

export interface AIReplyContext {
  customerName: string;
  language: "EN" | "AR" | "MIXED";
  intent: string;
  serviceName: string | null;
  servicePrice: number | null;
  businessName: string;
  knowledgeSnippet: string;
}

export interface AIReplyResult {
  text: string;
  confidence: number;
}

export interface AIProvider {
  readonly name: string;
  generateReply(ctx: AIReplyContext): Promise<AIReplyResult>;
}

class NotConfiguredError extends Error {
  constructor(provider: string) {
    super(`AI provider "${provider}" is not configured. Set the required env vars or switch AI_PROVIDER=rule-based.`);
  }
}

class AnthropicProvider implements AIProvider {
  readonly name = "anthropic";
  async generateReply(_ctx: AIReplyContext): Promise<AIReplyResult> {
    if (!process.env.ANTHROPIC_API_KEY) throw new NotConfiguredError(this.name);
    // Intentionally left as an integration point: call the Anthropic Messages API
    // here with `_ctx` folded into the system prompt/knowledge context, and return
    // the model's text. Not implemented so the app never makes network calls it
    // doesn't need in Demo Mode.
    throw new NotConfiguredError(this.name);
  }
}

/** Deterministic, offline provider — see templates.ts for the actual copy. */
class RuleBasedProvider implements AIProvider {
  readonly name = "rule-based";
  async generateReply(ctx: AIReplyContext): Promise<AIReplyResult> {
    const { buildTemplateReply } = await import("./templates");
    return buildTemplateReply(ctx);
  }
}

let cached: AIProvider | null = null;

export function getAIProvider(): AIProvider {
  if (cached) return cached;
  const kind = process.env.AI_PROVIDER ?? "rule-based";
  cached = kind === "anthropic" ? new AnthropicProvider() : new RuleBasedProvider();
  return cached;
}
