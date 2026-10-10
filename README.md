README.md


GameCraft AI 🎮
An AI-powered game asset generator that turns one game idea into a cohesive, art-directed set of game assets.

Describe a game in one sentence, such as "a fantasy game set in an enchanted forest", and GameCraft AI generates a matching character, environment, weapons, and inventory icons that all share the same art style.

Status: Hackathon prototype (Banana Hacks 2026). This README describes the planned pipeline. Sections marked (planned) are not yet implemented. Update this file as features are completed.

The Problem
AI image generators produce random, unrelated images. Each prompt drifts in style, palette, and perspective, so a set of assets rarely looks like it belongs to one game. Game jam teams and indie developers end up spending hours fixing, regenerating, or redrawing assets by hand.

The Solution
GameCraft AI builds a visual foundation first and generates every asset from it:

Concept parsing: An LLM turns your idea into a structured game brief (genre, mood, setting, asset list).
Style bible: A reviewable art direction covering palette, line style, shading, lighting, camera angle, and materials.
Style anchor: A hero image generated from the style bible, used as the visual reference for everything else.
Consistent generation: Each character, environment, and item is generated with the style anchor as a reference image.
Quality control: Each asset is scored against the anchor for style and palette match. Off-style results are regenerated automatically.
