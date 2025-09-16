## 1) Channels, Units, and Notation
### 1.1 Channels (how meaning is carried)
- **Growl band (GR):** low, continuous voicing (throat/chest). Carries **weight** (size, threat, emphasis).
- **Huff band (HF):** unvoiced breath pulses (h-h-h). Carries **attention** (call, readiness, preparatory).
- **Click band (CK):** tongue pops/taps (ṭ, ʟ, ǀ/ǁ approximations). Carries **pointing**, **counting**, and **path**.
- **Hiss band (HS):** s/ʃ bursts. Carries **distance**, **edges**, **location**, **negation**.
- **Hum band (HM):** nasal m/n drones. Carries **participants** and **grouping**.
- **Bark band (BK):** explosive plosive bursts (ak/ok/uk). Carries **events**, **alerts**, **imperative**.

You **combine bands** to form a **Beat**. Beats string into **Phrases**; phrases string into an **Utterance**.
### 1.2 The Beat (smallest unit)
A Beat is one primary band + optional modifiers:
```
<BAND><Pitch><Length><Loudness><Tilt><Repeat>
```
- **Pitch:** ↓ (low), → (mid), ↑ (high).
- **Length:** `:` (long), (none = short).
- **Loudness:** `!` (loud/urgent), (none = normal).
- **Tilt (contour):** `^` rise, `v` fall, `≈` level.
- **Repeat:** `×n` (repeat n times evenly).

**Examples:** `GR↓:` (long low growl), `BK!` (loud bark), `HF→^×2` (two rising mid huffs), `HS↑!` (sharp high hiss).

> **Handbook notation.** We transcribe Beast-Speech in braces: `{GR↓:}`. Multiple beats are separated by spaces. Phrases are separated by `‖`.
### 1.3 Tempo, Meter, and Pause
- **Tempo tiers:** **fast** (immediate/urgent), **steady** (present), **slow** (distant/past or polite).
- **Phrase pause:** short pause = boundary; **long pause** = clause break `‖`.
- **Meter encodes aspect:** single beat = **punctual**; **even cycles** (×2, ×4) = **continuous/habitual**; **accelerando** = **incipient**.
## 2) Phonotactics (what sequences are “well-formed”)
- A phrase **begins** with a **participant marker** (HM) or **attention** (HF).
- The **event nucleus** is a **BK** or **GR** Beat (sometimes both).
- **Arguments** (patient/goal/place) follow as **HS/CK** groups.
- **No more than two modifiers** attach to a Beat (e.g., `GR↓:!` is fine; avoid `GR↓:!^×3`—split into two beats).

**Canonical clause skeleton (spoken close-range):**  
`[HM PARTICIPANT] [HF READY] [BK/GR EVENT] [HS/CK PATH/PLACE] [HS TILT for polarity]`

At distance (howls, drums), reduce to: `[HM] [EVENT] [CK counts]`.
## 3) Reference & Participants (pronouns without words)
Participants are encoded **by HM pattern** at clause start:

|Meaning|Pattern|
|---|---|
|**I / we (speaker)**|`{HM→:}` (one long level hum)|
|**you**|`{HM↑×2}` (two high hums)|
|**that one / third party**|`{HM→×3}` (three mids)|
|**group / many**|`{HM↓×5}` (five low hums)|
|**unknown / someone**|`{HM≈}` (short level hum)|
**Demonstratives** are **deictic** with CK pointing: one click **left hand** = “this (near me)”; right = “that (near you)”; forward double-click = “that (yonder).” Without hands, **head turn + CK** substitutes.
## 4) Case, Number, Degree
- **Case** is by **order** and **band**:
    - **Actor** = initial HM.
    - **Patient/Goal** = HS/CK group **after** the event.
    - **Place/Path** = HS with **tilt** and **pitch** (see §6.4).

- **Number** is by **repeat count** on HM or CK:
    - 1–3 exact: `×1/×2/×3`.
    - **few** = `×4` (soft), **many** = `×5+` (heavier, lower).

- **Degree** (big/small/fast/slow) uses **GR pitch/length** as an adverb before the event:
    - **big/heavy**: `{GR↓:}`; **small/light**: `{GR↑}`.
    - **fast**: `{HF↑×3}`; **slow**: `{HF↓:}`.
## 5) Tense, Aspect, Mood, Polarity, Evidentiality
- **Tense**
    - **present**: steady tempo.
    - **past**: slow tempo + falling tilt on event `{… v}`.
    - **future**: HF preface `{HF→^}` before event.
- **Aspect**
    - **punctual**: single BK/GR.
    - **continuous**: `×2/×4` even cycles.
    - **habitual**: `×4` at slow tempo.
    - **inceptive**: event with **rising tilt** `{… ^}`.
- **Mood**
    - **indicative**: default.
    - **imperative**: **initial BK!** + event.
    - **optative** (“wish/please”): soft HM→: before clause + slow tempo.
- **Negation**
    - **preverbal HS↓** (low hiss) immediately before event = **not**.
    - **strong negation**: HS↓ + BK! before event.
- **Evidentiality**
    - **seen/known**: harsh/creaky GR on the event.
    - **heard/uncertain**: breathy HF overlay on the event.
    - **inferred/track**: CK counting before event.
