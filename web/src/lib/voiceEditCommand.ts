import { askLlm, LLM_AVAILABLE } from "@/lib/llm";
import { findPoses, type PoseCommand } from "@/lib/poses";
import { wordPattern } from "@/lib/text";

// Pose to insert before or after frame, pose null when not recognised
export type EditCommand = { pose: string | null; frame: number; side: "before" | "after" };

const NUM_WORDS: Record<string, number> = {
  "jeden": 1, "jedna": 1, "jedno": 1, "one": 1,
  "dva": 2, "dve": 2, "two": 2,
  "tri": 3, "three": 3,
  "štyri": 4, "four": 4,
  "päť": 5, "five": 5,
  "šesť": 6, "six": 6,
  "sedem": 7, "seven": 7,
  "osem": 8, "eight": 8,
  "deväť": 9, "nine": 9,
  "desať": 10, "ten": 10,
};

// Keyword fallback, whole words only, so "štyri" is not read as "tri" and "sedem" not as "sed"
function parseLocally(transcript: string, poses: PoseCommand[], frameCount: number): EditCommand | null {
  const side = wordPattern("pred|before").test(transcript) ? "before" : "after";

  const digits = transcript.match(/\d+/);
  const word = Object.keys(NUM_WORDS).find((w) => wordPattern(w).test(transcript));
  const frame = digits ? parseInt(digits[0]) : word ? NUM_WORDS[word] : null;
  if (!frame || frame < 1 || frame > frameCount) return null;

  const pose = findPoses(transcript).find((key) => poses.some((p) => p.name === key)) ?? null;
  return { pose, frame, side };
}

async function parseWithLlm(transcript: string, poses: PoseCommand[], frameCount: number): Promise<EditCommand> {
  const poseList = poses.map((p) => p.name).join(", ");
  const cmd = await askLlm<{ pose: string | null; frame: number | null; side: "before" | "after" | null }>(
    `You are a voice command parser for an exercise frame editor. The user speaks Slovak (or mixed Slovak/English). They have ${frameCount} frames numbered 1 to ${frameCount}.

Valid pose keys: [${poseList}].
Slovak→key hints: drep→crouch, úklon→bow, zamávaj/zamávajte→wave, stoj→stand, sed/sadni→sit, ruky hore→hands_up, t póza/t-póza/tpóza/tipos/depóza/te póza/tpose→t_pose, ukáž vpravo→point_right, ukáž vľavo→point_left.
Slovak side words: pred/pred snímkou→"before", po/za/po snímke→"after".

Return ONLY a JSON object with these fields:
- "pose": one of the valid keys above, or null if you cannot identify the pose
- "frame": integer 1–${frameCount}, or null if not mentioned
- "side": "before" or "after", or null if not mentioned

No other text, only JSON.`,
    transcript,
  );
  if (!cmd.frame || !cmd.side) throw new Error("no frame/side");
  const pose = cmd.pose && poses.some((p) => p.name === cmd.pose) ? cmd.pose : null;
  return { pose, frame: Number(cmd.frame), side: cmd.side === "before" ? "before" : "after" };
}

// LLM when available, keyword fallback on failure, null when nothing recognised
export async function parseEditCommand(transcript: string, poses: PoseCommand[], frameCount: number): Promise<EditCommand | null> {
  if (LLM_AVAILABLE) {
    try {
      return await parseWithLlm(transcript, poses, frameCount);
    } catch {
      // keyword fallback below
    }
  }
  return parseLocally(transcript, poses, frameCount);
}
