# U-11 · Everyday expressions, idioms and metaphors

**Status:** proposed  
**Effort:** M

## What
Add a second group to **"Other ways to say it"**: how people *actually* say this in daily life. That means idioms, set phrases, common metaphors and colloquial expressions, in Spanish and in English, for a word or for a whole phrase. Each one comes with a small label and a short "means / when to use it":

| You select | Spanish | English |
|---|---|---|
| *expensive* | **costar un ojo de la cara** (idiom) · **salir un huevo** (AR, colloquial) | **cost an arm and a leg** (idiom) · **pricey** (casual) |
| *estoy muy cansado* | **estoy muerto** · **estoy hecho pelota** (AR) | **I'm wiped out** · **I'm dead on my feet** |
| *it's easy* | **es pan comido** · **está tirado** (AR) | **it's a piece of cake** · **it's a no-brainer** |

- It uses the same AI request as today's rewrites (the prompt and JSON schema just get an `expressions` list), so it costs no extra call and is cached the same way.
- Labels: *idiom*, *metaphor*, *colloquial*, *slang*, and the region when it matters (AR = Argentina, following the existing vos / neutral setting). Vulgar ones are marked as such, or can be left out with a setting.
- Click to copy, like rewrites. Hover to see the meaning.
- When there's no natural expression, show nothing. It must not invent idioms, and the anti-AI-slop filter in `rewrites.py` applies here too.

## Why
Translations and synonyms tell you what a word *means*. This shows how people really *say* it in chats, emails and conversation, which is the part you can't get from a dictionary.

## Needs
An OpenRouter key, like rewrites today. Without a key, U-13 gives real everyday sentences for free.
