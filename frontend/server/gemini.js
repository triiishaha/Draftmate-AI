"use strict";
// Keeps trying until Gemini answers (or the deadline passes):
//  - overloaded / rate limited / slow  -> wait a bit, then try again (growing pauses)
//  - model not available               -> skip that model for good
//  - after the first failed round      -> look up other Gemini "flash" models the key can use
//  - wrong or blocked API key          -> stop at once with a clear error
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
const msgOf = (e) => String((e && (e.message || e)) || "");

const MODEL_GONE = /404|NOT_FOUND|no longer available/i;
const KEY_PROBLEM = /API_KEY_INVALID|API key not valid|PERMISSION_DENIED|UNAUTHENTICATED|\b40[13]\b/i;
const QUOTA = /exceeded your current quota|RESOURCE_EXHAUSTED|quota/i;
const RETRYABLE = /503|UNAVAILABLE|429|RESOURCE_EXHAUSTED|overload|high demand|did not respond|fetch failed|ECONN|ETIMEDOUT|EAI_AGAIN|socket|\b500\b|INTERNAL|empty response/i;

function createGenerator(ai, configuredModels, options = {}) {
  const attemptTimeoutMs = options.attemptTimeoutMs ?? 30000;
  const deadlineMs = options.deadlineMs ?? 120000;
  const baseDelayMs = options.baseDelayMs ?? 2000;
  const maxDelayMs = options.maxDelayMs ?? 15000;
  const log = options.log ?? console.warn;

  async function discover() {
    try {
      const listing = (async () => {
        const found = [];
        for await (const m of await ai.models.list()) {
          const name = String(m.name || "").replace(/^models\//, "");
          const actions = m.supportedActions || m.supported_actions || [];
          if (
            /flash/i.test(name) &&
            !/image|tts|live|audio|embed|vision|robotics|computer|exp\b/i.test(name) &&
            (!actions.length || actions.includes("generateContent"))
          ) {
            found.push(name);
          }
        }
        return found;
      })();
      const found = await Promise.race([listing, sleep(10000).then(() => [])]);
      const stable = found.filter((n) => !/preview/i.test(n));
      const preview = found.filter((n) => /preview/i.test(n));
      return [...stable, ...preview].filter((n) => !configuredModels.includes(n)).slice(0, 4);
    } catch (e) {
      return [];
    }
  }

  async function once(model, prompt) {
    let timer;
    const timeout = new Promise((_, reject) => {
      timer = setTimeout(
        () => reject(new Error(`${model} did not respond within ${attemptTimeoutMs / 1000} seconds.`)),
        attemptTimeoutMs
      );
    });
    try {
      const response = await Promise.race([ai.models.generateContent({ model, contents: prompt }), timeout]);
      const text = response && response.text;
      if (typeof text !== "string" || !text.trim()) throw new Error(`${model} returned an empty response.`);
      return text.trim();
    } finally {
      clearTimeout(timer);
    }
  }

  return async function generate(prompt) {
    const started = Date.now();
    const models = [...configuredModels];
    const dead = new Set();
    const failures = [];
    let round = 0;
    let discovered = false;
    let quotaRounds = 0;

    while (Date.now() - started < deadlineMs) {
      let anyRetryable = false;
      let failedThisRound = 0;
      let quotaThisRound = 0;
      for (const model of models) {
        if (dead.has(model)) continue;
        if (Date.now() - started >= deadlineMs) break;
        try {
          return await once(model, prompt);
        } catch (error) {
          const message = msgOf(error);
          failures.push(`${model}: ${message.slice(0, 140)}`);
          failedThisRound += 1;
          if (QUOTA.test(message)) quotaThisRound += 1;
          log(`Gemini ${model} failed (round ${round + 1}): ${message.slice(0, 140)}`);
          if (KEY_PROBLEM.test(message)) throw new Error(`Gemini rejected the API key. ${message.slice(0, 200)}`);
          if (MODEL_GONE.test(message)) dead.add(model);
          else if (RETRYABLE.test(message)) anyRetryable = true;
        }
      }

      // Quota errors don't clear in seconds: stop hammering the key and say so.
      quotaRounds = failedThisRound > 0 && quotaThisRound === failedThisRound ? quotaRounds + 1 : 0;
      if (quotaRounds >= 2) throw new Error(`Gemini quota exceeded for this API key. ${failures.slice(-2).join(" | ")}`);

      if (!discovered) {
        discovered = true;
        const extra = await discover();
        for (const name of extra) if (!models.includes(name)) models.push(name);
        if (extra.length) {
          log(`Also trying other models your key can use: ${extra.join(", ")}`);
          anyRetryable = true;
        }
      }

      if (models.every((m) => dead.has(m)) || !anyRetryable) break;
      const wait = Math.min(baseDelayMs * 2 ** round, maxDelayMs);
      round += 1;
      if (Date.now() - started + wait >= deadlineMs) break;
      await sleep(wait);
    }

    throw new Error(`Gemini did not give an answer. ${failures.slice(-4).join(" | ")}`);
  };
}

module.exports = { createGenerator };