## 6) Core Semantics (productive “root-families”)
Beast-Speech remains **compositional**. Learn these **event nuclei**; modify with bands above.
### 6.1 Alerts & Social
- **ATTEND / look here:** `{HF→^×2}`
- **YES / okay:** final **rise** on hm `{HM↑}` or echo event `×1` softly.
- **NO / don’t:** `{HS↓ BK!}` before event, or phrase-final `{HS↓ v}`.
- **PEACE / friend:** soft GR→ plus HM pair `{GR→ HM→×2}`.
- **ANGER / threat:** `{GR↓:!}` (sustained low growl) before/after event.
### 6.2 Motion & Control
- **COME (to me):** `{BK! HM→:}` (event then self marker).
- **GO (away):** `{BK! HS↑}` with outward HS tilt.
- **STOP / stay:** `{BK!}` held, then **pause**.
- **FOLLOW:** `{HF→^ HM→: BK}` (ready + me + move).
### 6.3 Transfer & Need
- **GIVE (to me/you/X):** `{BK HMtarget}`; target is HM pattern (§3).
- **TAKE:** `{BK HS↓}` (event + low hiss toward self).
- **HELP:** `{HF→^×3 BK!}` (recruitment huffs + event).
- **PAIN / hurt:** `{GR↓ BK!}` clustered; repeat for severity.
### 6.4 Place, Path, Elements (HS/CK “maps”)
- **here/there/up/down/in/out** are HS with tilt + pitch:
    - **here (grounded):** `{HS→≈}`
    - **there (yonder):** `{HS→^}` (rising)
    - **up/sky:** `{HS↑}`; **down/ground:** `{HS↓}`
    - **in/into:** `{HS→:}` long; **out:** `{HS→}` short + final fall.
- **water:** GR→ + HS≈ soft (“smooth edge”).
- **fire:** BK! + HS↑ “hot edge.”
- **food:** HM hum then GR↑ (light growl).
- **predator/danger:** **double BK!** with HS↑!, often at fast tempo.
### 6.5 Quantity and Measure (CK)
- **one/two/three:** `{CK×1/×2/×3}` taps.
- **many:** `{CK×5+}`; **few:** `{CK×4}`.
- **far/near:** HS pitch: high = far, mid = near.
- **big/small:** GR pitch/length (see §4).
## 7) Clause Patterns
### 7.1 Declarative (Actor–Event–Patient–Place)

```
{HM→:} {HF→} {BK} {HS→^} 
 I        ready   do   there
“I am doing (it) there.”  (Object/context from prior focus or CK pointing)
```
### 7.2 Transitive with target

```
{HM→:} {BK} {HM↑×2}
 I        give   you
= “I give (to you).” (Add object by CK pointing or prior focus)
```
### 7.3 Negative imperative

```
{HS↓ BK!} {BK} 
 don’t       act
= “Don’t do that.”
```
### 7.4 Question (rising final tilt)

```
{HM→:} {HF→} {BK^} {HS→^}
 I        ready   do↑   there
= “Am I to do it there?” (Yes/No)
```
### 7.5 Help call (recruitment)

```
{HF→^×3} {BK!} {HS→:}
  help-come     now     here/inside
= “Help me here, now!”
```
## 8) Human Performance Guide (how to speak it well)
- **GR**: low “rrr” in chest; mouth relaxed; vary **pitch** with larynx; length with breath.
- **HF**: strong **H** puffs from diaphragm; keep jaw open.
- **CK**: tongue clicks; alveolar (t), lateral (l), or dental (t̪). Any clean, distinct tap works.
- **HS**: long **s** or **sh**; shape tongue to steer pitch.
- **HM**: nasal “mm/nn” with closed lips or soft hum.
- **BK**: forceful **ak/ok/uk** bursts; keep it brief and percussive.

**Deictics (pointing)**: chin-juts, hand points, or foot taps; in darkness, use **CK** counts and **HS** tilts instead.

**Distance mode (drums/wood on stone):**
- BK = drum hit; HF = short roll; HS = hand scrape; CK = stick taps; HM = sustained low roll.
## 9) Animal Response Protocol (INT thresholds)
- **INT < 5:** recognize **alerts** (danger, food, stop, come) and **place** tilts; rarely reply.
- **INT ≥ 5:** can **reply simply** using Actor/Event/Place, express **negation**, **desire** (food/water), **pain**, **help**, and **follow/stop**.
- **INT ≥ 8:** can use **counting (1–3)**, simple **transfer** (give/take), and **habitual** vs **punctual** aspect.
## 10) Mini Drill (fluency without dictionary)
Practice these 10 lines aloud, then vary tempo, tilt, and repeats:
1. **Come here (to me).**  
    `{BK! HM→:} {HS→≈}`
2. **Go there (far).**  
    `{BK!} {HS↑}`
3. **Stop now.**  
    `{BK!} ‖ (short full stop)`
4. **Friend, follow.**  
    `{GR→ HM→×2} {HF→} {BK}`
5. **Danger there!**  
    `{BK! BK!} {HS↑!}`
6. **Give me (that).**  
    `{BK HM→:} {CK (point)}`
7. **No / Don’t.**  
    `{HS↓ BK!}`
8. **Help here!**  
    `{HF→^×3} {BK!} {HS→:}`
9. **Food here (now).**  
    `{HM→: GR↑} {HS→≈}`
10. **I see many (tracks).**  
    `{HM→:} {ga-ven as BK→ (your chosen “see” event)} {CK×5+}`  
    (Pick a consistent event symbol for “see/examine”—most speakers use BK softened with breath: `{BK≈}`.)
## 11) Learning Path
1. **Master bands** (GR, HF, CK, HS, HM, BK) and the handbook notation `{…}` with pitch/length/tilt.
2. Drill **participants** (HM patterns) and **deixis** (CK pointing).
3. Practice **tense/aspect** by tempo and repeat counts (present vs past vs future; punctual vs continuous).
4. Combine with **place tilts** (HS↑/HS↓/HS→) and **negation** (HS↓).
5. Rehearse **recruitment** (help, come, follow) and **control** (stop, give, take).
6. Record yourself to stabilize pitch and timing; animals respond to **consistency** more than accent.